"""naming.py — safe, readable file names for KB entries: "<Title> [<key>]".

Why (DESIGN/07-build-plan.md, PR-2):
    Files used to be named by the bare video ID (e.g. "8D8ewFBJfFM.txt"), which is unreadable.
    PR-2 names them by title while keeping the ID, e.g.
        "Building Multi-Agent Systems [8D8ewFBJfFM].txt"   (transcript, kb/full/)
        "Building Multi-Agent Systems [8D8ewFBJfFM].md"    (summary, kb/highlights/, PR-5)
    The same stem is used for both so a transcript and its summary always match.

Rules applied by safe_stem() (Windows is the strictest target, so its rules apply everywhere):
    - Unicode normalised to NFC; control characters removed.
    - Characters Windows forbids in file names  < > : " / \\ | ? *  are replaced by a space.
    - Runs of whitespace collapse to one space; leading/trailing spaces and dots are stripped
      (Windows silently drops trailing dots/spaces, which would break round-trips).
    - The title part is shortened so the whole stem fits `max_len` characters. The default
      (100) keeps full paths under Windows' classic 260-character limit for this repo's
      folder depth (~115 chars to kb/full/ + 100 + extension).
    - " [<key>]" is ALWAYS appended, so two videos with the same title never collide and the
      key is recoverable from the file name.
    - Empty / missing / all-invalid title -> the stem is just "<key>" (the pre-PR-2 name).
    - Defensive: a stem equal to a Windows reserved device name (CON, NUL, COM1, ...) gets a
      leading "_" (cannot happen with the key suffix, but guards future callers).

No network. No LLM. Pure function, fully covered by the `naming` eval suite.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

DEFAULT_MAX_LEN = 100

_FORBIDDEN = re.compile(r'[<>:"/\\|?*]')
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SPACES = re.compile(r"\s+")
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def clean_title(title: Optional[str]) -> str:
    """Return the title cleaned for use in a file name ('' if nothing usable remains)."""
    if not title:
        return ""
    t = unicodedata.normalize("NFC", title)
    t = _CONTROL.sub("", t)
    t = _FORBIDDEN.sub(" ", t)
    t = _SPACES.sub(" ", t)
    return t.strip(" .")


def safe_stem(title: Optional[str], key: str, *, max_len: int = DEFAULT_MAX_LEN) -> str:
    """Build the file stem "<clean title> [<key>]" (or "<key>" when there is no usable title).

    Args:
        title:   raw title (may be None/empty/contain forbidden characters).
        key:     source key, e.g. the 11-char YouTube ID. Must already be file-name safe.
        max_len: maximum length of the returned stem, in characters. Must leave room for
                 at least one title character plus " [<key>]".

    Returns:
        A stem without extension, safe on Windows, macOS and Linux.

    Raises:
        ValueError: if max_len is too small to hold " [<key>]" plus one character.
    """
    suffix = f" [{key}]"
    if max_len < len(suffix) + 1:
        raise ValueError(f"max_len={max_len} too small for key suffix {suffix!r}")
    t = clean_title(title)
    if not t:
        stem = key
    else:
        room = max_len - len(suffix)
        if len(t) > room:
            # Cut at the limit, then strip so the title never ends in a space or dot.
            t = t[:room].rstrip(" .")
        stem = f"{t}{suffix}" if t else key
    if stem.upper() in _RESERVED:
        stem = f"_{stem}"
    return stem
