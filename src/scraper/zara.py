import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import Response

from ..detector.ban import detect_ban_signal
from ..storage.models import Product, ScrapeResult
from .base import parse_product_data
from .browser import BrowserManager

log = logging.getLogger(__name__)

# Zara API URL fragments that carry product/stock data
_API_KEYWORDS = ("product", "stock", "availability", "catalog", "price", "extra-info")


class ZaraScraper:
    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    async def scrape(self, product: Product) -> ScrapeResult:
        start = time.monotonic()
        captured: dict = {}
        ban_signal: Optional[str] = None
        final_status: Optional[int] = None

        async def on_response(resp: Response) -> None:
            nonlocal ban_signal
            if resp.status in (403, 429, 503):
                ban_signal = str(resp.status)
                return
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return
            if not any(k in resp.url for k in _API_KEYWORDS):
                return
            try:
                captured.update(json.loads(await resp.text()))
            except Exception:
                pass

        try:
            async with self._browser.new_page() as page:
                page.on("response", on_response)

                resp = await page.goto(product.url, wait_until="domcontentloaded", timeout=30_000)
                final_status = resp.status if resp else None

                # Akamai interstitial: wait for JS challenge to solve and redirect to product page
                try:
                    await page.wait_for_url(
                        lambda url: "bm-verify" not in url and "_sec" not in url,
                        timeout=20_000,
                    )
                    await page.wait_for_load_state("networkidle", timeout=8_000)
                except Exception:
                    pass

                page_html = await page.content()

                if not ban_signal:
                    ban_signal = detect_ban_signal(
                        status_code=final_status,
                        body=page_html,
                        headers=dict(resp.headers) if resp else None,
                    )

                if ban_signal:
                    log.warning("[zara] Ban: product=%s signal=%s", product.name, ban_signal)
                    return ScrapeResult(
                        product_id=product.id,
                        timestamp=datetime.now(timezone.utc),
                        success=False,
                        status_code=final_status,
                        ban_signal=ban_signal,
                        response_time_ms=int((time.monotonic() - start) * 1000),
                    )

                in_stock, price, currency = parse_product_data(captured, page_html, product.size)

                log.info(
                    "[zara] OK: %s / %s | in_stock=%s price=%s",
                    product.name, product.size, in_stock, price,
                )
                return ScrapeResult(
                    product_id=product.id,
                    timestamp=datetime.now(timezone.utc),
                    success=True,
                    status_code=final_status,
                    in_stock=in_stock,
                    price=price,
                    currency=currency,
                    response_time_ms=int((time.monotonic() - start) * 1000),
                )

        except Exception as exc:
            log.warning("[zara] Error scraping %s: %s", product.url, exc)
            return ScrapeResult(
                product_id=product.id,
                timestamp=datetime.now(timezone.utc),
                success=False,
                error_message=str(exc),
                response_time_ms=int((time.monotonic() - start) * 1000),
            )
