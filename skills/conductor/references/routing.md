# Routing table

Edit this file to change which model does what. IDs are the ones
`orchestrator_capabilities` reported on 2026-11-24. If an ID is missing at
run time, take the newest model of the same family and tier.

**Default bias: spare Claude.** Claude Code limits run out faster than
Cursor's, so Claude is used only where it clearly earns its cost: deep
planning and reviews of risky code.

## Pools

Every route drains one pool. `scripts/usage.py` reports each pool as `ok`,
`tight`, `out`, or `unknown`.

| Pool | Routes | Notes |
| --- | --- | --- |
| `cursor-auto` | `cursor` `default` (Auto), `cursor` `composer-2.5` | Cheapest. The orchestrator itself and the default coder |
| `cursor-api` | `cursor` `grok-4.7`, `gemini-4-neon`, any `claude-*` | Named models. Small included pool, then on-demand $ |
| `claude` | `claudeAgent` `claude-haiku-5-5` < `claude-sonnet-5-5` < `claude-opus-5-5` | 5-hour and 7-day windows. Opus costs the most |
| `free` | `opencode` `opencode/beam-free` or OpenRouter `:free`; `pi` `vllm-router/auto` (local) | Rate-limited or weak. Read-only and trivial work |

Rules:

- **Claude only via `claudeAgent`.** `cursor` `claude-*` bills the
  `cursor-api` pool at API prices. Never use it.
- **Skip any ladder step whose pool is `out`.** Treat `tight` as "use only
  if nothing cheaper fits".

## Budget modes

`usage.py` recommends a mode. The user's words override it ("balanced",
"save cursor", "no claude").

| Mode | When (auto) | Claude use |
| --- | --- | --- |
| `claude-frugal` | default | Plan L/risk and risk reviews only. Opus only for those |
| `claude-off` | Claude 5h ≥ 90% or 7d ≥ 92% | None. Haiku only if every other step is `out` |
| `cursor-frugal` | Cursor Auto pool out, Claude `ok` | Sonnet implements, Haiku reviews light work |
| `survival` | Cursor Auto out and Claude not `ok` | Free models for read-only work; orchestrator does XS fixes; ask the user before anything big |
| `balanced` | user asks only | The "balanced" column below |

## Ladders (claude-frugal, the default)

Start at step 1. Skip steps whose pool is `out`. Move one step right on
failure, a usage-limit error, or two failed check runs.

| Phase | 1 | 2 | 3 |
| --- | --- | --- | --- |
| Plan M | orchestrator writes it (≤20 lines) | `cursor` `gemini-4-neon` `{reasoning_effort: "high"}` | `claudeAgent` `claude-sonnet-5-5` `{effort: "medium"}` |
| Plan L / risk | `claudeAgent` `claude-opus-5-5` `{effort: "high"}` | `cursor` `grok-4.7` `{reasoning_effort: "high"}` | `claudeAgent` `claude-sonnet-5-5` `{effort: "high"}` |
| Implement | `cursor` `composer-2.5` `{fastMode: true}` | `cursor` `composer-2.5` with the failure in the brief | `claudeAgent` `claude-sonnet-5-5` `{effort: "medium"}` |
| Review S | `opencode` free model | `cursor` `grok-4.7` `{reasoning_effort: "medium"}` | `claudeAgent` `claude-haiku-5-5` `{effort: "high"}` |
| Review M/L | `cursor` `grok-4.7` `{reasoning_effort: "high"}` | `cursor` `gemini-4-neon` `{reasoning_effort: "high"}` | `claudeAgent` `claude-sonnet-5-5` `{effort: "high"}` |
| Review risk | `claudeAgent` `claude-opus-5-5` `{effort: "high"}` | `claudeAgent` `claude-sonnet-5-5` `{effort: "high"}` | `cursor` `grok-4.7` `{reasoning_effort: "xhigh"}` |
| CI fix | same as implementer | `claudeAgent` `claude-sonnet-5-5` `{effort: "medium"}` | |
| PR / CI watch / merge | orchestrator, no delegate — stay until green + merged | | |

When `cursor-api` is `out`, M/L reviews fall through to Claude Sonnet. That
is the main Claude cost. Prefer one review round, and two only when
blockers were fixed.

## Other modes, differences only

- **claude-off:** drop every `claudeAgent` step. Plan L uses `grok-4.7`
  or `gemini-4-neon`; if `cursor-api` is also out, the orchestrator plans and
  says the plan is unreviewed. Reviews: `cursor-api` models, then `free`.
  Risk-area work: tell the user that no strong reviewer is available, then
  ask whether to wait for the Claude reset (give `resets_at`) or proceed.
- **cursor-frugal:** implement with `claudeAgent` `claude-sonnet-5-5`
  `{effort: "medium"}`; review S with `claude-haiku-5-5`; review M/L with
  `claude-sonnet-5-5`; keep Opus for Plan L / risk.
- **balanced:** Plan M → Sonnet high; Plan L → Opus high; implement →
  Composer, then Sonnet, then Opus; review → Sonnet high (risk: Opus).

## Family rule for review

The reviewer must be a different family from the implementer. Composer code
can be reviewed by anything. Claude-written code (cursor-frugal) gets a Grok,
Gemini, or free reviewer first.

## Effort

- Low for mechanical edits, renames, and docs.
- Default for implementation.
- High for planning, reviews, and retries after a failure.
- `xhigh`, `max`, `ultrathink`, or `ultracode` only if the user asks. They
  drain the `claude` pool fast.
