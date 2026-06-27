"""
httpx-based scraper with Akamai bm-verify bypass.

Both Zara and Stradivarius serve an Akamai interstitial (HTTP 200,
~2 KB meta-refresh HTML) on the first request. The bm-verify token
is server-generated and already in that HTML — we extract it, wait
for the timing window, then GET the bm-verify URL with the same
sticky exit IP. Akamai validates the token and returns the real page.
"""
import asyncio
import logging
import random
import re
import string
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

from ..detector.ban import detect_ban_signal
from ..proxy.manager import ProxyManager
from ..storage.models import Product, ScrapeResult
from .base import parse_product_data

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",  # no br: httpx needs brotli package installed
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

_BM_WAIT = 6.0  # seconds to wait before following bm-verify redirect


def _sticky_proxies(raw_url: str) -> Optional[dict]:
    """Inject a random session ID so both requests share the same exit IP."""
    if not raw_url:
        return None
    parsed = urlparse(raw_url)
    sid = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    new_user = f"{parsed.username}-session-{sid}"
    url = f"http://{new_user}:{parsed.password}@{parsed.hostname}:{parsed.port}"
    return {"http://": url, "https://": url}


class HttpScraper:
    """Single HTTP-based scraper used by both brand-specific scraper classes."""

    def __init__(self, proxy: ProxyManager, brand: str) -> None:
        self._proxy = proxy
        self._brand = brand

    async def scrape(self, product: Product) -> ScrapeResult:
        start = time.monotonic()
        proxies = _sticky_proxies(self._proxy.next_raw())

        try:
            async with httpx.AsyncClient(
                proxies=proxies,
                verify=False,
                timeout=30,
                follow_redirects=True,
            ) as client:
                # Step 1: GET product page (will get Akamai interstitial)
                r = await client.get(product.url, headers=_HEADERS)
                status = r.status_code
                html = r.text

                if status in (403, 429, 503):
                    return self._ban(product, start, str(status), status)

                # Akamai interstitial detected → follow bm-verify redirect
                if "bm-verify" in html and "meta http-equiv" in html:
                    m = re.search(r"URL='([^']+bm-verify=[^']+)'", html)
                    if m:
                        bm_path = m.group(1).replace("&amp;", "&")
                        base = f"https://{urlparse(product.url).netloc}"
                        bm_url = urljoin(base, bm_path)
                        log.debug("[%s] Akamai interstitial → waiting %.0fs", self._brand, _BM_WAIT)
                        await asyncio.sleep(_BM_WAIT)
                        r2 = await client.get(
                            bm_url,
                            headers={**_HEADERS, "Referer": str(r.url)},
                        )
                        status = r2.status_code
                        html = r2.text

                # Still an interstitial after bm-verify?
                if "bm-verify" in html and "meta http-equiv" in html:
                    log.warning("[%s] bm-verify loop: %s", self._brand, product.name)
                    return self._ban(product, start, "akamai_loop", status)

                ban = detect_ban_signal(status_code=status, body=html, headers={})
                if ban:
                    log.warning("[%s] Ban %s: %s", self._brand, product.name, ban)
                    return self._ban(product, start, ban, status)

                in_stock, price, currency = parse_product_data({}, html, product.size)
                log.info(
                    "[%s] %s / %s — in_stock=%s price=%s",
                    self._brand, product.name, product.size, in_stock, price,
                )
                return ScrapeResult(
                    product_id=product.id,
                    timestamp=datetime.now(timezone.utc),
                    success=True,
                    status_code=status,
                    in_stock=in_stock,
                    price=price,
                    currency=currency,
                    response_time_ms=int((time.monotonic() - start) * 1000),
                )

        except Exception as exc:
            log.warning("[%s] Error scraping %s: %s", self._brand, product.url, exc)
            return ScrapeResult(
                product_id=product.id,
                timestamp=datetime.now(timezone.utc),
                success=False,
                error_message=str(exc),
                response_time_ms=int((time.monotonic() - start) * 1000),
            )

    @staticmethod
    def _ban(
        product: Product,
        start: float,
        signal: str,
        status: Optional[int] = None,
    ) -> ScrapeResult:
        return ScrapeResult(
            product_id=product.id,
            timestamp=datetime.now(timezone.utc),
            success=False,
            status_code=status,
            ban_signal=signal,
            response_time_ms=int((time.monotonic() - start) * 1000),
        )
