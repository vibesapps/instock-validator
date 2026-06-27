import logging
import os
import random
import string
from typing import Optional
from urllib.parse import urlparse

log = logging.getLogger(__name__)


def _make_sticky(proxy_url: str) -> str:
    """Inject a random session ID into a BrightData proxy URL to pin the exit IP.

    Akamai's bm-verify token is bound to the originating IP. Without sticky
    sessions, BrightData assigns a new IP per TCP connection, so the meta-refresh
    round-trip comes from a different IP and the token is rejected → infinite loop.
    """
    parsed = urlparse(proxy_url)
    if not parsed.username or "session-" in parsed.username:
        return proxy_url
    session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    new_user = f"{parsed.username}-session-{session_id}"
    return f"{parsed.scheme}://{new_user}:{parsed.password}@{parsed.hostname}:{parsed.port}"


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

    def next_raw(self) -> Optional[str]:
        """Return next raw proxy URL string (no sticky session applied)."""
        available = [p for p in self._proxies if p not in self._banned]
        if not available:
            return None
        url = available[self._index % len(available)]
        self._index += 1
        return url

    def next(self) -> Optional[dict]:
        """Return next proxy config dict for Playwright, or None for direct."""
        available = [p for p in self._proxies if p not in self._banned]
        if not available:
            return None
        proxy_url = available[self._index % len(available)]
        self._index += 1

        # Pin each browser context to one exit IP so Akamai challenge round-trips work
        proxy_url = _make_sticky(proxy_url)

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
