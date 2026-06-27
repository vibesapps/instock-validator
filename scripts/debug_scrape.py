"""
Debug script v3: Akamai interstitial bypass approaches
 1. Stradivarius: intercept /_sec/verify at network level → fake 200 OK so JS
    thinks challenge passed → prevents reload() loop → meta-refresh fires → bm-verify
 2. Zara extra-info API: try multiple endpoint formats
Kullanım: python scripts/debug_scrape.py
"""
import asyncio
import json
import os
import random
import string
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

STRAD_URL = "https://www.stradivarius.com/tr/dugmeli-dokumlu-gomlek-l06226969?colorId=045"
ZARA_URL  = "https://www.zara.com/tr/tr/relaxed-fit-deri-ceket-p05388330.html"
ZARA_PID  = "05388330"

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0"

_STEALTH = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
"""


def _proxy_conf(proxy_url: str) -> dict:
    """Build Playwright proxy dict with a sticky session ID."""
    parsed = urlparse(proxy_url)
    session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    new_user = f"{parsed.username}-session-{session_id}"
    return {
        "server": f"http://{parsed.hostname}:{parsed.port}",
        "username": new_user,
        "password": parsed.password or "",
    }


# ── TEST 1: Stradivarius — /_sec/verify intercept ───────────────────────────

async def test_stradivarius_intercept():
    from playwright.async_api import async_playwright

    print("\n══════════════════════════════════════════════════")
    print("TEST 1: Stradivarius — _sec/verify route intercept")
    print("══════════════════════════════════════════════════")

    proxy_url = os.getenv("PROXY_LIST", "").split(",")[0].strip()
    proxy_conf = _proxy_conf(proxy_url) if proxy_url else None
    if proxy_conf:
        print(f"Proxy: {proxy_conf['server']} as {proxy_conf['username'][:35]}...")
    else:
        print("No proxy (direct connection)")

    captured_json: dict = {}
    intercepted_count = 0

    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=_UA,
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            proxy=proxy_conf,
            ignore_https_errors=True,
        )
        await ctx.add_init_script(_STEALTH)
        page = await ctx.new_page()

        # Intercept Akamai's _sec/verify: return 200 so JS thinks challenge passed.
        # Without this, the XHR fails through BrightData's SSL MITM → catch(e) →
        # window.location.reload() → infinite reload loop → meta-refresh never fires.
        async def handle_sec_verify(route, request):
            nonlocal intercepted_count
            intercepted_count += 1
            print(f"  [intercept] {request.method} {request.url[:70]} → 200 OK")
            await route.fulfill(status=200, body=b"", content_type="text/plain")

        await page.route("**/_sec/verify*", handle_sec_verify)

        # Capture any JSON API responses (product data)
        async def on_response(resp):
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                data = json.loads(await resp.text())
                if isinstance(data, dict):
                    captured_json.update(data)
                    print(f"  [json] {resp.url[:70]} → keys: {list(data.keys())[:5]}")
            except Exception:
                pass

        page.on("response", on_response)

        # Step 1: Load product page (will get interstitial)
        resp = await page.goto(STRAD_URL, wait_until="domcontentloaded", timeout=30_000)
        print(f"\nInitial status: {resp.status if resp else 'None'}")
        html = await page.content()
        is_interstitial = "bm-verify" in html or "_sec/verify" in html
        print(f"Page type: {'⚠ interstitial' if is_interstitial else '✓ product page'}")
        print(f"_sec/verify intercepts so far: {intercepted_count}")

        if is_interstitial:
            # Step 2: Wait for meta-refresh (5s) + product page load (up to 15s)
            print("\nWaiting 18s for meta-refresh → bm-verify → product page...")
            try:
                await page.wait_for_selector(
                    "h1, .product-detail-view, [data-testid='product-name'], [data-qa-id]",
                    timeout=18_000,
                )
                print("✓ Product selector found!")
            except Exception:
                print("✗ Selector timeout (18s)")

            print(f"Final URL: {page.url}")
            html2 = await page.content()
            still_interstitial = "bm-verify" in html2 or "_sec/verify" in html2
            print(f"Still interstitial: {still_interstitial}")
            if not still_interstitial:
                print(f"HTML preview (300 chars):\n{html2[:300]}")
        else:
            print(f"HTML preview (300 chars):\n{html[:300]}")

        print(f"\nTotal _sec/verify intercepts: {intercepted_count}")
        if captured_json:
            print(f"Captured JSON keys: {list(captured_json.keys())[:20]}")
        else:
            print("No JSON captured")

        await ctx.close()
        await browser.close()


# ── TEST 2: Zara extra-info API (httpx) ─────────────────────────────────────

async def test_zara_api():
    try:
        import httpx
    except ImportError:
        print("\nhttpx not installed")
        return

    print("\n══════════════════════════════════════════════════")
    print("TEST 2: Zara API (httpx + proxy)")
    print("══════════════════════════════════════════════════")

    proxy_url = os.getenv("PROXY_LIST", "").split(",")[0].strip()
    proxy_dict = {"http://": proxy_url, "https://": proxy_url} if proxy_url else {}
    if proxy_url:
        print(f"Proxy: {proxy_url[:50]}...")
    else:
        print("No proxy (direct)")

    headers = {
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Referer": ZARA_URL,
        "x-requested-with": "XMLHttpRequest",
    }

    # Multiple endpoint formats to try
    endpoints = [
        f"https://www.zara.com/tr/tr/product/{ZARA_PID}/extra-info",
        f"https://www.zara.com/tr/tr/product/{ZARA_PID}/extra-info?sectionName=man&gender=man",
        f"https://www.zara.com/itxrest/2/catalog/store/11726/product/detail?physicalStoreId=null&productId={ZARA_PID}&languageId=-39",
        f"https://www.zara.com/itxrest/2/catalog/store/11726/category/product/detail?productId={ZARA_PID}",
    ]

    async with httpx.AsyncClient(
        proxies=proxy_dict or None,
        verify=False,
        timeout=30,
        follow_redirects=True,
    ) as client:
        for url in endpoints:
            try:
                r = await client.get(url, headers=headers)
                ct = r.headers.get("content-type", "")
                print(f"\n{url[-60:]}")
                print(f"  Status: {r.status_code} | CT: {ct[:50]}")
                if "json" in ct:
                    try:
                        data = r.json()
                        print(f"  ✓ JSON keys: {list(data.keys())[:10]}")
                    except Exception:
                        print(f"  JSON parse error")
                else:
                    print(f"  Preview: {r.text[:120]}")
            except Exception as e:
                print(f"  Error: {e}")


async def main():
    await test_stradivarius_intercept()
    await test_zara_api()


if __name__ == "__main__":
    asyncio.run(main())
