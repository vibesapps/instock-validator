"""Shared parsing helpers used by both Zara and Stradivarius scrapers."""

import json
import re
from typing import Optional, Tuple

_PRICE_RE = re.compile(r'"price"\s*:\s*"?(\d+(?:[.,]\d+)?)"?')
_AVAIL_RE = re.compile(r'"availability"\s*:\s*"([^"]+)"', re.I)


def extract_next_data(html: str) -> dict:
    """Parse Next.js __NEXT_DATA__ JSON block embedded in page HTML."""
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>([^<]+)</script>', html, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}


def extract_json_ld(html: str) -> list[dict]:
    """Return all JSON-LD blocks from page HTML."""
    results = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([^<]+)</script>', html, re.S):
        try:
            results.append(json.loads(m.group(1)))
        except Exception:
            pass
    return results


def parse_price_from_text(raw: str) -> Optional[float]:
    m = _PRICE_RE.search(raw)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def parse_stock_from_text(raw: str, target_size: str) -> Optional[bool]:
    """
    Look for the target size near an availability indicator in a JSON string.
    Returns True (in stock), False (out of stock), or None (unknown).
    """
    upper_raw = raw.upper()
    size_upper = target_size.upper()
    if size_upper not in upper_raw:
        return None

    idx = upper_raw.find(size_upper)
    # Check 400-char window around size mention
    snippet = raw[max(0, idx - 300): idx + 300].lower()
    if any(k in snippet for k in ("out_of_stock", '"unavailable"', '"0"', '"qty":0')):
        return False
    if any(k in snippet for k in ("instock", "available", '"qty":1', '"qty":2')):
        return True
    return None


def parse_availability_schema(html: str) -> Optional[bool]:
    """Fall back to JSON-LD Product availability."""
    m = _AVAIL_RE.search(html)
    if not m:
        return None
    av = m.group(1).lower()
    if "instock" in av or "available" in av:
        return True
    if "outofstock" in av or "unavailable" in av:
        return False
    return None


def parse_product_data(
    captured_api_data: dict,
    page_html: str,
    target_size: str,
) -> Tuple[Optional[bool], Optional[float], Optional[str]]:
    """
    Unified parser. Tries API data first, then Next.js __NEXT_DATA__, then JSON-LD.
    Returns (in_stock, price, currency).
    """
    raw_api = json.dumps(captured_api_data)

    # --- Stock ---
    in_stock = parse_stock_from_text(raw_api, target_size)

    if in_stock is None:
        next_data = extract_next_data(page_html)
        raw_next = json.dumps(next_data)
        in_stock = parse_stock_from_text(raw_next, target_size)

    if in_stock is None:
        in_stock = parse_availability_schema(page_html)

    # --- Price ---
    price = parse_price_from_text(raw_api)
    if price is None:
        price = parse_price_from_text(page_html)

    currency = "TRY" if price is not None else None

    return in_stock, price, currency
