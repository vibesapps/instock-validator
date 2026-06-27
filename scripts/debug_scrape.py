"""
Debug script v6: httpx ile bm-verify URL'ini direkt follow et.
Akamai interstitial'ı bm-verify tokenını sunucu tarafında HTML'e gömer
(JavaScript ile üretilmiyor). Aynı sticky IP ile GET edersek token
validate edilebilir — _sec/verify XHR zorunlu değilse ürün sayfası açılır.
Kullanım: python scripts/debug_scrape.py
"""
import asyncio
import json
import os
import random
import re
import string
import sys
from pathlib import Path
from urllib.parse import urlparse, urljoin

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError:
    print("httpx not installed")
    sys.exit(1)

ZARA_URL  = "https://www.zara.com/tr/tr/relaxed-fit-deri-ceket-p05388330.html"
STRAD_URL = "https://www.stradivarius.com/tr/dugmeli-dokumlu-gomlek-l06226969?colorId=045"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}


def _sticky_proxy(proxy_url: str) -> dict:
    """Build proxy dict with a random session ID to pin exit IP."""
    if not proxy_url:
        return {}
    parsed = urlparse(proxy_url)
    sid = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    new_user = f"{parsed.username}-session-{sid}"
    url = f"http://{new_user}:{parsed.password}@{parsed.hostname}:{parsed.port}"
    print(f"Sticky proxy user: ...{new_user[-25:]}")
    return {"http://": url, "https://": url}


def _extract_data(html: str, label: str) -> None:
    """Print any price/stock/product data found in HTML."""
    # __NEXT_DATA__
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL,
    )
    if m:
        raw = m.group(1)
        print(f"  ✓ __NEXT_DATA__ {len(raw)} bytes")
        try:
            nd = json.loads(raw)
            pp = nd.get("props", {}).get("pageProps", {})
            print(f"    pageProps keys: {list(pp.keys())[:20]}")
            for k, v in pp.items():
                if isinstance(v, dict) and any(
                    s in str(v).lower() for s in ("price", "stock", "availab", "size")
                ):
                    print(f"    pageProps.{k}: {json.dumps(v, ensure_ascii=False)[:500]}")
        except Exception as e:
            print(f"    parse error: {e}")
    else:
        print("  (no __NEXT_DATA__)")

    # JSON-LD
    ld_list = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    )
    for i, ld in enumerate(ld_list):
        try:
            data = json.loads(ld)
            t = data.get("@type", "?")
            print(f"  JSON-LD #{i+1} @type={t}")
            if t in ("Product", "Offer"):
                print(f"    {json.dumps(data, ensure_ascii=False)[:600]}")
        except Exception:
            pass


async def test_bm_follow(name: str, url: str, client: "httpx.AsyncClient") -> None:
    print(f"\n══════════════════════════════════════════════════")
    print(f"TEST: {name}")
    print(f"══════════════════════════════════════════════════")
    base = f"https://{urlparse(url).netloc}"

    # ── Step 1: GET product page ──────────────────────────────────────────────
    print(f"Step 1: GET {url}")
    try:
        r1 = await client.get(url, headers=_HEADERS)
    except Exception as e:
        print(f"  Error: {e}")
        return

    print(f"  Status={r1.status_code} Size={len(r1.text)} CT={r1.headers.get('content-type','?')[:30]}")

    is_interstitial = "bm-verify" in r1.text and "meta http-equiv" in r1.text
    if not is_interstitial:
        print("  No interstitial — got response directly!")
        print(f"  HTML preview: {r1.text[:400]}")
        _extract_data(r1.text, name)
        return

    # Extract bm-verify redirect URL from HTML
    m = re.search(r"URL='([^']+bm-verify=[^']+)'", r1.text)
    if not m:
        print("  No bm-verify URL found")
        return

    bm_path = m.group(1).replace("&amp;", "&")
    bm_url = urljoin(base, bm_path)
    print(f"  bm-verify URL: {bm_url[:90]}...")

    # ── Step 2: Follow bm-verify (same sticky IP) ─────────────────────────────
    # Akamai's meta-refresh says 5s; wait a moment to respect timing window
    print("  Waiting 6s (bm-verify timing window)...")
    await asyncio.sleep(6)

    print(f"Step 2: GET bm-verify URL")
    headers2 = {**_HEADERS, "Referer": str(r1.url)}
    try:
        r2 = await client.get(bm_url, headers=headers2)
    except Exception as e:
        print(f"  Error: {e}")
        return

    print(f"  Status={r2.status_code} Size={len(r2.text)} URL={str(r2.url)[:80]}")

    is_interstitial2 = "bm-verify" in r2.text and "meta http-equiv" in r2.text
    if is_interstitial2:
        print("  ⚠ Got ANOTHER interstitial — _sec/verify is required server-side")
        print(f"  (bm-verify approach won't work without Web Unlocker)")
        return

    # Check if it's a 403/block
    if r2.status_code in (403, 429, 503):
        print(f"  ⚠ Blocked: {r2.status_code}")
        return

    # Check what we got
    if "_sec/verify" in r2.text:
        print("  ⚠ Got interstitial without meta-refresh tag (different challenge format)")
        return

    print("  ✓ No interstitial! Extracting product data...")
    _extract_data(r2.text, name)

    if not any(k in r2.text for k in ("__NEXT_DATA__", "application/ld+json")):
        print(f"  HTML preview (600 chars):\n{r2.text[:600]}")


async def main():
    proxy_url = os.getenv("PROXY_LIST", "").split(",")[0].strip()
    proxy_dict = _sticky_proxy(proxy_url)

    async with httpx.AsyncClient(
        proxies=proxy_dict or None,
        verify=False,
        timeout=30,
        follow_redirects=True,
    ) as client:
        await test_bm_follow("Zara — bm-verify follow", ZARA_URL, client)
        await test_bm_follow("Stradivarius — bm-verify follow", STRAD_URL, client)


if __name__ == "__main__":
    asyncio.run(main())
