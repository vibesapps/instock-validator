import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List

from .models import BanEvent, Product, ScrapeResult

log = logging.getLogger(__name__)

DB_PATH = Path("data/instock.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    brand       TEXT NOT NULL,
    url         TEXT NOT NULL,
    size        TEXT NOT NULL,
    external_id TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scrape_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    success         INTEGER NOT NULL,
    status_code     INTEGER,
    in_stock        INTEGER,
    price           REAL,
    currency        TEXT,
    ban_signal      TEXT,
    error_message   TEXT,
    response_time_ms INTEGER,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS ban_events (
    id                  TEXT PRIMARY KEY,
    product_id          TEXT NOT NULL,
    signal_type         TEXT NOT NULL,
    details             TEXT,
    timestamp           TEXT NOT NULL,
    recovery_timestamp  TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_sr_product_ts ON scrape_results(product_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sr_ts          ON scrape_results(timestamp);
CREATE INDEX IF NOT EXISTS idx_ban_ts         ON ban_events(timestamp);
"""


def _conn(path: Path = DB_PATH) -> sqlite3.Connection:
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def init_db(path: Path = DB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _conn(path) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(_SCHEMA)
    log.info("Database ready at %s", path)


def upsert_product(product: Product, path: Path = DB_PATH) -> None:
    with _conn(path) as c:
        c.execute(
            """
            INSERT OR REPLACE INTO products (id, name, brand, url, size, external_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (product.id, product.name, product.brand, product.url, product.size, product.external_id),
        )


def load_products(path: Path = DB_PATH) -> List[Product]:
    with _conn(path) as c:
        rows = c.execute("SELECT id, name, brand, url, size, external_id FROM products").fetchall()
    return [
        Product(id=r["id"], name=r["name"], brand=r["brand"], url=r["url"],
                size=r["size"], external_id=r["external_id"])
        for r in rows
    ]


def insert_scrape_result(result: ScrapeResult, path: Path = DB_PATH) -> None:
    with _conn(path) as c:
        c.execute(
            """
            INSERT INTO scrape_results
                (product_id, timestamp, success, status_code, in_stock,
                 price, currency, ban_signal, error_message, response_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.product_id,
                result.timestamp.isoformat(),
                int(result.success),
                result.status_code,
                None if result.in_stock is None else int(result.in_stock),
                result.price,
                result.currency,
                result.ban_signal,
                result.error_message,
                result.response_time_ms,
            ),
        )


def insert_ban_event(event: BanEvent, path: Path = DB_PATH) -> None:
    with _conn(path) as c:
        c.execute(
            """
            INSERT INTO ban_events (id, product_id, signal_type, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event.id, event.product_id, event.signal_type, event.details, event.timestamp.isoformat()),
        )


def mark_ban_recovered(ban_id: str, recovery_ts: datetime, path: Path = DB_PATH) -> None:
    with _conn(path) as c:
        c.execute(
            "UPDATE ban_events SET recovery_timestamp = ? WHERE id = ?",
            (recovery_ts.isoformat(), ban_id),
        )
