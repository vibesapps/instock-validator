"""
Scraping yaklaşımlarını test eder:
 1. Stradivarius ürün sayfası (browser)
 2. Zara extra-info API (direkt httpx + BrightData proxy)
Kullanım: python scripts/debug_scrape.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

STRAD_URL = "https://www.stradivarius.com/tr/dugmeli-dokumlu-gomlek-l06226969?colorId=045"
ZARA_URL  = "https://www.zara.com/tr/tr/relaxed-fit-deri-ceket-p05388330.html"
# Zara product ID extracted from URL above
ZARA_PID  = "05388330"

# ── Test 1: Stradivarius product page (browser) ─────────────────────────────

async def test_stradivarius():
    from src.proxy.manager import ProxyManager
    from src.scraper.browser import BrowserManager

    print("\n══════════════════════════════════════════")
    print("TEST 1: Stradivarius product page (browser)")
    print("══════════════════════════════════════════")

    proxy = ProxyManager()
    browser = BrowserManager(proxy)
    await browser.start()

    captured_urls = []
    captured = {}

    async def on_response(resp):
        ct = resp.headers.get("content-type", "")
        if "json" not in ct:
            return
        captured_urls.append(resp.url)
        try:
            data = json.loads(await resp.text())
            if isinstance(data, dict):
                captured.update(data)
        except Exception:
            pass

    async with browser.new_page() as page:
        page.on("response", on_response)
        resp = await page.goto(STRAD_URL, wait_until="domcontentloaded", timeout=30_000)
        print(f"HTTP status: {resp.status if resp else 'None'}")

        try:
            await page.wait_for_selector(
                "h1, .product-detail-view, [data-testid='product-name']",
                timeout=25_000,
            )
            print("Selector found — product page loaded!")
        except Exception as e:
            print(f"Selector timeout: {e}")

        print(f"Final URL: {page.url}")
        html = await page.content()

    await browser.stop()

    print(f"\nYakalanan JSON URL'leri ({len(captured_urls)}):")
    for u in captured_urls[:10]:
        print(" ", u)

    print(f"\nHTML preview (500 chars):\n{html[:500]}")

    if captured:
        print(f"\nJSON keys: {list(captured.keys())[:20]}")


# ── Test 2: Zara extra-info API (httpx + BrightData proxy) ──────────────────

async def test_zara_api():
    try:
        import httpx
    except ImportError:
        print("\nhttpx not installed, skipping API test")
        return

    print("\n══════════════════════════════════════════")
    print("TEST 2: Zara extra-info API (httpx + proxy)")
    print("══════════════════════════════════════════")

    proxy_url = os.getenv("PROXY_LIST", "").split(",")[0].strip()
    if not proxy_url:
        print("PROXY_LIST boş — proxy yok, direkt bağlantı deneniyor")
    else:
        print(f"Proxy: {proxy_url[:40]}...")

    api_url = (
        f"https://www.zara.com/tr/tr/product/{ZARA_PID}/extra-info"
        f"?sectionName=man&gender=man"
    )
    print(f"API URL: {api_url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Referer": ZARA_URL,
        "x-requested-with": "XMLHttpRequest",
    }

    proxy_dict = {"http://": proxy_url, "https://": proxy_url}

    try:
        async with httpx.AsyncClient(
            proxies=proxy_dict,
            verify=False,
            timeout=30,
            follow_redirects=True,
        ) as client:
            r = await client.get(api_url, headers=headers)
            print(f"Status: {r.status_code}")
            print(f"Content-Type: {r.headers.get('content-type')}")
            print(f"Response preview:\n{r.text[:2000]}")
    except Exception as e:
        print(f"Error: {e}")


async def main():
    await test_stradivarius()
    await test_zara_api()

if __name__ == "__main__":
    asyncio.run(main())
