"""provider.py — the ONE swappable layer between "run on Max" and "run via API key".

Contract (DESIGN/01-architecture-contract.md s4 + DESIGN/04-execution-modes.md):
    ModelProvider.complete(prompt, model_tier, max_tokens) -> Completion{text, usage, cost_usd}
    ModelProvider.complete_json(prompt, schema, model_tier, max_tokens) -> dict
    SubscriptionProvider  -> `claude -p` (Claude MAX subscription login / OAuth token)
    ApiProvider           -> Anthropic API with ANTHROPIC_API_KEY
    select_provider(config) -> validates env guardrails, returns the right impl

PR-4 hardening (DESIGN/07-build-plan.md), verified against the official headless docs
(https://code.claude.com/docs/en/headless, read 2026-11-23):
  1. The prompt goes in on STDIN, not as a command-line argument. Windows caps a command line
     at 32,767 characters and transcripts here reach ~100 KB, so argv would fail. `claude -p`
     reads stdin (documented cap: 10 MB).
  2. The binary is resolved with shutil.which, so `claude.exe` / `claude.cmd` on Windows work.
  3. Each call runs in a clean, empty scratch folder. Without --bare, `claude -p` loads the
     CLAUDE.md, hooks and MCP config of its working directory; running from the repo would add
     those to every call. (--bare is NOT used: it ignores the subscription login.)
  4. Subprocess I/O is decoded as UTF-8 explicitly (Windows' default code page would break on
     characters such as an em dash in a transcript).
  5. `--output-format json`: the text is read from `result`; `is_error: true`, a non-zero exit
     code, unparseable output or a missing `result` raise ProviderError — never a silent
     empty success. Usage is read from `usage` and the client-side cost estimate from
     `total_cost_usd` (documented as an estimate).
  6. Structured output: `complete_json()` passes `--json-schema` and returns
     `structured_output`; a missing field raises ProviderError (docs: absent when the run ends
     without valid structured output).
  7. Models are chosen by ALIAS for the subscription path ("haiku" / "sonnet" / "opus"), so
     no dated model ID is hard-coded and goes stale. The API path needs full model IDs, kept in
     config `model.api_tier_models`.

`max_tokens` applies to ApiProvider only; `claude -p` has no output-token flag, so spend on the
subscription path is controlled by the pipeline's CostLedger budget gate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class ProviderError(RuntimeError):
    """Raised for guardrail violations or provider invocation failures."""


@dataclass
class Completion:
    """One model response.

    text:     the response text.
    usage:    {"input", "output", "cache_read", "cache_write"} token counts (0 when unknown).
    cost_usd: cost estimate for this call when the provider reports one (claude -p's
              total_cost_usd is a client-side estimate), else None.
    model:    the model name/alias the call was made with.
    raw:      the provider's full JSON payload (for debugging / audit).
    """
    text: str
    usage: Dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
    cost_usd: Optional[float] = None
    model: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Tokens counted against the run budget (input + output + cache reads/writes)."""
        return sum(int(v or 0) for v in self.usage.values())


# Subscription path: Claude Code model ALIASES (resolved by the CLI to the current model).
DEFAULT_SUBSCRIPTION_MODELS = {"haiku": "haiku", "sonnet": "sonnet", "opus": "opus"}


class ModelProvider(ABC):
    """Common routing: a role ('synthesize') or tier ('sonnet') -> concrete model name."""

    def __init__(self, route: Dict[str, str], tier_models: Dict[str, str]) -> None:
        self.route = route or {}                # role -> tier, e.g. {"synthesize": "sonnet"}
        self.tier_models = dict(tier_models)    # tier -> model name/alias

    def model_for(self, model_tier: str) -> str:
        """Resolve a role or tier to a model name. Unknown names pass through unchanged."""
        tier = self.route.get(model_tier, model_tier)
        return self.tier_models.get(tier, tier)

    @abstractmethod
    def complete(self, prompt: str, model_tier: str, max_tokens: int = 1024) -> Completion:
        ...

    @abstractmethod
    def complete_json(self, prompt: str, schema: Dict[str, Any], model_tier: str,
                      max_tokens: int = 1024) -> Dict[str, Any]:
        ...


def _empty_usage() -> Dict[str, int]:
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}


