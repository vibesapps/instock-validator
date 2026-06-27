"""
instock.ai — Veri Katmanı Validasyon Servisi
Entry point. Çalıştırma: python -m src.main
"""

import asyncio
import json
import logging
import os
import random
import signal
import sys
from datetime import datetime
from pathlib import Path

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .proxy.manager import ProxyManager
from .reporter.summary import generate_report, print_report
from .scraper.browser import BrowserManager
from .scraper.stradivarius import StradivariusScraper
from .scraper.zara import ZaraScraper
from .storage.db import init_db, insert_ban_event, insert_scrape_result, upsert_product
from .storage.models import BanEvent, Product

# --- Config from env ---
CONFIG_PATH             = Path(os.getenv("CONFIG_PATH",             "config/products.yml"))
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "30"))
REPORT_INTERVAL_HOURS   = int(os.getenv("REPORT_INTERVAL_HOURS",   "24"))
MIN_DELAY_SECONDS       = float(os.getenv("MIN_DELAY_SECONDS",     "8"))
MAX_DELAY_SECONDS       = float(os.getenv("MAX_DELAY_SECONDS",     "20"))

# --- Logging ---
Path("data").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/instock.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def load_products(path: Path) -> list[Product]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    products: list[Product] = []
    for entry in cfg.get("products", []):
        for size in entry.get("sizes", ["ONE SIZE"]):
            products.append(Product(
                name=entry["name"],
                brand=entry["brand"].lower(),
                url=entry["url"],
                size=size,
            ))
    return products


async def scrape_all(browser: BrowserManager, products: list[Product]) -> None:
    zara_scraper = ZaraScraper(browser)
    strad_scraper = StradivariusScraper(browser)

    log.info("=== Scrape run started: %d product-size pairs ===", len(products))

    for product in products:
        # Randomised inter-request delay — critical for avoiding rate limiting
        delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        log.debug("Waiting %.1fs before next request", delay)
        await asyncio.sleep(delay)

        scraper = zara_scraper if product.brand == "zara" else strad_scraper
        result = await scraper.scrape(product)
        insert_scrape_result(result)

        if result.ban_signal:
            event = BanEvent(
                product_id=product.id,
                signal_type=result.ban_signal,
                details=f"HTTP {result.status_code}" if result.status_code else "n/a",
            )
            insert_ban_event(event)

    log.info("=== Scrape run complete ===")


def run_daily_report() -> None:
    report = generate_report()
    print_report(report)

    out_dir = Path("data/reports")
    out_dir.mkdir(exist_ok=True)
    fname = out_dir / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    fname.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Report saved to %s", fname)


async def main() -> None:
    Path("data/reports").mkdir(parents=True, exist_ok=True)

    init_db()

    products = load_products(CONFIG_PATH)
    log.info("Loaded %d product-size combinations", len(products))
    for p in products:
        upsert_product(p)

    proxy = ProxyManager()
    browser = BrowserManager(proxy)
    await browser.start()

    scheduler = AsyncIOScheduler(timezone="UTC")

    # Fire first scrape immediately, then on interval
    scheduler.add_job(
        scrape_all,
        args=[browser, products],
        trigger="interval",
        minutes=SCRAPE_INTERVAL_MINUTES,
        next_run_time=datetime.utcnow(),
        id="scrape",
        max_instances=1,  # no overlapping runs
    )
    scheduler.add_job(
        run_daily_report,
        trigger="interval",
        hours=REPORT_INTERVAL_HOURS,
        id="report",
    )

    scheduler.start()
    log.info(
        "Scheduler running — scrape every %dm, report every %dh",
        SCRAPE_INTERVAL_MINUTES, REPORT_INTERVAL_HOURS,
    )

    stop = asyncio.Event()

    def _handle_signal(*_):
        log.info("Shutdown signal received")
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    await stop.wait()

    scheduler.shutdown(wait=False)
    await browser.stop()
    log.info("Stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
