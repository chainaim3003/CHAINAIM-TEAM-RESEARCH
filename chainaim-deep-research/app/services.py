"""app/services.py — all logic behind the local app (PR-9). No Streamlit, no AI, fully testable.

The Streamlit page (app/streamlit_app.py) is a thin UI over these functions, which only read and
write the same files the command-line tools use (manifest.json, links.txt, kb/full, kb/prompts,
kb/highlights, kb/digests, logs/). Extraction itself is done by running the existing, tested
scripts (orchestrate.py, build_kb_pack.py, digest.py) as subprocesses, so the app and the
scheduled tasks behave identically and share one run lock (pipeline.lock at the repo root).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

PKG = Path(__file__).resolve().parent.parent          # .../chainaim-deep-research
REPO = PKG.parent                                     # .../CHAINAIM-TEAM-RESEARCH
sys.path.insert(0, str(PKG / "scripts"))
sys.path.insert(0, str(PKG))

from build_kb_pack import _COMMAND_START, DEFAULT_MIN_SUMMARY_CHARS, summary_status  # noqa: E402
from orchestrate import classify, load_config, resolve_paths         # noqa: E402

KIND_LABEL = {"github_repo": "GitHub", "arxiv_paper": "arXiv", "web_article": "Web"}
LOCK = REPO / "pipeline.lock"
LOG_DIR = REPO / "logs"


@dataclass
class Entry:
    key: str
    kind: str          # YouTube / GitHub / arXiv / Web
    title: str
    url: str
    added: str         # YYYY-MM-DD
    stem: str
    full: Optional[Path]
    prompt: Path
    summary: Path
    status: str        # ok / check / missing


def kb_paths(kb_dir: Optional[str] = None) -> Dict[str, Path]:
    """Resolve kb_dir/manifest/full dirs from config.yaml (kb_dir overrides output.kb_dir)."""
    cfg = load_config(PKG / "config.yaml")
    p = resolve_paths(cfg, kb_dir)
    out = cfg.get("output", {})
    p["prompts_dir"] = p["kb_dir"] / out.get("prompts_dir", "kb/prompts")
    p["highlights_dir"] = p["kb_dir"] / out.get("highlights_dir", "kb/highlights")
    p["digests_dir"] = p["kb_dir"] / "kb" / "digests"
    p["min_summary_chars"] = int(out.get("min_summary_chars", DEFAULT_MIN_SUMMARY_CHARS))  # type: ignore[assignment]
    return p


def list_entries(paths: Dict[str, Path]) -> List[Entry]:
    """All extracted items in the KB, newest first."""
    mf = paths["manifest"]
    if not mf.exists():
        return []
    data = json.loads(mf.read_text(encoding="utf-8"))
    rows: List[Entry] = []
    for key, e in data.items():
        if e.get("status") != "extracted":
            continue
        fp = e.get("full_paths") or {}
        rel = fp.get("txt") or fp.get("md") or next(iter(fp.values()), None)
        full = paths["kb_dir"] / rel if rel else None
        stem = e.get("stem") or (Path(rel).stem if rel else key)
        summary = paths["highlights_dir"] / f"{stem}.md"
        rows.append(Entry(
            key=key, kind=KIND_LABEL.get(e.get("kind") or "", "YouTube"),
            title=e.get("title") or stem, url=e.get("source_url", ""), added=(e.get("ts") or "")[:10],
            stem=stem, full=full if full and full.exists() else None,
            prompt=paths["prompts_dir"] / f"{stem}.prompt.md", summary=summary,
            status=summary_status(summary, min_chars=int(paths["min_summary_chars"])),  # type: ignore[arg-type]
        ))
    rows.sort(key=lambda r: (r.added, r.title.lower()), reverse=True)
    return rows


def parse_links(text: str) -> Tuple[List[str], List[str]]:
    """Split pasted text into (recognised links, rejected lines). One link per line or space-separated."""
    good, bad = [], []
    for token in text.replace(",", " ").split():
        kind, key = classify(token)
        (good if kind != "unknown" and key else bad).append(token)
    return good, bad


def add_links(list_file: Path, links: List[str]) -> Tuple[List[str], List[str]]:
    """Append links not already in list_file. Returns (added, already_present)."""
    list_file.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if list_file.exists():
        existing = {ln.strip() for ln in list_file.read_text(encoding="utf-8-sig").splitlines()}
    added, present = [], []
    with list_file.open("a", encoding="utf-8") as fh:
        for l in links:
            if l in existing:
                present.append(l)
            else:
                fh.write(l + "\n")
                existing.add(l)
                added.append(l)
    return added, present


def summary_status_text(text: str, min_chars: int) -> str:
    """Same rule as build_kb_pack.summary_status, for text that is not saved yet."""
    t = text.strip()
    first = next((ln.strip() for ln in t.splitlines() if ln.strip()), "")
    if not t:
        return "missing"
    if len(t) < min_chars or first.startswith(_COMMAND_START):
        return "check"
    return "ok"


def save_summary(entry: Entry, text: str, *, min_chars: int, force: bool = False) -> Tuple[bool, str]:
    """Write the AI's answer to kb/highlights/<stem>.md. Refuses empty text; refuses short or
    command-like text unless force=True. Returns (saved, message)."""
    st = summary_status_text(text, min_chars)
    if st == "missing":
        return False, "Nothing to save - paste the AI's answer first."
    if st == "check" and not force:
        return False, (f"This looks too short (< {min_chars} chars) or like a pasted command. "
                       f"Tick 'save anyway' if it really is the summary.")
    entry.summary.parent.mkdir(parents=True, exist_ok=True)
    entry.summary.write_text(text.strip() + "\n", encoding="utf-8")
    return True, f"Saved: {entry.summary}"


def read_text(path: Optional[Path], limit: Optional[int] = None) -> str:
    if not path or not path.exists():
        return ""
    t = path.read_text(encoding="utf-8", errors="replace")
    return t if limit is None else t[:limit]


def latest_digest(paths: Dict[str, Path]) -> Optional[Path]:
    d = paths["digests_dir"]
    files = sorted(d.glob("*.md")) if d.exists() else []
    return files[-1] if files else None


def recent_logs(n: int = 10) -> List[Path]:
    files = sorted(LOG_DIR.glob("*.log")) if LOG_DIR.exists() else []
    return list(reversed(files[-n:]))


# ---------------- run lock (shared with ops/*.ps1) ----------------
def pid_alive(pid: int) -> bool:
    """True if a process with this PID exists. Safe on Windows (never sends a signal there)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def lock_holder(lock: Path = LOCK) -> Optional[int]:
    """PID holding the run lock, or None (missing or stale lock)."""
    if not lock.exists():
        return None
    try:
        pid = int(lock.read_text(encoding="ascii", errors="ignore").strip().splitlines()[0])
    except (ValueError, IndexError):
        return None
    return pid if pid_alive(pid) else None


