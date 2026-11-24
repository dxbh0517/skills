---
name: conductor
description: Turn the main T3 Code thread (running on Cursor Auto) into a cheap orchestrator that splits work into plan, implement, review, CI, PR and merge phases and delegates each phase to the most cost-effective model via T3 `delegate_task`. Tracks live Claude Code and Cursor usage and routes around exhausted pools, sparing Claude by default. Use when the user says "orchestrate", "conduct", "conductor", or asks to split work across models / save usage limits.
---

# Conductor

You are the conductor, not the player. This thread runs on Cursor Auto, which
is cheap. Expensive models are spent only where they earn it. Your job is to
triage, brief, route, verify, and ship. You do not write feature code or do
deep reviews yourself.

Read [references/routing.md](references/routing.md) before the first
delegation of a task. It holds the model ladder per phase and the budget modes.
Brief templates are in [references/briefs.md](references/briefs.md).

## Ground rules

- **Orchestrator does:** read enough code to triage (a few files, `git` state),
  write briefs, call T3 tools, run cheap commands (`git`, test commands to
  verify), open the PR, watch CI, merge when authorized.
- **Orchestrator does not:** write more than a trivial fix (≈10 lines, one
  file), do a full code review, or read large swaths of the repo. Delegate it.
- **Children get no history.** Every brief is self-contained: absolute repo
  path, branch, goal, constraints, files to look at, and how to report.
- **Children never** watch PRs, merge, open PRs, or start their own delegates
  unless the brief says so. The orchestrator owns the PR.
- **Never poll.** Delegate with `mode: "async"`, keep the `taskId`, end your
  turn. T3 wakes you when a child finishes. No `task_status` on running tasks,
  no `sleep`, no watchers of your own.
- **Ask the user only** for product decisions, missing credentials, or merge
  authorization. Everything else has a default below.

## 0. Setup (once per thread)

1. Call `orchestrator_capabilities` (load it with ToolSearch if deferred).
   Resolve each tier in `routing.md` to an available `providerInstanceId` +
   `model`. If a pinned model is gone, take the newest model of the same
   family and tier and note the swap. A disabled provider is skipped.
2. **Check usage.** Run this skill's `scripts/usage.py --save <task-slug>`
   (use its absolute path). It prints Claude Code's 5-hour and 7-day
   utilization, Cursor's Auto and named-model (API) pool, a status per pool,
   and a recommended budget mode. Show the user its first two lines.
3. Pick the budget mode: the user's words win ("balanced", "save cursor",
   "no claude"), otherwise the script's recommendation. With no reading,
   use `claude-frugal`. **The default always spares Claude**; its limits run
   out faster.
4. Start a **ledger** and keep it in your messages, updated after each phase:

```
| # | phase | provider/model (effort) | pool | taskId | result | notes |
```

Record usage-limit or rate-limit errors in `notes`. They drive escalation.

## Usage tracking

- Re-run `usage.py` (no flags; it caches for 5 minutes) **before every
  delegation to the `claude` or `cursor-api` pool**, and right after any
  usage-limit error. If a pool turned `out` or the mode changed, re-route
  and note it in the ledger.
- Never delegate to a pool reported `out`. A `tight` pool is used only when
  no cheaper step in the ladder fits.
- A usage-limit error from a child marks that pool `out` for the rest of the
  task, even if the script still says otherwise.
- At the end, run `usage.py --diff <task-slug>` and put the consumed
  percentages in the report.
- If the script fails for a pool, say so once, treat Claude as `tight` and
  Cursor named models as `tight`, and continue. Do not retry in a loop; the
  Claude endpoint rate-limits frequent reads.

## 1. Triage

Read the request and just enough of the repo to size it. Classify:

| Size | Signals | Phases |
| --- | --- | --- |
| XS | typo, config value, one obvious line | orchestrator fixes it → verify → PR |
| S | one file or one clear function, known approach | implement → light review → PR |
| M | several files, one feature, some design choice | plan → implement → review → PR |
| L | cross-cutting, new subsystem, migration, unclear approach | plan (deep) → split into slices → parallel implement → review per slice → PR(s) |

Bump one size up for **risk areas**: auth, security, permissions, payments,
data loss / migrations, concurrency, public API. Risk areas always get the
strong reviewer.

If you are on the default branch, create a feature branch before any child
edits code (`git switch -c <type>/<short-name>`).

## 2. Plan (M, L)

