import logging
import random
from contextlib import asynccontextmanager
from typing import Optional, Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from ..proxy.manager import ProxyManager

log = logging.getLogger(__name__)

# Firefox user agents — different TLS fingerprint than Chrome, less flagged by Akamai
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
]

_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', {
    get: () => ['tr-TR', 'tr', 'en-US', 'en']
});
"""

# Block these resource types to reduce memory pressure on 2GB VM
_BLOCKED_RESOURCES = {"image", "media", "font"}


class BrowserManager:
    def __init__(self, proxy_manager: Optional[ProxyManager] = None) -> None:
        self._proxy = proxy_manager or ProxyManager()
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.firefox.launch(headless=True)
        log.info("Firefox browser started")

    async def stop(self) -> None:
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._pw:
            await self._pw.stop()
        log.info("Browser stopped")

    async def _restart(self) -> None:
        log.warning("Browser crash detected — restarting")
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        self._browser = await self._pw.firefox.launch(headless=True)
        log.info("Browser restarted")

    async def _open_context_and_page(self) -> Tuple[BrowserContext, Page]:
        ua = random.choice(_USER_AGENTS)
        vp = random.choice(_VIEWPORTS)
        proxy = self._proxy.next()

        ctx: BrowserContext = await self._browser.new_context(
            user_agent=ua,
            viewport=vp,
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            proxy=proxy,
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
            },
        )
        await ctx.add_init_script(_STEALTH_SCRIPT)

        page: Page = await ctx.new_page()

        # Block images/fonts to keep memory low on 2GB VM
        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in _BLOCKED_RESOURCES
            else route.continue_(),
        )

        await page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        })
        return ctx, page

    @asynccontextmanager
    async def new_page(self):
        """Yield a stealth-configured Page. Restarts browser once on crash."""
        ctx = None
        for attempt in range(2):
            try:
                ctx, page = await self._open_context_and_page()
                break
            except Exception as exc:
                if ctx:
                    try:
                        await ctx.close()
                    except Exception:
                        pass
                    ctx = None
                if attempt == 0 and any(w in str(exc).lower() for w in ("closed", "crash", "disconnect", "connect")):
                    await self._restart()
                    continue
                raise

        try:
            yield page
        finally:
            try:
                await ctx.close()
            except Exception:
                pass
