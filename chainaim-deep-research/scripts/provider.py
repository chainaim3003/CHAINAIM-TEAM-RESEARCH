"""provider.py — the ONE swappable layer between "run on Max" and "run via API key".

Contract (DESIGN/01-architecture-contract.md s4 + DESIGN/04-execution-modes.md):
    ModelProvider.complete(prompt, model_tier, max_tokens) -> {text, usage{input,output}}
    SubscriptionProvider  -> shells to `claude -p` (Claude MAX / OAuth)
    ApiProvider           -> Anthropic API with ANTHROPIC_API_KEY
    select_provider(config) -> validates env guardrails, returns the right impl

STATUS IN V1 (honest, per Rule 3/8):
  - select_provider() and its guardrails are REAL and unit-testable NOW. `orchestrate.py
    --provider-check` runs exactly these guardrails so you can validate your environment
    before V2 wiring.
  - SubscriptionProvider.complete() and ApiProvider.complete() are REAL implementations,
    but they are NOT invoked by the V1 pipeline (V1 synthesis is a manual Claude Code/Max
    session — see DESIGN/04-execution-modes.md). They become load-bearing in V2 when
    synthesis is scripted.
  - LABELLED UNVERIFIED: the exact JSON shape of `claude -p --output-format json`
    (esp. the usage field names) must be confirmed against the installed Claude Code CLI
    on your machine. The parser below is defensive and tries known field names, but you
    should verify with: `claude -p "hi" --output-format json` and adjust _parse_usage()
    if the keys differ. This is the only part of this file not verifiable from here.
"""

from __future__ import annotations

import json
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class ProviderError(RuntimeError):
    """Raised for guardrail violations or provider invocation failures."""


@dataclass
class Completion:
    text: str
    usage: Dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0})


# tier -> concrete model id. Override via config.model.route + a tier->id map if you
# pin specific dated model snapshots. Defaults are family aliases.
DEFAULT_TIER_MODELS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}


class ModelProvider(ABC):
    def __init__(self, route: Dict[str, str], tier_models: Optional[Dict[str, str]] = None) -> None:
        self.route = route  # logical role -> tier, e.g. {"synthesize": "sonnet"}
        self.tier_models = {**DEFAULT_TIER_MODELS, **(tier_models or {})}

    def model_for(self, model_tier: str) -> str:
        """Resolve a tier name ('sonnet') OR a role ('synthesize') to a model id."""
        tier = self.route.get(model_tier, model_tier)  # role -> tier, else passthrough
        return self.tier_models.get(tier, tier)

    @abstractmethod
    def complete(self, prompt: str, model_tier: str, max_tokens: int = 1024) -> Completion:
        ...


class SubscriptionProvider(ModelProvider):
    """Claude MAX via the sanctioned automation path: `claude -p`.

    Billing: non-interactive credit pool when headless (see DESIGN/02-cost-model.md).
    Requires ANTHROPIC_API_KEY to be UNSET (enforced by select_provider) so Claude Code
    uses your subscription rather than silently billing the API.
    """

    def __init__(self, route, tier_models=None, *, claude_bin: str = "claude", timeout_s: float = 600.0) -> None:
        super().__init__(route, tier_models)
        self.claude_bin = claude_bin
        self.timeout_s = timeout_s

    @staticmethod
    def _parse_usage(payload: Dict[str, Any]) -> Dict[str, int]:
        # UNVERIFIED field names — see module docstring. Try known variants.
        usage = payload.get("usage") or payload.get("message", {}).get("usage") or {}
        in_tok = int(usage.get("input_tokens", usage.get("input", 0)) or 0)
        out_tok = int(usage.get("output_tokens", usage.get("output", 0)) or 0)
        return {"input": in_tok, "output": out_tok}

    @staticmethod
    def _parse_text(payload: Dict[str, Any]) -> str:
        if isinstance(payload.get("result"), str):
            return payload["result"]
        content = payload.get("content") or payload.get("message", {}).get("content")
        if isinstance(content, list):
            return "".join(b.get("text", "") for b in content if isinstance(b, dict))
        if isinstance(content, str):
            return content
        return ""

    def complete(self, prompt: str, model_tier: str, max_tokens: int = 1024) -> Completion:
        model = self.model_for(model_tier)
        cmd = [self.claude_bin, "-p", prompt, "--output-format", "json", "--model", model]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_s)
        except FileNotFoundError as exc:
            raise ProviderError(f"`{self.claude_bin}` not found on PATH: {exc}") from exc
        if proc.returncode != 0:
            raise ProviderError(f"claude -p failed (rc={proc.returncode}): {proc.stderr.strip()}")
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            # plain-text fallback if --output-format json isn't honored
            return Completion(text=proc.stdout.strip(), usage={"input": 0, "output": 0})
        return Completion(text=self._parse_text(payload), usage=self._parse_usage(payload))