Follow the Plan row of the ladder for your mode. In `claude-frugal`, the
orchestrator writes a short plan itself for M tasks (≤20 lines). Otherwise
delegate with `role: "design"`,
`interactionMode: "plan"`, `isolation: "shared"`. Use the plan brief. Ask for:
approach, file-level change list, slices that can run in parallel with no
shared files, test strategy, risks, open questions.

When it returns: check the plan against the request. Put product questions
to the user in one batch. Do not re-plan to polish; a good-enough plan ships.

## 3. Implement

- **One slice:** delegate to the **implementer** tier, `role:
  "implementation"`, `isolation: "shared"` on the feature branch. The child
  commits, does not push.
- **Several independent slices (L):** one child per slice, `isolation:
  "worktree"`, all started in the same turn. Each child works on its own
  branch `<feature>/<slice>`, commits, and pushes its branch. Slices that
  share files run in sequence, not in parallel.
- Give each implementer the plan excerpt for its slice, the checks to run,
  and the definition of done.

On return, verify yourself, cheaply: `git log`/`git diff --stat`, run the
repo's typecheck/lint/tests (or the subset the child names). Do not read the
whole diff line by line; that is the reviewer's job.

**Escalation:** if a child fails, errors, hits a usage limit, or its checks
fail twice, move one step up the implementer ladder with a brief that
includes what failed and the error output. Never retry the same model on the
same failure more than once.

## 4. Review

The reviewer must be a **different model family** from the implementer.
Pick from the reviewer tier in `routing.md` (risk areas → strong reviewer).
Use `role: "review"`, read-only brief, `mode: "async"`, a fresh
`delegate_task` for every round (never `t3_thread_send`).

Handle findings like this:

- Verify each finding against the code yourself before acting. Downgrade
  rare-path, style, and small-perf items to nits.
- `blocker` / `should` you agree with → send back to the **implementer** with
  the finding text (not to the reviewer, not yourself unless trivial).
- Nits → decline in one line, list as follow-ups.
- Max 2 review rounds (3 for risk areas). Round 2 reviews only the fixes and
  open ids. Stop early on APPROVE or nits only.
- Still disputed after the budget: show both sides in 2–3 lines and let the
  user decide.

XS tasks skip review. S tasks get one light round from the cheap reviewer.

If the user says "council" or "sol loop", run that skill for this phase
instead.

## 5. PR

The orchestrator opens the PR itself (cheap tool calls, no delegate).
Follow the `file-pr` skill for title and description. Rebase on the latest
base first, push, then `pull_request_create` (it links the PR for you).

End the description with the models that did the work, from the ledger,
for example:

```
Planned with Claude Opus 5.5 (Claude Code), implemented with Composer 2.5
(Cursor), reviewed with Claude Sonnet 5.5 (Claude Code), orchestrated with
Cursor Auto in T3 Code.
```

For multiple slices: one PR per slice, opened in dependency order.

## 6. CI

Follow the `babysit-pr` skill. You, the orchestrator, own the watch:
`watch_pull_request`, then end your turn.

On a wake:

- **Failed check:** read it with `ci_logs`. Infra flake (timeout, network,
  runner died) → `ci_rerun` once. Real failure → delegate the fix to the
  **CI fixer** tier with the log excerpt, the failing command, and the
  branch. The child commits and pushes; it never watches.
- **Review-bot comments:** triage like reviewer findings (step 4). Real
  issues → implementer. False positives → reply with a reason using the
  `leaving-pr-comments` skill.
- Before you hand back or ask the user anything, `unwatch_pull_request`.

## 7. Merge

Merge only with explicit authorization in this task: the user said "merge",
"ship it", "full send", or this skill was invoked with merge permission.
Without it, stop at "ready to merge" and report. With "full stop", never
merge.

Merge gate (check right before merging, after `git fetch`): required checks
green on the latest head, no unresolved blocker/should, not BEHIND or DIRTY,
no base commits since the last green run that touch the PR's files. Then
`pull_request_merge`.

## 8. Report

Final message, short:

- PR link(s) and merge status.
- The ledger (phase → model → pool → result).
- Usage consumed by this task (`usage.py --diff`), the final budget mode,
  and any mode switches, escalations, or usage-limit hits.
- Declined findings and follow-ups.
- How the change was verified.

## Cancel and cleanup

If you replace a child or no longer need it, `task_cancel` it. Do not leave
children running when you hand back. Never use `t3_thread_interrupt` on a
child thread.
