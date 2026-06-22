"""cost_ledger.py — per-run token accounting + budget gate.

Implements the contract interface (DESIGN/01-architecture-contract.md section 4):
    costLedger.over_budget() -> bool
    costLedger.add(...)
    costLedger.flush() -> run

V1 spends ZERO LLM tokens (extraction only), so in V1 this ledger mostly records
free_tool_calls and items counts, and the budget gate is a no-op guard that becomes
load-bearing in V2+ when synthesis is scripted. The gate is implemented for real now
so the V2 switch is a config change, not a refactor (see DESIGN/04-execution-modes.md).

cost_ledger line schema (DESIGN/01-architecture-contract.md section 3):
    { "ts", "items_processed", "items_skipped_dedupe",
      "free_tool_calls", "llm_tokens", "tool_cost_usd" }
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class CostLedger:
    """Accumulates one run's counters and appends a JSONL line on flush().

    Args:
        path: absolute path to cost_ledger.jsonl.
        token_budget_per_run: hard ceiling on llm_tokens for this run. over_budget()
            returns True once projected/accumulated tokens meet or exceed it.
    """

    def __init__(self, path: str | Path, *, token_budget_per_run: int) -> None:
        self.path = Path(path)
        self.token_budget_per_run = int(token_budget_per_run)
        self.items_processed = 0
        self.items_skipped_dedupe = 0
        self.free_tool_calls = 0
        self.llm_tokens = 0
        self.tool_cost_usd = 0.0

    def over_budget(self, projected_tokens: int = 0) -> bool:
        """True if accumulated + projected tokens would meet/exceed the run budget.

        Call BEFORE each LLM request with the projected token cost of that request,
        so the orchestrator can checkpoint and stop cleanly instead of overspending.
        """
        return (self.llm_tokens + max(0, projected_tokens)) >= self.token_budget_per_run

    def add(
        self,
        *,
        items_processed: int = 0,
        items_skipped_dedupe: int = 0,
        free_tool_calls: int = 0,
        llm_tokens: int = 0,
        tool_cost_usd: float = 0.0,
    ) -> None:
        """Accumulate counters. All args are keyword-only with 0 defaults."""
        self.items_processed += items_processed
        self.items_skipped_dedupe += items_skipped_dedupe
        self.free_tool_calls += free_tool_calls
        self.llm_tokens += llm_tokens
        self.tool_cost_usd += tool_cost_usd

    def as_run(self) -> Dict[str, Any]:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "items_processed": self.items_processed,
            "items_skipped_dedupe": self.items_skipped_dedupe,
            "free_tool_calls": self.free_tool_calls,
            "llm_tokens": self.llm_tokens,
            "tool_cost_usd": round(self.tool_cost_usd, 6),
        }

    def flush(self) -> Dict[str, Any]:
        """Append this run's line to the ledger file and return it."""
        run = self.as_run()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(run, ensure_ascii=False) + "\n")
        return run

    def cumulative(self) -> Dict[str, Any]:
        """Read the whole ledger and sum counters across all past runs (+ this one).

        Used for the 'tokens this run + cumulative' report the design requires.
        """
        totals = {
            "runs": 0,
            "items_processed": 0,
            "items_skipped_dedupe": 0,
            "free_tool_calls": 0,
            "llm_tokens": 0,
            "tool_cost_usd": 0.0,
        }
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue  # tolerate a partial trailing line
                totals["runs"] += 1
                for k in ("items_processed", "items_skipped_dedupe", "free_tool_calls", "llm_tokens"):
                    totals[k] += int(rec.get(k, 0))
                totals["tool_cost_usd"] += float(rec.get("tool_cost_usd", 0.0))
        # add the in-memory (not-yet-flushed) run
        totals["runs"] += 1
        totals["items_processed"] += self.items_processed
        totals["items_skipped_dedupe"] += self.items_skipped_dedupe
        totals["free_tool_calls"] += self.free_tool_calls
        totals["llm_tokens"] += self.llm_tokens
        totals["tool_cost_usd"] = round(totals["tool_cost_usd"] + self.tool_cost_usd, 6)
        return totals
