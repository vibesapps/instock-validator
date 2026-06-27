import logging
import os
from typing import Optional
from urllib.parse import urlparse

log = logging.getLogger(__name__)


class ProxyManager:
    """
    Proxy abstraction layer. Currently no-op (returns None = direct connection).
    To activate: set PROXY_LIST env var to comma-separated proxy URLs.
      e.g. PROXY_LIST=http://user:pass@host1:8080,http://user:pass@host2:8080

    When residential proxies are needed, populate PROXY_LIST and redeploy.
    No code changes required — the scraper calls next() without knowing whether
    a proxy is active.
    """

    def __init__(self) -> None:
        raw = os.getenv("PROXY_LIST", "")
        self._proxies: list[str] = [p.strip() for p in raw.split(",") if p.strip()]
        self._banned: set[str] = set()
        self._index = 0
        if self._proxies:
            log.info("ProxyManager: %d proxy(ies) loaded", len(self._proxies))
        else:
            log.info("ProxyManager: no proxies configured — using direct connection")

    @property
    def active(self) -> bool:
        return bool(self._proxies)

    def next(self) -> Optional[dict]:
        """Return next proxy config dict for Playwright, or None for direct."""
        available = [p for p in self._proxies if p not in self._banned]
        if not available:
            return None
        proxy_url = available[self._index % len(available)]
        self._index += 1

        parsed = urlparse(proxy_url)
        config: dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username:
            config["username"] = parsed.username
        if parsed.password:
            config["password"] = parsed.password
        return config

    def mark_banned(self, proxy_url: str) -> None:
        log.warning("Proxy banned, removing: %s", proxy_url)
        self._banned.add(proxy_url)
