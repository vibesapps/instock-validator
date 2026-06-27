import logging
import random
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from ..proxy.manager import ProxyManager

log = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
]

# Injected into every page context before any script runs.
# Removes the most common headless browser fingerprints detected by Akamai/PerimeterX.
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', {
    get: () => { const arr = [1,2,3,4,5]; arr.item = () => null; return arr; }
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['tr-TR', 'tr', 'en-US', 'en']
});
window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
const _originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) =>
    params.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _originalQuery(params);
"""


class BrowserManager:
    def __init__(self, proxy_manager: Optional[ProxyManager] = None) -> None:
        self._proxy = proxy_manager or ProxyManager()
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-extensions",
                # Low-memory optimizations for 1 GB RAM instances
                "--disable-gpu",
                "--no-zygote",
                "--js-flags=--max-old-space-size=256",
            ],
        )
        log.info("Chromium browser started")

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        log.info("Browser stopped")

    async def _ensure_alive(self) -> None:
        if self._browser and self._browser.is_connected():
            return
        log.warning("Browser disconnected — restarting")
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        self._browser = await self._pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-extensions",
                "--disable-gpu",
                "--no-zygote",
                "--js-flags=--max-old-space-size=256",
            ],
        )
        log.info("Browser restarted")

    @asynccontextmanager
    async def new_page(self):
        """Yield a stealth-configured Page with randomised UA/viewport/proxy."""
        ua = random.choice(_USER_AGENTS)
        vp = random.choice(_VIEWPORTS)
        proxy = self._proxy.next()

        await self._ensure_alive()
        ctx: BrowserContext = await self._browser.new_context(
            user_agent=ua,
            viewport=vp,
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            proxy=proxy,
            extra_http_headers={
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
            },
        )
        await ctx.add_init_script(_STEALTH_SCRIPT)

        page: Page = await ctx.new_page()
        await page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })

        try:
            yield page
        finally:
            await ctx.close()
