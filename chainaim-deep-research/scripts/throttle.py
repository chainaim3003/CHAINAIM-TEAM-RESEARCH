"""throttle.py — pacing + retry/backoff for external (free) skill calls.

Implements the contract interface (DESIGN/01-architecture-contract.md section 4):
    throttle.run_with_retry(cmd) -> (ok, output)
with min_delay, jitter, backoff, max_retries.

Why this exists: the free youtube-transcript skill can get IP-throttled at scale
(see DESIGN/02-cost-model.md). We pace calls and retry with exponential backoff so
a transient block doesn't fail the whole run, and we never hammer the endpoint.

No LLM. Shells out to deterministic skills via subprocess.
"""

from __future__ import annotations

import os
import random
import subprocess
import time
from dataclasses import dataclass
from typing import List, Sequence, Tuple


def utf8_env() -> dict:
    """Environment for child Python processes: force UTF-8 stdout/stderr (PEP 540 UTF-8 mode)."""
    return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")


@dataclass
class Throttle:
    """Pace and retry subprocess calls.

    All behavior is configurable (Rule 8 — flags in the signature):
        min_delay_s:    minimum seconds enforced before each call
        jitter_s:       random 0..jitter_s added to each delay (anti-thundering-herd)
        backoff_factor: delay multiplier applied per retry attempt
        max_retries:    total attempts per command before giving up
        timeout_s:      per-call subprocess timeout (None = no timeout)
    """

    min_delay_s: float = 2.0
    jitter_s: float = 1.0
    backoff_factor: float = 2.0
    max_retries: int = 3
    timeout_s: float | None = 300.0

    # internal: timestamp of the last call, to enforce min_delay between calls
    _last_call_ts: float = 0.0

    def _sleep_before_call(self, attempt: int) -> None:
        base = self.min_delay_s * (self.backoff_factor ** attempt)
        delay = base + random.uniform(0.0, self.jitter_s)
        # also respect min spacing since the previous call returned
        since_last = time.monotonic() - self._last_call_ts
        if since_last < self.min_delay_s:
            delay = max(delay, self.min_delay_s - since_last)
        if delay > 0:
            time.sleep(delay)

    def run_with_retry(self, cmd: Sequence[str]) -> Tuple[bool, str]:
        """Run cmd with pacing + retry. Returns (ok, output).

        ok=True  -> returncode 0; output is stdout.
        ok=False -> exhausted retries; output is the last stderr (or error text).
        """
        cmd_list: List[str] = list(cmd)
        last_err = ""
        for attempt in range(self.max_retries):
            self._sleep_before_call(attempt)
            try:
                # PR-13: always UTF-8 on BOTH sides. Without this, Windows decodes the child's
                # output with the PC's code page (e.g. cp1252) and transcripts containing
                # characters like curly quotes or emoji crash with UnicodeDecodeError.
                proc = subprocess.run(
                    cmd_list,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=utf8_env(),
                    timeout=self.timeout_s,
                )
            except subprocess.TimeoutExpired:
                last_err = f"timeout after {self.timeout_s}s on attempt {attempt + 1}"
                self._last_call_ts = time.monotonic()
                continue
            except FileNotFoundError as exc:
                # command itself missing (e.g. 'uv' not installed) — no point retrying
                return False, f"command not found: {exc}"
            self._last_call_ts = time.monotonic()
            if proc.returncode == 0:
                return True, proc.stdout or ""
            last_err = (proc.stderr or proc.stdout or "").strip()
        return False, last_err
