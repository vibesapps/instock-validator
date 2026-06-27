#!/usr/bin/env python3
"""
Tek bir ürünü hemen scrape eder — deploy öncesi sağlık kontrolü.
Kullanım: python scripts/smoke_test.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.proxy.manager import ProxyManager
from src.scraper.browser import BrowserManager
from src.scraper.zara import ZaraScraper
from src.scraper.stradivarius import StradivariusScraper
from src.storage.models import Product

TEST_PRODUCTS = [
    Product(
        name="Smoke Test — Zara",
        brand="zara",
        url="https://www.zara.com/tr/en/",   # ana sayfa — ban tespiti için yeterli
        size="M",
    ),
    Product(
        name="Smoke Test — Stradivarius",
        brand="stradivarius",
        url="https://www.stradivarius.com/tr/",
        size="M",
    ),
]


async def run():
    proxy = ProxyManager()
    browser = BrowserManager(proxy)
    await browser.start()

    zara = ZaraScraper(browser)
    strad = StradivariusScraper(browser)

    all_ok = True
    for product in TEST_PRODUCTS:
        print(f"\nTest: {product.name} ({product.url})")
        scraper = zara if product.brand == "zara" else strad
        result = await scraper.scrape(product)
        status = "OK" if result.success else f"FAIL (ban={result.ban_signal}, err={result.error_message})"
        print(f"  Sonuç: {status} | {result.response_time_ms}ms | HTTP {result.status_code}")
        if not result.success:
            all_ok = False

    await browser.stop()
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(run())
