"""extract/arxiv.py — free, AI-free arXiv paper -> text extractor (PR-7).

Why (DESIGN/07-build-plan.md; decision 2026-11-23: the agent stays AI-free):
    An arXiv link becomes kb/full/<Paper title> [arxiv-<id>].md with the paper's metadata
    (title, authors, dates, categories, links), abstract and FULL TEXT, plus (via build_kb_pack)
    a ready-to-paste paper prompt for any AI.

Sources (all free, no key):
    - Metadata: arXiv export API  https://export.arxiv.org/api/query?id_list=<id>  (Atom XML).
      arXiv's API terms ask for at most one request every 3 seconds on one connection; every
      request made here (API, HTML, PDF) is paced by `min_delay_s` (default 3.0).
    - Full text, in order:
        1. arXiv's HTML version  https://arxiv.org/html/<id>  -> main text via trafilatura (Markdown)
        2. the PDF               https://arxiv.org/pdf/<id>   -> text via pypdf
      The file states which one was used. If neither yields text, the abstract is still saved and
      the file says the full text could not be extracted — nothing is invented.
    - Output is capped at `max_chars` (default 400,000); the cut is stated in the file.

Network functions are injectable (`http_get`, `html_to_markdown`, `pdf_to_text`, `sleep`) so the
offline eval suite can test parsing and the HTML->PDF fallback without network.
"""

from __future__ import annotations

import io
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

USER_AGENT = "chainaim-deep-research/0.1 (+https://github.com/chainaim3003/CHAINAIM-TEAM-RESEARCH)"
API = "https://export.arxiv.org/api/query?id_list="
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# New-style ids (2007+): 2401.12345 / 1706.03762v7 ; old-style: hep-th/9901001, math.GT/0309136
NEW_ID = r"\d{4}\.\d{4,5}"
OLD_ID = r"[a-z][a-z\-]*(?:\.[A-Z]{2})?/\d{7}"
ID_RE = re.compile(rf"({NEW_ID}|{OLD_ID})(v\d+)?")


class ArxivError(Exception):
    pass


HttpGet = Callable[[str, float], Tuple[int, bytes]]


def default_http_get(url: str, timeout_s: float) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 (fixed arxiv hosts)
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def default_html_to_markdown(html: str, url: str) -> str:
    from extract.web import import_trafilatura  # lazy + quiet (no SOCKS warning)
    return import_trafilatura().extract(html, url=url, output_format="markdown", include_tables=True,
                               with_metadata=False) or ""


def default_pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader  # lazy
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


def file_id(arxiv_id: str) -> str:
    """File-name-safe form of an id ('hep-th/9901001' -> 'hep-th_9901001')."""
    return arxiv_id.replace("/", "_")


@dataclass
class ArxivClient:
    timeout_s: float = 30.0
    min_delay_s: float = 3.0
    http_get: HttpGet = default_http_get
    sleep: Callable[[float], None] = time.sleep
    calls: int = 0
    _last: float = field(default=0.0, repr=False)

    def get(self, url: str) -> Tuple[int, bytes]:
        if self.calls and self.min_delay_s > 0:
            self.sleep(self.min_delay_s)  # arXiv API terms: <= 1 request / 3 s
        self.calls += 1
        try:
            return self.http_get(url, self.timeout_s)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ArxivError(f"network error calling arXiv: {exc}") from exc


