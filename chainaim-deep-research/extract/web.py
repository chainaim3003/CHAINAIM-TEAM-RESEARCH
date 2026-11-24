"""extract/web.py — free, AI-free web article -> text extractor (PR-7).

Why (DESIGN/07-build-plan.md; decision 2026-11-23: the agent stays AI-free):
    Any other web link (blog post, article, documentation page) becomes
    kb/full/<Article title> [web-<hash>].md with title, site, author, date, URL and the page's
    MAIN TEXT as Markdown (menus, ads, footers removed), plus a ready-to-paste article prompt.

Engine: trafilatura (https://trafilatura.readthedocs.io): `fetch_url` downloads the page,
`bare_extraction(..., with_metadata=True).as_dict()` gives title/author/date/sitename, and
`extract(..., output_format="markdown")` gives the main text. Verified against trafilatura 2.4.0.

Limits (reported, never hidden): pages that need JavaScript, logins or paywalls usually yield
little or no text — those fail with a clear reason instead of saving an empty file. Output is
capped at `max_chars` (stated in the file).

`fetch` and `extract_fn` are injectable for the offline eval suite.
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple

_TRACKING = re.compile(r"^(utm_[a-z]+|fbclid|gclid|mc_cid|mc_eid|ref|ref_src)$", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)


class WebError(Exception):
    pass


def import_trafilatura():
    """Import trafilatura without the harmless urllib3 'SOCKS support ... PySocks' warning
    (printed when a SOCKS proxy setting is present; downloads still work without PySocks)."""
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r".*SOCKS support in urllib3.*")
        import trafilatura
    return trafilatura


def first_url(line: str) -> Optional[str]:
    m = URL_RE.search(line)
    return m.group(0).rstrip(".,;") if m else None


def normalize_url(url: str) -> str:
    """Drop #fragments and tracking parameters so the same article dedupes to one key."""
    p = urllib.parse.urlsplit(url.strip())
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not _TRACKING.match(k)]
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/",
                                    urllib.parse.urlencode(q), ""))


def web_key(url: str) -> str:
    """Stable short id for a normalized URL: 'web:' + first 10 hex chars of its SHA-256."""
    return "web:" + hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:10]


def default_fetch(url: str) -> Optional[str]:
    return import_trafilatura().fetch_url(url)


def default_extract(html: str, url: str) -> Tuple[Dict[str, str], str]:
    """Return (metadata dict, markdown main text) using trafilatura."""
    trafilatura = import_trafilatura()
    doc = trafilatura.bare_extraction(html, url=url, with_metadata=True)
    meta = doc.as_dict() if doc is not None else {}
    md = trafilatura.extract(html, url=url, output_format="markdown", include_tables=True,
                             with_metadata=False) or ""
    return {k: str(meta.get(k) or "") for k in ("title", "author", "date", "sitename", "hostname")}, md


def extract_article(
    url: str,
    *,
    min_chars: int = 300,
    max_chars: int = 300_000,
    fetch: Callable[[str], Optional[str]] = default_fetch,
    extract_fn: Callable[[str, str], Tuple[Dict[str, str], str]] = default_extract,
) -> Tuple[str, Dict[str, str]]:
    """Download one page and render Markdown. Returns (markdown, meta{title}). Raises WebError."""
    html = fetch(url)
    if not html:
        raise WebError(f"could not download {url} (blocked, offline, or not an HTML page)")
    meta, text = extract_fn(html, url)
    text = (text or "").strip()
    if len(text) < min_chars:
        raise WebError(f"only {len(text)} characters of main text found at {url} "
                       f"(page may need JavaScript, a login, or be paywalled)")
    notes = []
    if len(text) > max_chars:
        notes.append(f"main text cut at {max_chars:,} characters (of {len(text):,})")
        text = text[:max_chars]
    title = meta.get("title") or meta.get("hostname") or url
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [
        f"# {title}",
        "",
        f"- URL: {url}",
        f"- Site: {meta.get('sitename') or meta.get('hostname') or 'n/a'} · Author: {meta.get('author') or 'n/a'} · "
        f"Date: {meta.get('date') or 'n/a'}",
        f"- Extracted: {fetched} by chainaim-deep-research (no AI; main text via trafilatura)",
        "",
        "## Main text",
        "",
        text,
        "",
    ]
    if notes:
        out += ["## Notes", "", *[f"- {n}" for n in notes], ""]
    return "\n".join(out), {"title": title}
