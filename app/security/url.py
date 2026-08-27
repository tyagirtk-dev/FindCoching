from __future__ import annotations

from urllib.parse import urlparse

from flask import request


def safe_next_url(target: str | None, fallback: str = "/") -> str:
    """
    Return a local relative URL only.

    Prevents open redirects such as:
        https://evil.example/
        //evil.example/
        javascript:...
    """
    if not target:
        return fallback

    target = target.strip()

    if not target:
        return fallback

    parsed = urlparse(target)

    # Reject absolute URLs.
    if parsed.scheme or parsed.netloc:
        return fallback

    # Reject protocol-relative URLs.
    if target.startswith("//"):
        return fallback

    # Only allow application-local paths.
    if not target.startswith("/"):
        return fallback

    # Reject control characters.
    if any(ord(ch) < 32 for ch in target):
        return fallback

    return target


def request_next_url(fallback: str = "/") -> str:
    return safe_next_url(request.args.get("next"), fallback)
