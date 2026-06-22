"""ingest/local_dir.py — V1 ingest adapter for the local / GitHub input-dir channel.

Contract (DESIGN/01-architecture-contract.md section 2): an ingest adapter takes a
channel handle and emits normalized items. Here the "channel" is a checked-out
directory / list file on disk (the V1 "local / GitHub input dir" source).

This adapter does NO classification — it only reads raw source lines. The Router/
classify step (in orchestrate.py) assigns kind + key + skill. Keeping ingest
classification-free is what lets new channels (Drive, Telegram) reuse the same spine.

No LLM. No network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


def _read_lines(path: Path) -> List[str]:
    """Read a source file: one source per line; '#' comments and blanks ignored."""
    out: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def collect_sources(
    *,
    source_list: Optional[str],
    source_dir: Optional[str],
    base_dir: Path,
    list_glob: str = "*.txt",
    md_glob: str = "*.md",
) -> List[Dict[str, str]]:
    """Collect raw source items from a list file and/or a scanned directory.

    Args (flags — Rule 8):
        source_list: path to a newline-delimited list file (relative to base_dir or absolute).
        source_dir:  directory scanned for list_glob + md_glob files (or None to skip).
        base_dir:    directory that relative paths resolve against (the package dir).
        list_glob:   filename pattern for plain list files in source_dir.
        md_glob:     filename pattern for markdown list files in source_dir.

    Returns: list of items {"url": <raw line>, "raw": <raw line>, "origin": <file>},
             de-duplicated within this run (order preserved). kind/key are added later
             by the Router.
    """
    items: List[Dict[str, str]] = []
    seen_in_run: set[str] = set()

    def _add(line: str, origin: str) -> None:
        if line in seen_in_run:
            return
        seen_in_run.add(line)
        items.append({"url": line, "raw": line, "origin": origin})

    if source_list:
        lp = Path(source_list)
        if not lp.is_absolute():
            lp = base_dir / lp
        if lp.exists():
            for line in _read_lines(lp):
                _add(line, str(lp))

    if source_dir:
        dp = Path(source_dir)
        if not dp.is_absolute():
            dp = base_dir / dp
        if dp.exists():
            for pattern in (list_glob, md_glob):
                for f in sorted(dp.glob(pattern)):
                    for line in _read_lines(f):
                        _add(line, str(f))

    return items
