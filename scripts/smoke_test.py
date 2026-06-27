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
from src.scraper.zara import ZaraScraper
from src.scraper.stradivarius import StradivariusScraper
from src.storage.models import Product

TEST_PRODUCTS = [
    Product(
        name="Smoke Test — Zara",
        brand="zara",
        url="https://www.zara.com/tr/tr/relaxed-fit-deri-ceket-p05388330.html",
        size="M",
    ),
    Product(
        name="Smoke Test — Stradivarius",
        brand="stradivarius",
        url="https://www.stradivarius.com/tr/dugmeli-dokumlu-gomlek-l06226969?colorId=045",
        size="M",
    ),
]


async def run():
    proxy = ProxyManager()
    zara = ZaraScraper(proxy)
    strad = StradivariusScraper(proxy)

    all_ok = True
    for product in TEST_PRODUCTS:
        print(f"\nTest: {product.name}")
        scraper = zara if product.brand == "zara" else strad
        result = await scraper.scrape(product)

        print(f"  success    : {result.success}")
        print(f"  status     : {result.status_code}")
        print(f"  in_stock   : {result.in_stock}")
        print(f"  price      : {result.price}")
        print(f"  currency   : {result.currency}")
        print(f"  ban_signal : {result.ban_signal}")
        print(f"  error      : {result.error_message}")
        print(f"  time_ms    : {result.response_time_ms}")

        if not result.success:
            print(f"  => FAIL")
            all_ok = False
        elif result.in_stock is None and result.price is None:
            print(f"  => WARN — data not parsed (in_stock=None, price=None)")
            all_ok = False
        else:
            print(f"  => OK")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(run())