class ApiProvider(ModelProvider):
    """Anthropic API via ANTHROPIC_API_KEY (Commercial Terms path; multi-tenant ok).

    Imports the `anthropic` SDK lazily so V1 (which never calls this) has no hard
    dependency on it. Install with: `uv add anthropic` (or the [api] extra).
    """

    def __init__(self, route, tier_models=None, *, api_key_env: str = "ANTHROPIC_API_KEY") -> None:
        super().__init__(route, tier_models)
        self.api_key_env = api_key_env

    def complete(self, prompt: str, model_tier: str, max_tokens: int = 1024) -> Completion:
        try:
            import anthropic  # lazy import
        except ImportError as exc:
            raise ProviderError(
                "ApiProvider needs the 'anthropic' SDK: `uv add anthropic`"
            ) from exc
        client = anthropic.Anthropic(api_key=os.environ[self.api_key_env])
        msg = client.messages.create(
            model=self.model_for(model_tier),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        return Completion(
            text=text,
            usage={"input": msg.usage.input_tokens, "output": msg.usage.output_tokens},
        )


def select_provider(config: Dict[str, Any]) -> ModelProvider:
    """Validate env guardrails (DESIGN/04-execution-modes.md) and return the impl.

    Guardrails enforced:
      1. Key hygiene / no silent API billing:
         provider == subscription -> ANTHROPIC_API_KEY MUST be unset (else it would
                                      silently bill the API instead of your Max seat).
         provider == api          -> the key MUST be set.
      2. One-beneficiary guard:
         deployment == product    -> refuse subscription (force api). Serving others on a
                                      personal seat violates the subscription terms.
    Raises ProviderError on any violation (fail loudly, before spending anything).
    """
    model = config.get("model", {})
    provider = model.get("provider", "subscription")
    deployment = model.get("deployment", "internal")
    route = model.get("route", {})
    api_key_env = model.get("api_key_env", "ANTHROPIC_API_KEY")
    oauth_env = model.get("oauth_token_env", "CLAUDE_CODE_OAUTH_TOKEN")
    tier_models = model.get("tier_models")  # optional override map

    if deployment == "product" and provider == "subscription":
        raise ProviderError(
            "deployment=product forbids provider=subscription (one human, one beneficiary). "
            "Serving others on a personal Max seat violates the subscription terms — set provider: api."
        )

    if provider == "subscription":
        if os.environ.get(api_key_env):
            raise ProviderError(
                f"{api_key_env} is set, but provider=subscription. Claude Code would silently "
                f"bill the API instead of your Max seat. `unset {api_key_env}` or switch to provider: api."
            )
        # OAuth token is required only for HEADLESS subscription use; interactive `/login`
        # sessions don't need it. Warn-don't-fail (return provider; orchestrate prints the note).
        return SubscriptionProvider(route, tier_models)

    if provider == "api":
        if not os.environ.get(api_key_env):
            raise ProviderError(f"provider=api but {api_key_env} is not set.")
        return ApiProvider(route, tier_models, api_key_env=api_key_env)

    raise ProviderError(f"unknown model.provider '{provider}' (expected 'subscription' or 'api')")


def provider_env_report(config: Dict[str, Any]) -> Dict[str, Any]:
    """Non-raising introspection for `--provider-check`: report what the guardrails see."""
    model = config.get("model", {})
    api_key_env = model.get("api_key_env", "ANTHROPIC_API_KEY")
    oauth_env = model.get("oauth_token_env", "CLAUDE_CODE_OAUTH_TOKEN")
    return {
        "provider": model.get("provider"),
        "deployment": model.get("deployment"),
        f"{api_key_env}_set": bool(os.environ.get(api_key_env)),
        f"{oauth_env}_set": bool(os.environ.get(oauth_env)),
    }
