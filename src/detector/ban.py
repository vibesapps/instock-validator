import re
from typing import Optional

# (compiled_pattern, signal_name)
_PATTERNS = [
    (re.compile(r'captcha|recaptcha|hcaptcha|px-captcha', re.I), 'captcha'),
    (re.compile(r'/_pxCaptcha|perimeterx|px-block|x-px-block', re.I), 'perimeterx'),
    (re.compile(r'akamai|bm_sz|ak-bmsc', re.I), 'akamai_challenge'),
    (re.compile(r'cf-ray|challenge-platform|cloudflare', re.I), 'cloudflare'),
    (re.compile(r'verify you are human|robot check|bot protection|are you a robot', re.I), 'bot_check'),
    (re.compile(r'access denied|403 forbidden', re.I), '403'),
    (re.compile(r'too many requests|rate.?limit', re.I), '429'),
    (re.compile(r'service unavailable|temporarily unavailable', re.I), '503'),
    (re.compile(r'_sec_cpt|security challenge|challenge required', re.I), 'challenge'),
]


def detect_ban_signal(
    *,
    status_code: Optional[int] = None,
    body: Optional[str] = None,
    url: Optional[str] = None,
    headers: Optional[dict] = None,
) -> Optional[str]:
    """Return the first detected ban signal, or None if request appears clean."""
    if status_code in (403, 429, 503):
        return str(status_code)

    if headers:
        header_str = str(headers).lower()
        if 'x-px-block' in header_str or '_pxhd' in header_str:
            return 'perimeterx'
        if 'cf-ray' in header_str:
            return 'cloudflare'

    if body:
        sample = body[:8000]  # scan first 8 KB — enough for bot protection pages
        for pattern, signal in _PATTERNS:
            if pattern.search(sample):
                return signal

    return None
