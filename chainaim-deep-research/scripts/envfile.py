"""envfile.py — load KEY=VALUE pairs from the repo-root .env into os.environ (no dependency).

Why (PR-5): GITHUB_TOKEN lives in .env (git-ignored, see .env.example). This loader:
    - reads <repo root>/.env only if it exists,
    - ignores blank lines and '#' comments, strips optional quotes around values,
    - NEVER overrides a variable already set in the environment,
    - never prints values.
Empty values (e.g. "GITHUB_TOKEN=") are skipped, so an untouched copy of .env.example has no effect.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List


def load_env_file(path: Path) -> List[str]:
    """Load variables from `path`. Returns the NAMES that were set (never values)."""
    if not path.exists():
        return []
    set_names: List[str] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not name or not value or name in os.environ:
            continue
        os.environ[name] = value
        set_names.append(name)
    return set_names
