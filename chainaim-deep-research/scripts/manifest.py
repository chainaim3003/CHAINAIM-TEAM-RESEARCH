"""manifest.py — dedupe ledger.

Implements the contract interface (DESIGN/01-architecture-contract.md section 4):
    manifest.seen(key) -> bool
    manifest.record(key, url, hash, paths, status, *, source_line=None)

The manifest is a JSON object keyed by source key (e.g. the 11-char YouTube id).
It is the durable record of what has already been extracted, so re-runs are
idempotent: the dedupe gate skips any key whose status is already "extracted".

No LLM. No network. Pure local state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def content_hash(text: str) -> str:
    """Return a short, stable content hash: 'sha256-' + first 16 hex chars.

    Used to detect that a source's *content* changed even if its key didn't.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256-{digest[:16]}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Manifest:
    """Durable dedupe ledger backed by a JSON file.

    Args:
        path: absolute path to manifest.json.
        autosave: if True (default), every record() writes to disk immediately.
                  Set False to batch writes and call save() once.
    """

    def __init__(self, path: str | Path, *, autosave: bool = True) -> None:
        self.path = Path(path)
        self.autosave = autosave
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise RuntimeError(
                    f"manifest at {self.path} exists but is unreadable: {exc}. "
                    f"Refusing to overwrite — inspect/repair it manually."
                ) from exc
        else:
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # atomic-ish write: temp file then replace, so a crash mid-write can't
        # corrupt the existing manifest.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def seen(self, key: str) -> bool:
        """True iff key is already recorded with status 'extracted'."""
        entry = self._data.get(key)
        return bool(entry and entry.get("status") == "extracted")

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._data.get(key)

    def record(
        self,
        key: str,
        url: str,
        content_hash_value: str,
        paths: Dict[str, str],
        status: str = "extracted",
        *,
        source_line: Optional[str] = None,
    ) -> None:
        """Record (or update) a manifest entry. Matches the contract schema.

        Args:
            key: source key (e.g. the 11-char YouTube id).
            url: CANONICAL source URL (e.g. https://www.youtube.com/watch?v=<id>). Callers
                must pass a clean URL here, not the raw input line (PR-1 fix: earlier runs
                stored whole input-table rows such as "| 96 | 6/22/26 | ... |").
            content_hash_value: content hash of the extracted text (see content_hash()).
            paths: {fmt: path relative to kb_dir} written by the extractor.
            status: entry status; "extracted" is what the dedupe gate checks.
            source_line: OPTIONAL original input line, kept verbatim as an audit trail of
                where the source came from (notes, table rows). Omitted from the entry when
                None, so entries written before PR-1 and after it share one schema.
        """
        entry: Dict[str, Any] = {
            "source_url": url,
            "content_hash": content_hash_value,
            "full_paths": paths,
            "status": status,
            "ts": utc_now_iso(),
        }
        if source_line is not None:
            entry["source_line"] = source_line
        self._data[key] = entry
        if self.autosave:
            self.save()

    def raw(self) -> Dict[str, Dict[str, Any]]:
        """Return the underlying {key: entry} dict (read access for tools such as
        migrate_manifest.py). Mutating it does not persist anything until save()."""
        return self._data

    def __len__(self) -> int:
        return len(self._data)
