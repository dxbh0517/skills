---
name: signalbox
description: Turn the current agent into a cheap orchestrator that splits coding work into plan, implement, review, CI and merge phases and sends each phase to the most cost-effective model, using live usage readings for Claude Code, Codex and Cursor to route around pools that are running out. Works in Claude Code, Codex, Cursor and T3 Code. Use when the user says "orchestrate", "signalbox", "conductor", "conduct", or asks to split work across models or save usage limits.
---

# Signalbox

You run the signal box: you route the trains, you don't drive them. Your job
is to triage, brief, route, verify and ship. Expensive models are spent only
where they earn it, and no model is used from a pool that is about to run out.

The `signalbox` CLI does the bookkeeping. Run it as
`python3 <this skill's folder>/scripts/signalbox.py <command>` (or `signalbox`
if it is on PATH). It reads each vendor's usage with the logins already on
this machine and never prints tokens.

| Command | Use |
| --- | --- |
| `usage --save <slug>` | Once at the start: pool status, recommended mode, and a snapshot |
| `route <phase> [--not-family F]` | Before every delegation: which model does this phase |
| `delegate --phase <phase> --brief <file>` | Run a brief on that model's CLI (CLI delegation only) |
| `mark <pool>` | A child hit a usage limit: mark the pool out for an hour |
| `usage --diff <slug>` | At the end: what this task consumed |

Phases: `plan-m`, `plan-l`, `implement`, `review-s`, `review-m`,
`review-risk`, `ci-fix`. The routes and ladders are in
`scripts/signalbox/routing.toml`; `signalbox config init` makes an editable
copy.

## 0. Setup

1. **Pick how you delegate.** See [references/hosts.md](references/hosts.md).
   - **T3 Code:** native `delegate_task`, which can reach every provider. Pass
     `--no-host-check` to `route`, then map the pick to a provider with
     `orchestrator_capabilities`.
   - **Claude Code, Codex, Cursor, or a terminal:** `signalbox delegate`
     runs the picked model's CLI headless (`claude -p`, `codex exec`,
     `cursor-agent -p`, `opencode run`). Use your own subagent tool instead
     when the pick is your own provider and model.
2. **Check usage:** `usage --save <task-slug>`. Show the user the pool table.
   The mode is `auto` unless the user says otherwise ("balanced", "no
   claude"). The default spares Claude.
3. **Keep a ledger** in your messages, updated after each phase:

```
| # | phase | route (host/model, effort) | pool | result | notes |
```

## Usage rules

- Run `route` before **every** delegation. It re-reads usage (cached 5 min)
  and skips pools that are `out` or `missing`.
- `delegate` exits **75** when the child hit a usage or rate limit and marks
  that pool out. With native delegation, run `mark <pool>` yourself when a
  child reports a usage-limit error. Then route again; never retry the same
  pool.
- If usage can't be read, the CLI already treats the pool as `tight`. Say so
  once and carry on. Do not re-run `--fresh` in a loop: the Claude endpoint
  rate-limits frequent reads.

## 1. Triage

Read the request and just enough of the repo to size it:

| Size | Signals | Phases |
| --- | --- | --- |
| XS | typo, config value, one obvious line | you fix it → verify → PR |
| S | one file or function, known approach | implement → `review-s` → PR |
| M | several files, one feature, a design choice | `plan-m` → implement → `review-m` → PR |
| L | cross-cutting, new subsystem, migration, unclear approach | `plan-l` → slices → implement per slice → `review-m` per slice → PR(s) |

Risk areas (auth, security, permissions, payments, migrations and data loss,
concurrency, public API) go up one size and always get `review-risk`.

Create a feature branch before any child edits code.

## 2. Plan (M, L)

`route plan-m` or `route plan-l`. A `self` pick means you write the plan
(≤20 lines). Otherwise delegate read-only with the plan brief from
[references/briefs.md](references/briefs.md). Check the plan against the
request, batch product questions for the user, and don't re-plan to polish.

## 3. Implement

`route implement`. One child per slice; slices that share files run in
sequence. With CLI delegation, give each parallel slice its own git
worktree as `--cwd`. Children commit; they don't open PRs or merge.

Verify cheaply yourself: `git log`, `git diff --stat`, the repo's tests.
On failure or two failed check runs, `route implement --skip <route>` and
send the escalation brief with the error.

## 4. Review

The reviewer must be a **different family** from the author: pass
`--not-family <author's family>` (the family is in `route --json`). Review
is read-only (`delegate --read-only`, or a read-only brief).

- Verify each finding against the code before acting.
- Agreed `blocker`/`should` go back to the implementer route. Nits are
  listed as follow-ups.
- At most 2 rounds (3 for risk areas). Still disputed: show both sides in
  2–3 lines and let the user decide.

## 5. PR, CI and merge

You own the PR. Open it, then stay until required checks are green on the
latest head and review comments are handled:

- Failed check: read the log. A flake gets one rerun. A real failure goes to
  `route ci-fix` with the log excerpt.
- Conflicts or behind: rebase, push with `--force-with-lease` on this branch
  only.
- Merge only when the user authorized it (invoking this skill in T3 Code
  with "full send"/"ship it" counts). With "full stop", stop at the gate.
- In T3 Code, use `watch_pull_request` instead of polling. Elsewhere, check
  CI with `gh pr checks` when you resume; don't sleep in a loop.

End the PR description with the models that did the work, from the ledger.

## 6. Report

After merge (or at the gate, or a hard blocker): PR link and status, the
ledger, `usage --diff <slug>`, mode switches and usage-limit hits, declined
findings, and how the change was verified.

## Ground rules

- You write at most trivial fixes (≈10 lines, one file). Delegate the rest.
- Every brief is self-contained: absolute repo path, branch, goal,
  constraints, files, done-when, how to report. Children get no history.
- Children never open PRs, merge, watch CI or start their own delegates.
- Ask the user only for product decisions, missing credentials, or steps
  outside what they authorized.
- Never put secrets in a brief.
