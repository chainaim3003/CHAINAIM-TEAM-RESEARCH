"""extract/youtube.py — free YouTube transcript extractor.

Contract (DESIGN/01-architecture-contract.md): an Extractor takes {url} and writes
raw content to kb/full/<key>.{txt,md,json}. NO LLM — this reuses the free, on-disk
youtube-transcript skill via subprocess (verified interface, this session):

    uv run <transcript_script> "<id_or_url>" [--timestamps]
      -> transcript to stdout (one line per caption segment, or "[MM:SS] text")
      -> "Error: ..." to stderr + exit 1 on failure

We pass the raw url/id straight through; the skill extracts the 11-char id itself.
All pacing/retry is delegated to Throttle (DESIGN/02-cost-model.md: throttle + dedupe).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

# import sibling module from scripts/ (orchestrate puts scripts/ on sys.path)
from throttle import Throttle  # type: ignore
from manifest import content_hash  # type: ignore


def build_cmd(transcript_script: str, source: str, *, timestamps: bool) -> List[str]:
    """Build the exact subprocess command for the youtube-transcript skill.

    Exposed as a function so tests can assert the command without running it.
    """
    script = str(Path(transcript_script).resolve())
    cmd = ["uv", "run", script, source]
    if timestamps:
        cmd.append("--timestamps")
    return cmd


def write_full(
    *,
    key: str,
    text: str,
    full_dir: Path,
    formats: List[str],
    kb_dir: Path,
) -> Dict[str, str]:
    """Write extracted transcript to kb/full/<key>.<fmt> for each requested format.

    Returns a {fmt: path} map for the manifest. Each path is stored RELATIVE to kb_dir
    (POSIX-style, e.g. "kb/full/<key>.txt") so the manifest is portable across machines
    and OSes: it sits beside manifest.json (which lives at kb_dir) and resolves the same
    way from any clone. If a target somehow lands outside kb_dir, its absolute POSIX path
    is stored as a fallback rather than crashing.

    'md' wraps the transcript in a minimal markdown stub; 'json' stores {key, text}. The
    transcript text itself is never modified (the skill's CRITICAL rule), only wrapped.
    """
    full_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, str] = {}
    for fmt in formats:
        target = full_dir / f"{key}.{fmt}"
        if fmt == "txt":
            target.write_text(text, encoding="utf-8")
        elif fmt == "md":
            target.write_text(f"# {key}\n\n```\n{text}\n```\n", encoding="utf-8")
        elif fmt == "json":
            target.write_text(json.dumps({"key": key, "text": text}, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            raise ValueError(f"unknown format '{fmt}' (expected txt|md|json)")
        try:
            paths[fmt] = target.relative_to(kb_dir).as_posix()
        except ValueError:
            paths[fmt] = target.as_posix()
    return paths


def extract(
    *,
    key: str,
    source: str,
    transcript_script: str,
    full_dir: Path,
    kb_dir: Path,
    formats: List[str],
    throttle: Throttle,
    timestamps: bool = False,
) -> Tuple[bool, Dict[str, str], str]:
    """Extract one video. Returns (ok, paths, info).

    ok=False -> info is the skill's stderr / error text; paths is empty.
    ok=True  -> paths is {fmt: file} (relative to kb_dir, see write_full), info is the
    content hash.
    """
    cmd = build_cmd(transcript_script, source, timestamps=timestamps)
    ok, output = throttle.run_with_retry(cmd)
    if not ok:
        return False, {}, output
    text = output.rstrip("\n")
    if not text.strip():
        return False, {}, "empty transcript (video may lack captions)"
    paths = write_full(key=key, text=text, full_dir=full_dir, formats=formats, kb_dir=kb_dir)
    return True, paths, content_hash(text)
