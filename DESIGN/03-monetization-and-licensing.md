# Monetization & Licensing (verified 2026-06-21)

> Sources: Anthropic usage policy / Commercial Terms as reported by multiple 2026 write-ups.
> **Terms change — confirm at https://www.anthropic.com/legal and the Console before relying on this.**

## Hard constraint: subscription ≠ commercial
- Claude Pro/Max OAuth is for **individual use only** ("one human, one subscription, one
  beneficiary"). The Agent SDK / products serving others must use **API key auth (Commercial Terms)**.
- April 2026: Anthropic blocked third-party tools (OpenClaw, etc.) from using subscription
  auth at scale. Routing a customer's request through your seat → not allowed.

## Two phases, two billing paths
| Phase | Who consumes output | Billing | Status |
|-------|---------------------|---------|--------|
| Internal research (V1–V4) | you / ChainAIM staff | Claude **Max** via Claude Code (`claude -p`) | allowed — the designed path |
| Monetized product (V5+) | external customers | Claude **API** (Commercial Terms) **or** customer **BYOK** | required once others consume output |

## How to charge (the value-add is the product, not the tokens)
1. **Sell the domain harness + curation**, not LLM access. Wrapper-markup is dying; the fee
   must stand on software value (workflows, proprietary sources, the organized KB, UX, support).
2. **BYOK (Bring Your Own Key):** customer connects their own Anthropic key; you license the
   harness. Best fit for a TypeScript/npm-distributed product. You bear no inference cost.
3. **API + metered billing** with markup justified by substantial value-add.
4. **Output rights:** commercial use of outputs is allowed, but you cannot sell *raw* outputs
   as standalone products without substantial human contribution. Curated highlights/KB qualify;
   a raw transcript dump does not.

## Domain-specific flag (finance/risk)
Deploying Claude in financial/legal/healthcare contexts requires **human-in-the-loop review
and disclosure**. Build a review gate into the productized version before any customer-facing
decision support.

## Implication for the language choice
- For **internal V1**, language is a convenience call (Python ships fastest).
- For **monetization**, a **TypeScript/npm** package is the cleaner distributable for a BYOK
  product and aligns with Claude Code's ecosystem. The contract is identical, so the Python
  internal tool and a TS distributable can coexist.