def parse_atom(xml_bytes: bytes) -> Dict[str, object]:
    """Parse one entry from the export API Atom feed. Raises ArxivError if there is none."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ArxivError(f"arXiv API returned invalid XML: {exc}") from exc
    entry = root.find(f"{ATOM}entry")
    if entry is None or entry.find(f"{ATOM}title") is None:
        raise ArxivError("arXiv API: paper not found")
    def txt(tag: str) -> str:
        el = entry.find(tag)
        return " ".join((el.text or "").split()) if el is not None else ""
    if txt(f"{ATOM}title").lower() == "error":
        raise ArxivError(f"arXiv API error: {txt(f'{ATOM}summary')}")
    cats = [c.get("term", "") for c in entry.findall(f"{ATOM}category")]
    prim = entry.find(f"{ARXIV_NS}primary_category")
    return {
        "title": txt(f"{ATOM}title"),
        "abstract": txt(f"{ATOM}summary"),
        "authors": [" ".join((a.findtext(f"{ATOM}name") or "").split()) for a in entry.findall(f"{ATOM}author")],
        "published": txt(f"{ATOM}published")[:10],
        "updated": txt(f"{ATOM}updated")[:10],
        "versioned_id": txt(f"{ATOM}id").rsplit("/abs/", 1)[-1],
        "primary_category": prim.get("term", "") if prim is not None else (cats[0] if cats else ""),
        "categories": [c for c in cats if c],
    }


def extract_paper(
    client: ArxivClient,
    arxiv_id: str,
    *,
    max_chars: int = 400_000,
    min_fulltext_chars: int = 2_000,
    html_to_markdown: Callable[[str, str], str] = default_html_to_markdown,
    pdf_to_text: Callable[[bytes], str] = default_pdf_to_text,
) -> Tuple[str, Dict[str, str]]:
    """Fetch metadata + full text for one arXiv id and render Markdown.

    Returns (markdown, meta) with meta: title, versioned_id, fulltext_source ("html"|"pdf"|"none").
    Raises ArxivError when the paper itself cannot be found.
    """
    st, body = client.get(API + arxiv_id)
    if st != 200:
        raise ArxivError(f"arXiv API HTTP {st} for {arxiv_id}")
    meta = parse_atom(body)

    notes: List[str] = []
    text, source = "", "none"
    html_url = f"https://arxiv.org/html/{arxiv_id}"
    st, body = client.get(html_url)
    if st == 200:
        text = html_to_markdown(body.decode("utf-8", errors="replace"), html_url).strip()
        if len(text) >= min_fulltext_chars:
            source = "html"
        else:
            notes.append(f"HTML version gave only {len(text)} characters; trying the PDF")
            text = ""
    else:
        notes.append(f"no HTML version (HTTP {st}); using the PDF")
    if not text:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        st, body = client.get(pdf_url)
        if st == 200 and body:
            try:
                text = pdf_to_text(body).strip()
            except Exception as exc:  # noqa: BLE001 — any PDF parsing failure is reported, not fatal
                notes.append(f"PDF text extraction failed: {exc}")
                text = ""
            if text:
                source = "pdf"
                notes.append("text extracted from the PDF: layout, formulas and tables may be garbled")
        else:
            notes.append(f"PDF could not be downloaded (HTTP {st})")
    if not text:
        notes.append("FULL TEXT NOT EXTRACTED — only metadata and abstract are included")
    if len(text) > max_chars:
        notes.append(f"full text cut at {max_chars:,} characters (of {len(text):,})")
        text = text[:max_chars]

    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    authors = ", ".join(meta["authors"]) or "(unknown)"  # type: ignore[arg-type]
    out = [
        f"# {meta['title']}",
        "",
        f"- arXiv: {meta['versioned_id']} · Primary category: {meta['primary_category']} · "
        f"All: {', '.join(meta['categories'])}",  # type: ignore[arg-type]
        f"- Authors: {authors}",
        f"- Published: {meta['published']} · Updated: {meta['updated']}",
        f"- Links: https://arxiv.org/abs/{arxiv_id} · https://arxiv.org/pdf/{arxiv_id}",
        f"- Full text source: {source} · Extracted: {fetched} by chainaim-deep-research (no AI)",
        "",
        "## Abstract",
        "",
        str(meta["abstract"]) or "(none)",
        "",
        "## Full text",
        "",
        text or "(not available — see notes)",
        "",
    ]
    if notes:
        out += ["## Notes", "", *[f"- {n}" for n in notes], ""]
    return "\n".join(out), {"title": str(meta["title"]), "versioned_id": str(meta["versioned_id"]),
                            "fulltext_source": source}
