"""
Debug script v4: itxrest API brute-force — find working store IDs for
Zara TR and Stradivarius TR. Browser approach is confirmed blocked
(Akamai validates _sec/verify server-side, client tricks don't work).

Kullanım: python scripts/debug_scrape.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError:
    print("httpx not installed")
    sys.exit(1)

ZARA_PID   = "05388330"   # from URL: relaxed-fit-deri-ceket-p05388330.html
STRAD_PID  = "6226969"    # from URL: dugmeli-dokumlu-gomlek-l06226969
STRAD_URL  = "https://www.stradivarius.com/tr/dugmeli-dokumlu-gomlek-l06226969?colorId=045"
ZARA_URL   = "https://www.zara.com/tr/tr/relaxed-fit-deri-ceket-p05388330.html"

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0"

# Inditex brand store IDs to try for Turkey online store
# (itxrest storeId = country market ID, negative languageId = tr)
ZARA_STORE_IDS  = [11726, 10706, 3132, 25025, 13059, 11730, 11700, 26009, 2323, 1749]
STRAD_STORE_IDS = [11726, 10706, 54016, 54018, 54010, 25025, 13059, 50005, 3132]


def _proxy_dict() -> dict:
    proxy_url = os.getenv("PROXY_LIST", "").split(",")[0].strip()
    if not proxy_url:
        return {}
    print(f"Proxy: {proxy_url[:50]}...")
    return {"http://": proxy_url, "https://": proxy_url}


def _fmt_json(data) -> str:
    """Short repr of a JSON value."""
    if isinstance(data, dict):
        return str({k: str(v)[:60] for k, v in data.items()})
    return str(data)[:120]


async def test_zara_itxrest():
    print("\n══════════════════════════════════════════════════")
    print("TEST 1: Zara itxrest — find correct Turkey store ID")
    print("══════════════════════════════════════════════════")

    proxy_dict = _proxy_dict()
    headers = {
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Referer": ZARA_URL,
    }

    # Try two product ID formats: with and without leading zero
    pid_variants = [ZARA_PID, ZARA_PID.lstrip("0")]

    async with httpx.AsyncClient(
        proxies=proxy_dict or None,
        verify=False,
        timeout=30,
        follow_redirects=True,
    ) as client:
        for store_id in ZARA_STORE_IDS:
            for pid in pid_variants:
                url = (
                    f"https://www.zara.com/itxrest/2/catalog/store/{store_id}"
                    f"/product/detail?physicalStoreId=null&productId={pid}&languageId=-39"
                )
                try:
                    r = await client.get(url, headers=headers)
                    ct = r.headers.get("content-type", "")
                    if "json" in ct:
                        try:
                            body = r.json()
                        except Exception:
                            body = {"raw": r.text[:100]}
                        status_mark = "✓" if r.status_code == 200 else f"✗({r.status_code})"
                        print(f"  store={store_id} pid={pid}: {status_mark} → {_fmt_json(body)}")
                        if r.status_code == 200:
                            print(f"\n  *** FOUND WORKING CONFIG: store={store_id} pid={pid} ***")
                            print(json.dumps(body, indent=2, ensure_ascii=False)[:2000])
                            return  # stop on first success
                    else:
                        if r.status_code != 404:
                            print(f"  store={store_id} pid={pid}: {r.status_code} {ct[:30]}")
                except Exception as e:
                    print(f"  store={store_id} pid={pid}: ERROR {e}")


async def test_strad_itxrest():
    print("\n══════════════════════════════════════════════════")
    print("TEST 2: Stradivarius itxrest — find Turkey store ID")
    print("══════════════════════════════════════════════════")

    proxy_dict = _proxy_dict()
    headers = {
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Referer": STRAD_URL,
    }

    pid_variants = [STRAD_PID, "0" + STRAD_PID]

    async with httpx.AsyncClient(
        proxies=proxy_dict or None,
        verify=False,
        timeout=30,
        follow_redirects=True,
    ) as client:
        for store_id in STRAD_STORE_IDS:
            for pid in pid_variants:
                url = (
                    f"https://www.stradivarius.com/itxrest/2/catalog/store/{store_id}"
                    f"/product/detail?physicalStoreId=null&productId={pid}&languageId=-39"
                )
                try:
                    r = await client.get(url, headers=headers)
                    ct = r.headers.get("content-type", "")
                    if "json" in ct:
                        try:
                            body = r.json()
                        except Exception:
                            body = {"raw": r.text[:100]}
                        status_mark = "✓" if r.status_code == 200 else f"✗({r.status_code})"
                        print(f"  store={store_id} pid={pid}: {status_mark} → {_fmt_json(body)}")
                        if r.status_code == 200:
                            print(f"\n  *** FOUND WORKING CONFIG: store={store_id} pid={pid} ***")
                            print(json.dumps(body, indent=2, ensure_ascii=False)[:2000])
                            return
                    else:
                        if r.status_code != 404:
                            print(f"  store={store_id} pid={pid}: {r.status_code} {ct[:30]}")
                except Exception as e:
                    print(f"  store={store_id} pid={pid}: ERROR {e}")


async def test_zara_storelist():
    """Fetch Zara's store list for Turkey to find the correct storeId."""
    print("\n══════════════════════════════════════════════════")
    print("TEST 3: Zara store list for Turkey (storeId discovery)")
    print("══════════════════════════════════════════════════")

    proxy_dict = _proxy_dict()
    headers = {
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
    }

    # Inditex store discovery endpoints
    urls = [
        "https://www.zara.com/itxrest/2/catalog/store/countries/languageId/-39",
        "https://www.zara.com/itxrest/2/catalog/store?countryCode=TR&languageId=-39",
        "https://www.zara.com/itxrest/3/store?countryCode=TR",
        "https://www.zara.com/tr/tr/api/catalog/v1/stores?countryCode=TR",
    ]

    async with httpx.AsyncClient(
        proxies=proxy_dict or None,
        verify=False,
        timeout=30,
        follow_redirects=True,
    ) as client:
        for url in urls:
            try:
                r = await client.get(url, headers=headers)
                ct = r.headers.get("content-type", "")
                print(f"\n{url[-60:]}")
                print(f"  Status: {r.status_code} | CT: {ct[:50]}")
                if "json" in ct:
                    try:
                        body = r.json()
                        print(f"  JSON: {_fmt_json(body)[:200]}")
                    except Exception:
                        print(f"  Body: {r.text[:200]}")
                else:
                    print(f"  Body: {r.text[:150]}")
            except Exception as e:
                print(f"  Error: {e}")


async def main():
    await test_zara_itxrest()
    await test_strad_itxrest()
    await test_zara_storelist()


if __name__ == "__main__":
    asyncio.run(main())