class SubscriptionProvider(ModelProvider):
    """Claude MAX via the sanctioned automation path: `claude -p`.

    Requires ANTHROPIC_API_KEY to be UNSET (enforced by select_provider) so Claude Code uses
    your subscription login rather than silently billing the API.

    Args:
        route:       role -> tier map (config model.route).
        tier_models: tier -> model alias (config model.tier_models; default aliases).
        claude_bin:  executable name or path (config model.claude_bin, default "claude").
        claude_cmd:  full command prefix instead of claude_bin (tests pass
                     [python, fake_claude.py]); overrides claude_bin when given.
        timeout_s:   per-call timeout in seconds (config model.timeout_s, default 600).
        workdir:     folder the CLI runs in; default a fresh empty temp folder per provider.
    """

    def __init__(
        self,
        route: Dict[str, str],
        tier_models: Optional[Dict[str, str]] = None,
        *,
        claude_bin: str = "claude",
        claude_cmd: Optional[Sequence[str]] = None,
        timeout_s: float = 600.0,
        workdir: Optional[str] = None,
    ) -> None:
        super().__init__(route, {**DEFAULT_SUBSCRIPTION_MODELS, **(tier_models or {})})
        self.claude_bin = claude_bin
        self._claude_cmd = list(claude_cmd) if claude_cmd else None
        self.timeout_s = float(timeout_s)
        self._workdir = workdir

    # -- helpers -------------------------------------------------------------------------
    def _base_cmd(self) -> List[str]:
        if self._claude_cmd:
            return list(self._claude_cmd)
        resolved = shutil.which(self.claude_bin)
        if not resolved:
            raise ProviderError(
                f"`{self.claude_bin}` not found on PATH. Install Claude Code or set model.claude_bin "
                f"to its full path."
            )
        return [resolved]

    def _cwd(self) -> str:
        if not self._workdir:
            self._workdir = tempfile.mkdtemp(prefix="cdr-claude-")
        Path(self._workdir).mkdir(parents=True, exist_ok=True)
        return self._workdir

    @staticmethod
    def parse_usage(payload: Dict[str, Any]) -> Dict[str, int]:
        """Map claude -p `usage` (Anthropic API field names) to our usage dict."""
        u = payload.get("usage") or {}
        return {
            "input": int(u.get("input_tokens") or 0),
            "output": int(u.get("output_tokens") or 0),
            "cache_read": int(u.get("cache_read_input_tokens") or 0),
            "cache_write": int(u.get("cache_creation_input_tokens") or 0),
        }

    def _run(self, prompt: str, model: str, extra_args: Sequence[str] = ()) -> Dict[str, Any]:
        """Run `claude -p` once with the prompt on stdin; return the parsed JSON payload."""
        cmd = self._base_cmd() + ["-p", "--output-format", "json", "--model", model, *extra_args]
        try:
            proc = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=self.timeout_s, cwd=self._cwd(),
            )
        except FileNotFoundError as exc:
            raise ProviderError(f"cannot start {cmd[0]!r}: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"claude -p timed out after {self.timeout_s:.0f}s") from exc

        out = (proc.stdout or "").strip()
        try:
            payload = json.loads(out) if out else None
        except json.JSONDecodeError:
            payload = None
        if proc.returncode != 0:
            # Docs: failures inside the run are printed as the result on stdout.
            detail = (payload or {}).get("result") if isinstance(payload, dict) else None
            raise ProviderError(
                f"claude -p failed (exit {proc.returncode}): {detail or (proc.stderr or out).strip()[:500]}"
            )
        if not isinstance(payload, dict):
            raise ProviderError(f"claude -p returned non-JSON output: {out[:300]!r}")
        if payload.get("is_error"):
            raise ProviderError(f"claude -p reported an error: {str(payload.get('result'))[:500]}")
        return payload

    # -- public API ----------------------------------------------------------------------
    def complete(self, prompt: str, model_tier: str, max_tokens: int = 1024) -> Completion:
        """Run one prompt; return the text, token usage and cost estimate."""
        model = self.model_for(model_tier)
        payload = self._run(prompt, model)
        text = payload.get("result")
        if not isinstance(text, str):
            raise ProviderError("claude -p JSON has no string 'result' field")
        cost = payload.get("total_cost_usd")
        return Completion(text=text, usage=self.parse_usage(payload),
                          cost_usd=float(cost) if isinstance(cost, (int, float)) else None,
                          model=model, raw=payload)

    def complete_json(self, prompt: str, schema: Dict[str, Any], model_tier: str,
                      max_tokens: int = 1024) -> Dict[str, Any]:
        """Run one prompt with --json-schema; return the validated `structured_output` dict.

        Raises ProviderError when the run ends without structured output (docs: the field is
        absent then — e.g. the model declined).
        """
        model = self.model_for(model_tier)
        payload = self._run(prompt, model, ["--json-schema", json.dumps(schema)])
        out = payload.get("structured_output")
        if not isinstance(out, dict):
            raise ProviderError("claude -p returned no structured_output for the given --json-schema")
        self.last_payload = payload  # usage/cost of the last structured call, for the ledger
        return out


class ApiProvider(ModelProvider):
    """Anthropic API via ANTHROPIC_API_KEY (Commercial Terms path; multi-tenant ok).

    Needs full model IDs (config model.api_tier_models). The `anthropic` SDK is imported lazily
    so subscription-only runs have no dependency on it (`uv sync --extra api` to install).
    """

    def __init__(self, route: Dict[str, str], tier_models: Dict[str, str], *,
                 api_key_env: str = "ANTHROPIC_API_KEY") -> None:
        if not tier_models:
            raise ProviderError("provider=api needs model.api_tier_models (tier -> full model ID) in config.yaml")
        super().__init__(route, tier_models)
        self.api_key_env = api_key_env

    def _client(self):
        try:
            import anthropic  # lazy import
        except ImportError as exc:
            raise ProviderError("ApiProvider needs the 'anthropic' SDK: `uv sync --extra api`") from exc
        return anthropic.Anthropic(api_key=os.environ[self.api_key_env])

    def complete(self, prompt: str, model_tier: str, max_tokens: int = 1024) -> Completion:
        model = self.model_for(model_tier)
        msg = self._client().messages.create(
            model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        u = msg.usage
        usage = {
            "input": int(getattr(u, "input_tokens", 0) or 0),
            "output": int(getattr(u, "output_tokens", 0) or 0),
            "cache_read": int(getattr(u, "cache_read_input_tokens", 0) or 0),
            "cache_write": int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        }
        return Completion(text=text, usage=usage, cost_usd=None, model=model)

    def complete_json(self, prompt: str, schema: Dict[str, Any], model_tier: str,
                      max_tokens: int = 1024) -> Dict[str, Any]:
        """Structured output on the API path via a forced tool call with the schema as input."""
        model = self.model_for(model_tier)
        msg = self._client().messages.create(
            model=model, max_tokens=max_tokens,
            tools=[{"name": "emit", "description": "Return the answer in this exact structure.",
                    "input_schema": schema}],
            tool_choice={"type": "tool", "name": "emit"},
            messages=[{"role": "user", "content": prompt}],
        )
        for b in msg.content:
            if getattr(b, "type", None) == "tool_use" and isinstance(getattr(b, "input", None), dict):
                return b.input
        raise ProviderError("API response contained no structured tool output")


def select_provider(config: Dict[str, Any]) -> ModelProvider:
    """Validate env guardrails (DESIGN/04-execution-modes.md) and return the impl.

    Guardrails enforced:
      1. Key hygiene / no silent API billing:
         provider == subscription -> ANTHROPIC_API_KEY MUST be unset.
         provider == api          -> the key MUST be set.
      2. One-beneficiary guard:
         deployment == product    -> refuse subscription (force api).
    Raises ProviderError on any violation (fail loudly, before spending anything).
    """
    model = config.get("model", {})
    provider = model.get("provider", "subscription")
    deployment = model.get("deployment", "internal")
    route = model.get("route", {})
    api_key_env = model.get("api_key_env", "ANTHROPIC_API_KEY")

    if deployment == "product" and provider == "subscription":
        raise ProviderError(
            "deployment=product forbids provider=subscription (one human, one beneficiary). "
            "Serving others on a personal Max seat violates the subscription terms — set provider: api."
        )

    if provider == "subscription":
        if os.environ.get(api_key_env):
            raise ProviderError(
                f"{api_key_env} is set, but provider=subscription. Claude Code would silently "
                f"bill the API instead of your Max seat. Unset {api_key_env} or switch to provider: api."
            )
        return SubscriptionProvider(
            route, model.get("tier_models"),
            claude_bin=model.get("claude_bin", "claude"),
            timeout_s=float(model.get("timeout_s", 600)),
            workdir=model.get("claude_workdir"),
        )

    if provider == "api":
        if not os.environ.get(api_key_env):
            raise ProviderError(f"provider=api but {api_key_env} is not set.")
        return ApiProvider(route, model.get("api_tier_models") or {}, api_key_env=api_key_env)

    raise ProviderError(f"unknown model.provider '{provider}' (expected 'subscription' or 'api')")


def provider_env_report(config: Dict[str, Any]) -> Dict[str, Any]:
    """Non-raising introspection for `--provider-check`: report what the guardrails see."""
    model = config.get("model", {})
    api_key_env = model.get("api_key_env", "ANTHROPIC_API_KEY")
    oauth_env = model.get("oauth_token_env", "CLAUDE_CODE_OAUTH_TOKEN")
    claude_bin = model.get("claude_bin", "claude")
    return {
        "provider": model.get("provider"),
        "deployment": model.get("deployment"),
        f"{api_key_env}_set": bool(os.environ.get(api_key_env)),
        f"{oauth_env}_set": bool(os.environ.get(oauth_env)),
        "claude_bin": shutil.which(claude_bin) or f"NOT FOUND ({claude_bin})",
    }