def acquire_lock(lock: Path = LOCK) -> bool:
    if lock_holder(lock) is not None:
        return False
    lock.write_text(str(os.getpid()), encoding="ascii")
    return True


def release_lock(lock: Path = LOCK) -> None:
    try:
        if lock.exists() and lock.read_text(encoding="ascii").strip() == str(os.getpid()):
            lock.unlink()
    except OSError:
        pass


def run_script(args: List[str], *, log_name: str = "app") -> Iterator[str]:
    """Run one package script with this Python (same environment as the app), yielding output
    lines live and appending them to logs/<date>-<log_name>.log. Final line: 'EXIT <code>'."""
    from datetime import datetime
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}-{log_name}.log"
    cmd = [sys.executable, *args]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"RUN {' '.join(cmd)}\n")
        proc = subprocess.Popen(cmd, cwd=str(PKG), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", env=env)
        assert proc.stdout is not None
        for line in proc.stdout:
            fh.write(line)
            yield line.rstrip("\n")
        code = proc.wait()
        fh.write(f"EXIT {code}\n")
    yield f"EXIT {code}"


def digest_args(kb_dir: Path, days: int = 7) -> List[str]:
    """The command the app runs for 'Make digest now' (same as ops/run_weekly.ps1)."""
    return ["scripts/digest.py", "--config", "config.yaml", "--kb-dir", str(kb_dir), "--days", str(days)]


def extraction_args(kb_dir: Path, list_file: Path) -> List[List[str]]:
    """The two commands the app runs for 'Extract now' (same as ops/add_link.ps1)."""
    no_dir = str(kb_dir / "no-such-dir")
    return [
        ["scripts/orchestrate.py", "--config", "config.yaml", "--kb-dir", str(kb_dir),
         "--source-list", str(list_file), "--source-dir", no_dir],
        ["scripts/build_kb_pack.py", "--config", "config.yaml", "--kb-dir", str(kb_dir)],
    ]


def scheduled_tasks() -> List[Dict[str, str]]:
    """Status of the two Windows scheduled tasks (empty list when not on Windows or none)."""
    if os.name != "nt":
        return []
    ps = ("Get-ScheduledTask -TaskName 'ChainAIM-Research-*' -ErrorAction SilentlyContinue | "
          "Get-ScheduledTaskInfo | Select-Object TaskName,"
          "@{n='LastRun';e={$_.LastRunTime.ToString('yyyy-MM-dd HH:mm')}},LastTaskResult,"
          "@{n='NextRun';e={$_.NextRunTime.ToString('yyyy-MM-dd HH:mm')}} | ConvertTo-Json")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                             text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return []
    if not out:
        return []
    data = json.loads(out)
    return data if isinstance(data, list) else [data]
