# ChainAIM Deep Research Agent — Cost Model

> Scope: **language-independent.** About Claude billing/model routing, not implementation language.

> All figures below were verified via web search on 2026-06-21 against Anthropic's
> support center and multiple 2026 pricing write-ups. **Pricing and limits change —
> confirm current numbers at https://claude.com/pricing and https://support.claude.com
> before baking them into policy.** Do not trust these as permanent.

## 1. How Claude Max actually meters your agent (this drives the design)

Two completely different billing paths, decided by *how* the agent runs:

| Path | What triggers it | How it's billed |
|------|------------------|-----------------|
| **Interactive** | You typing in Claude Code / the IDE extension | Subscription pool: a ~5-hour rolling window + weekly caps, **shared** across Claude chat, Claude Code, and Cowork. No per-token charge. |
| **Non-interactive** (headless) | Agent SDK, `claude -p`, GitHub Actions, cron, third-party apps using your subscription | **As of 2026-06-15:** a *separate monthly credit pool* — **$20 Pro / $100 Max 5x / $200 Max 20x** — at API-equivalent rates. Does **not** roll over. When exhausted, requests stop (or fall to API credits if you enabled them). |
| **API key** | `ANTHROPIC_API_KEY` set in the environment | Pay-per-token at API rates, **ignoring your subscription entirely.** Most common accidental-billing mistake. |

**Design consequences:**
1. A *scheduled* research agent (cron / `claude -p`) lives off the **non-interactive
   credit pool** — effectively ~$100/mo of automation on Max 5x before it stops. The
   agent MUST track spend and exit on budget. This is why `cost_ledger.py` and the
   per-run token ceiling exist.
2. Keep `ANTHROPIC_API_KEY` **unset** in the agent's environment unless you deliberately
   want metered API overflow. The runner should assert this and warn if it's set.
3. CI/cron agents no longer eat your interactive 5-hour window (good) but have their own
   hard monthly cap (must budget for it).

## 2. Model pricing and what each is for (verified API rates, per MTok = million tokens)

| Model | Input | Output | Use it for | Why |
|-------|------:|-------:|------------|-----|
| **Haiku** | ~$1 | ~$5 | Router (classify ambiguous links), high-volume cheap checks | Cheapest; fine for classification. |
| **Sonnet** | ~$3 | ~$15 | Default synthesis (TL;DR, highlights) and the judge | Best quality-per-dollar. |
| **Opus** | ~$5 | ~$25 | Only the "deep" narrative level and hard V4 integration | Highest capability; use sparingly. |

Two levers that dominate the bill:
- **Output is 5× input** on every model → control output length, not input size.
- **Cache reads bill at ~0.1× input**; cache writes ~1.25×. Claude Code reuses a large
  stable prefix (system prompt, CLAUDE.md, tool defs), so most input becomes cache reads.
  Keep `CLAUDE.md` lean and avoid loading unneeded MCP servers — fixed overhead is what
  caching absorbs, and bloated overhead is what wastes the non-interactive pool.

This Haiku/Sonnet/Opus routing is exactly Anthropic's *Building Effective Agents* routing
pattern: send easy tasks to the small model, hard tasks to the big one.

## 3. Variable costs from external KEYS (and expiry risk)

| Dependency | Cost | Expiry / risk | Agent behavior |
|------------|------|---------------|----------------|
| youtube-transcript | Free | IP-block at scale | Throttle + dedupe; warn on repeated blocks |
| markdown-converter (markitdown) | Free | — | — |
| gog-cli (Google Drive) | Free tier | OAuth token expiry | Warn before token lapse |
| tavily (web search) | Free tier | Monthly free-call cap | Track calls; warn near cap |
| context7 (library docs) | Free tier | Rate/quota | Track; warn near cap |
| Twilio (WhatsApp) | **Paid** | Approval-gated onboarding | Flag clearly as paid; not in cheap tiers |

The agent should keep a small `keys_status` check that reports, per run: which free tiers
are near their limit or near expiry, so a function silently going dark never surprises you.

## 4. Cost-conscious operating rules (enforced in code / CLAUDE.md)
1. Never feed a whole video/doc through the model when a free skill can extract the text first.
2. Per-run token budget (`cost.token_budget_per_run`); check before each LLM call; exit + checkpoint on breach.
3. Synthesis defaults to Sonnet; Opus only for the "deep" level, explicitly.
4. Evaluator-optimizer loop capped at 2 retries.
5. V4 multi-agent (the ~15× pattern) only behind `--deep` with its own hard ceiling.
6. Report tokens (this run + cumulative) and free-tier status every run.
