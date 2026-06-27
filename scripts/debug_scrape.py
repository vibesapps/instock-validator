"""
Debug script v5: httpx ile ürün sayfasını direkt çek.
httpx istekleri Akamai interstitial almıyor — gerçek HTML geliyor.
Next.js SSR HTML'de __NEXT_DATA__ veya JSON-LD içinde fiyat/stok var.
Kullanım: python scripts/debug_scrape.py
"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

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


def _proxy_dict() -> dict:
    proxy_url = os.getenv("PROXY_LIST", "").split(",")[0].strip()
    if proxy_url:
        print(f"Proxy: {proxy_url[:60]}...")
    return {"http://": proxy_url, "https://": proxy_url} if proxy_url else {}


async def test_site(name: str, url: str, client: "httpx.AsyncClient") -> None:
    print(f"\n══════════════════════════════════════════════════")
    print(f"TEST: {name}")
    print(f"══════════════════════════════════════════════════")

    try:
        r = await client.get(url, headers=_HEADERS)
    except Exception as e:
        print(f"Request error: {e}")
        return

    print(f"Status : {r.status_code}")
    print(f"URL    : {str(r.url)[:90]}")
    print(f"CT     : {r.headers.get('content-type', '?')}")
    print(f"Size   : {len(r.text)} bytes")

    # Akamai interstitial check
    if ("bm-verify" in r.text and "meta http-equiv" in r.text) or "_sec/verify" in r.text:
        print("⚠ Akamai interstitial — httpx also blocked (unexpected)")
        print(r.text[:400])
        return

    found_anything = False

    # ── 1. Next.js __NEXT_DATA__ ─────────────────────────────────────────────
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        r.text, re.DOTALL,
    )
    if m:
        found_anything = True
        raw = m.group(1)
        print(f"\n✓ __NEXT_DATA__ ({len(raw)} bytes)")
        try:
            nd = json.loads(raw)
            page_props = nd.get("props", {}).get("pageProps", {})
            print(f"  pageProps keys: {list(page_props.keys())[:20]}")
            # Dump anything that looks like product/price/stock data
            for k, v in page_props.items():
                if isinstance(v, dict):
                    sub = list(v.keys())
                    if any(s in str(v).lower() for s in ("price", "stock", "availab", "size", "color")):
                        print(f"  pageProps.{k} keys: {sub[:12]}")
                        print(f"    {json.dumps(v, ensure_ascii=False)[:600]}")
                elif isinstance(v, (str, int, float, bool)):
                    if any(s in k.lower() for s in ("price", "stock", "availab")):
                        print(f"  pageProps.{k} = {v}")
        except Exception as e:
            print(f"  parse error: {e}")
            print(f"  raw[:300]: {raw[:300]}")
    else:
        print("\n  (no __NEXT_DATA__)")

    # ── 2. JSON-LD (schema.org) ───────────────────────────────────────────────
    ld_matches = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL
    )
    if ld_matches:
        found_anything = True
        print(f"\n✓ JSON-LD blobs: {len(ld_matches)}")
        for i, ld in enumerate(ld_matches):
            try:
                data = json.loads(ld)
                t = data.get("@type", "?")
                print(f"  #{i+1} @type={t}")
                if t in ("Product", "Offer"):
                    print(f"    {json.dumps(data, ensure_ascii=False)[:800]}")
                elif t == "ItemList":
                    items = data.get("itemListElement", [])
                    print(f"    {len(items)} items")
            except Exception as e:
                print(f"  #{i+1} parse error: {e}")
    else:
        print("  (no JSON-LD)")

    # ── 3. Inline script state blobs ─────────────────────────────────────────
    for pat in [
        r'window\.__STATE__\s*=\s*(\{.*?\})\s*;',
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;',
        r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;',
    ]:
        m2 = re.search(pat, r.text, re.DOTALL)
        if m2:
            found_anything = True
            try:
                data = json.loads(m2.group(1))
                print(f"\n✓ {pat[:25]}... keys: {list(data.keys())[:10]}")
                print(f"  {json.dumps(data, ensure_ascii=False)[:500]}")
            except Exception:
                print(f"\n✓ {pat[:25]}... (parse error)")

    # ── 4. Any script mentioning price/stock ─────────────────────────────────
    scripts = re.findall(r'<script(?:[^>]*)>(.*?)</script>', r.text, re.DOTALL)
    for script in scripts:
        lower = script.lower()
        if any(k in lower for k in ('"price"', '"availability"', '"instock"', '"stocklevel"', 'fiyat', 'stok')):
            # Try extracting JSON from the script
            for json_pat in [r'(\{[^{}]{20,}\})', r'(\[[^\[\]]{20,}\])']:
                for blob in re.findall(json_pat, script)[:5]:
                    try:
                        data = json.loads(blob)
                        keys = list(data.keys()) if isinstance(data, dict) else []
                        if any(k in keys for k in ("price", "availability", "inStock", "stockLevel")):
                            found_anything = True
                            print(f"\n✓ Inline price/stock JSON: {keys}")
                            print(f"  {json.dumps(data, ensure_ascii=False)[:400]}")
                    except Exception:
                        pass

    if not found_anything:
        print("\nNo embedded JSON found. Raw HTML preview (800 chars):")
        print(r.text[:800])


async def main():
    proxy_dict = _proxy_dict()
    async with httpx.AsyncClient(
        proxies=proxy_dict or None,
        verify=False,
        timeout=30,
        follow_redirects=True,
    ) as client:
        await test_site("Zara (httpx — ürün sayfası direkt)", ZARA_URL, client)
        await test_site("Stradivarius (httpx — ürün sayfası direkt)", STRAD_URL, client)


if __name__ == "__main__":
    asyncio.run(main())
