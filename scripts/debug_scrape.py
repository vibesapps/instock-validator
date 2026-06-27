"""
Tek bir ürünü scrape edip ham veriyi döker.
Kullanım: python scripts/debug_scrape.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.proxy.manager import ProxyManager
from src.scraper.browser import BrowserManager
from src.storage.models import Product

TEST_URL = "https://www.zara.com/tr/tr/relaxed-fit-deri-ceket-p05388330.html"

async def run():
    proxy = ProxyManager()
    browser = BrowserManager(proxy)
    await browser.start()

    captured = {}
    captured_urls = []

    async def on_response(resp):
        ct = resp.headers.get("content-type", "")
        if "json" not in ct:
            return
        captured_urls.append(resp.url)
        try:
            data = json.loads(await resp.text())
            captured.update(data) if isinstance(data, dict) else None
        except Exception:
            pass

    async with browser.new_page() as page:
        page.on("response", on_response)
        resp = await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=30_000)
        print(f"\nHTTP status: {resp.status if resp else 'None'}")

        try:
            await page.wait_for_url(
                lambda url: "bm-verify" not in url and "_sec" not in url,
                timeout=20_000,
            )
            await page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass

        print(f"Final URL: {page.url}")
        html = await page.content()

    await browser.stop()

    print(f"\n── Yakalanan JSON URL'leri ({len(captured_urls)}) ──")
    for u in captured_urls:
        print(" ", u)

    print(f"\n── captured keys: {list(captured.keys())[:20]} ──")
    print(json.dumps(captured, indent=2, ensure_ascii=False)[:3000])

    print(f"\n── HTML snippet (ilk 3000 karakter) ──")
    print(html[:3000])

if __name__ == "__main__":
    asyncio.run(run())
