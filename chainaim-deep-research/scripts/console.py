"""scripts/console.py - make console output safe on every Windows PC (PR-13).

When a script's output goes to a pipe (scheduled task, VS Code task, the app, setup), Python writes it
in the PC's code page (often cp1252). Titles with emoji or other characters outside that code page then
crash with UnicodeEncodeError. Call utf8_console() first thing in every entry point.
"""

from __future__ import annotations

import sys


def utf8_console() -> None:
    """Switch stdout/stderr to UTF-8 (unencodable characters are replaced, never fatal)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass  # not a text stream (e.g. replaced by a test harness) - leave as is
