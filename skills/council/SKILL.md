---
name: council
description: Run a multi-model council — several models from different families review or critique the same work in parallel, score it out of 10, and the findings get fixed in bounded rounds. Use when the user says "council", "run the council", "council review", or asks several models to review, score, or critique code, a plan, a design, or a document.
---

# Council

Several models review the same work in parallel. You collect, verify, fix,
and re-review — in **bounded** rounds. A council that runs to round 14 has
failed; stop rules below are part of the job.

## 0. Before round 1

Address outstanding PR comments, fix known issues, and run the relevant
checks first. Give the council the current implementation, not one you
already know is wrong. If the user wants to discard the implementation and
explore new ideas, skip fixes to code being replaced.

## 1. Members

If the user names members, use those. Otherwise use the default council in
[references/members.md](references/members.md). Edit that file to change
your defaults. One model per member, high reasoning effort where supported.

In T3 Code: `orchestrator_capabilities` once, then one `delegate_task` per
member in parallel (`mode: "async"`, a fresh task every round, never
`t3_thread_send`). Elsewhere use the harness's subagent tools. If a member is
unavailable, report it instead of substituting (except the free-model retry
in `members.md`).

## 2. The brief (write once, reuse)

Write the brief to a file in the scratchpad and pass its path; every round
reuses it. Contents:

- Goal and what "good" means for this work, in the user's words.
- Absolute repo path, branch, base, and how to see the change
  (`git diff <base>...HEAD`), or the document path.
- Read-only: no edits, commits, pushes, PRs, or deploys.
- Output format: a score `N/10`, then findings, each tagged **blocker**
  (wrong or broken in the intended use), **should** (clear improvement worth
  doing now), or **nit**, with file:line and one sentence of evidence. At
  most 10 findings, most severe first. No patches.
- Scope fence: "Judge the stated goal. Do not ask for new features."

## 3. Rounds

**Round 1:** full review by every member.

**Round 2+ (delta reviews):** each member gets the brief path, its own
previous findings, and the diff since the last round (`git diff <last-round-sha>..HEAD`).
Ask only: which prior findings are fixed, and any **new blocker** the fixes
introduced. Do not ask for a fresh full review.

Between rounds, verify each finding against the source yourself. Fix agreed
blockers and shoulds. Decline nits and scope creep in one line each and list
them as follow-ups. A finding raised by only one member that you can't
reproduce is declined with a reason, not fixed to placate.

## 4. Stop rules

Stop at the first that applies:

1. **Target met:** every member scores ≥ the target and has no open blocker.
   Default target 8/10; the user's number overrides ("until 9/10").
2. **Only nits left** across all members.
3. **Plateau:** the average score rose by less than 0.5 since the previous
   round, or the same finding survived two fix attempts.
4. **Round cap:** 3 rounds by default, 5 when the user set a score target.
   The user can raise it explicitly.

When stopping on 3 or 4 with the target unmet, do not start another round.
Report the scores, the open disagreements in 2–3 lines each, and let the
user decide.

## 5. Failures and cost

- **Rate limit / usage limit:** retry that member once in the same round; if
  it fails again, mark it `skipped (limit)` and continue with the rest. Never
  hold the round for it, and do not let retries count as extra rounds.
- **Frugal mode** (default when Claude or another paid pool is tight, or the
  user says "frugal"): expensive members join round 1 and the final
  confirmation only; cheap and local members cover the middle rounds.
- A member that returns no score is `no score`. Never invent one.

## 6. Report

If the work ends in a pull request, put the results in the PR description,
before the model and harness line at the end. Edit the description; do not
post a comment.

```markdown
## Council review

Rounds: 2 (stopped: target met)

| Delegate | Round 1 | Round 2 |
| --- | --- | --- |
| Claude Opus 5.5 | 7/10 | 9/10 |
| Grok 4.7 | 8/10 | 9/10 |
| OpenRouter Free | 7/10 | skipped (limit) |
| vLLM Auto (local) | 6/10 | 8/10 |

Declined: <one line each>. Follow-ups: <list>.
```

No PR → the same block in the final reply only. Always state why the council
stopped.
