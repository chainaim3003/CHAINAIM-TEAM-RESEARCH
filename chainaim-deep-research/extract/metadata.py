"""extract/metadata.py — free metadata lookups for sources (V1: YouTube video title).

Why (DESIGN/07-build-plan.md, PR-2):
    The transcript skill (agent-skills/.../get_transcript.py) prints transcript text only — it
    does NOT return the video title (verified 2026-11-23). File names now use the title, so
    the title is fetched separately here.

Source: YouTube's public oEmbed endpoint
    https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=<id>&format=json
    -> JSON with "title" (and author_name, thumbnail_url, ...). No API key, no quota.

Behaviour:
    - Returns (title, None) on success, (None, "<reason>") on failure. NEVER invents a title;
      the caller falls back to the ID-only file name and prints a warning.
    - HTTP 4xx (private/removed/invalid video) is final: no retry.
    - Network errors, timeouts and HTTP 5xx are retried `retries` times with exponential
      backoff (backoff_s, 2*backoff_s, ...).
    - `http_get` is injectable so the offline eval suite can test every path without network.

No LLM. One small HTTPS GET per video.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional, Tuple

OEMBED_ENDPOINT = "https://www.youtube.com/oembed"
USER_AGENT = "chainaim-deep-research/0.1 (+https://github.com/chainaim3003/CHAINAIM-TEAM-RESEARCH)"

HttpGet = Callable[[str, float], bytes]


class HttpStatusError(Exception):
    """Raised by an http_get implementation for a non-2xx HTTP response."""

    def __init__(self, status: int, reason: str = "") -> None:
        super().__init__(f"HTTP {status} {reason}".strip())
        self.status = status


def default_http_get(url: str, timeout_s: float) -> bytes:
    """GET `url` with the standard library and return the body bytes.

    Raises:
        HttpStatusError: non-2xx response (status preserved for retry decisions).
        urllib.error.URLError / TimeoutError / OSError: network-level failures.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 (fixed https host)
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise HttpStatusError(exc.code, str(exc.reason)) from exc


def oembed_url(key: str) -> str:
    """Build the oEmbed request URL for a YouTube video ID."""
    watch = f"https://www.youtube.com/watch?v={key}"
    return f"{OEMBED_ENDPOINT}?{urllib.parse.urlencode({'url': watch, 'format': 'json'})}"


def fetch_youtube_title(
    key: str,
    *,
    timeout_s: float = 10.0,
    retries: int = 2,
    backoff_s: float = 1.0,
    http_get: HttpGet = default_http_get,
    sleep: Callable[[float], None] = time.sleep,
) -> Tuple[Optional[str], Optional[str]]:
    """Look up a YouTube video's title via oEmbed.

    Args:
        key:       11-char YouTube video ID.
        timeout_s: per-request timeout in seconds.
        retries:   extra attempts after the first, for network errors / HTTP 5xx only.
        backoff_s: first retry delay; doubles each retry.
        http_get:  injectable GET function (default: urllib). Used by offline evals.
        sleep:     injectable sleep (evals pass a no-op).

    Returns:
        (title, None) on success; (None, reason) on any failure.
    """
    url = oembed_url(key)
    last_err = "unknown error"
    for attempt in range(retries + 1):
        if attempt:
            sleep(backoff_s * (2 ** (attempt - 1)))
        try:
            body = http_get(url, timeout_s)
            data = json.loads(body.decode("utf-8"))
            title = data.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip(), None
            return None, "oEmbed response has no title"
        except HttpStatusError as exc:
            if 400 <= exc.status < 500:
                return None, f"oEmbed {exc} (video private, removed or invalid)"
            last_err = f"oEmbed {exc}"
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return None, f"oEmbed returned invalid JSON: {exc}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = f"network error: {exc}"
    return None, f"{last_err} (after {retries + 1} attempts)"
