# Brief templates

Children start with no history. Fill every `<...>`. Keep briefs short; point
at files instead of pasting them. Never put secrets in a brief.

## Plan

```
Plan only. Do not edit files, commit, or start subagents.
Repo: <abs path>  Branch: <branch>  Base: <sha>
Goal: <user request in 1-3 sentences, plus any decisions already made>
Constraints: <stack, conventions, things not to touch>
Start from: <files / dirs that matter>
Reply with:
1. Approach (≤10 lines) and why over the main alternative.
2. Change list: file -> what changes.
3. Slices: groups of changes that can be built in parallel with NO shared
   files, in dependency order. Mark which slices can run at the same time.
4. Tests: what proves it works (commands, new tests).
5. Risks and open questions for the user (product decisions only).
```

## Implement

```
Implement this slice. Do not open a PR, watch CI, merge, or start subagents.
Repo: <abs path>  Branch: <branch>  (worktree slice: create/switch to <branch>)
Goal: <slice goal>
Plan: <plan excerpt for this slice>
Files: <expected files>   Out of scope: <what not to touch>
Done when: <checks pass: exact commands>, plus <behavior>.
Make the smallest change that meets the goal. Follow existing patterns.
Commit with a clear message. <shared: do not push | worktree: push the branch>
Reply with: commit SHA(s), files changed, check commands run and their result,
anything you could not do and why.
```

## Escalated implement (after a failure)

Same as Implement, plus:

```
A previous attempt failed. What happened: <summary>
Error / failing output: <trimmed excerpt>
Current state of the branch: <sha, what is committed>
Fix the failure first; keep what already works.
```

## Review

```
Review only. Do not edit, commit, push, comment on PRs, or start subagents.
Repo: <abs path>  Base: <base sha>  Head: <branch or sha>
Intent: <what the change should do>  Out of scope: <...>
Checks: <commands run and results>
Diff: git diff <base>...<head> [-- <paths>]. Read surrounding code and callers.
Find bugs, broken callers, security issues, and mismatches with the intent.
Skip style unless it hides a bug. Flag code the intent does not need.
blocker = intended case is wrong. should = real bug callers will hit. nit = rest.
Reply:
VERDICT: APPROVE or CHANGES
R1 [blocker|should|nit] <file>:<line> <claim>. Fix: <suggestion>
```

Round 2+: add the ledger (`fixed:` / `disagree: <evidence>` / `declined:`)
and "Check only the open ids and the code changed since <sha>. Mark each old
id resolved or still open: <reason>."

## CI fix

```
Fix a failing CI check. Do not open PRs, watch CI, merge, or start subagents.
Repo: <abs path>  Branch: <branch> (PR <url>)
Failing check: <name>  Command it runs: <cmd if known>
Log excerpt: <trimmed, the real error lines>
Reproduce locally if possible, make the smallest fix, run the same command,
commit, and push the branch.
Reply with: root cause in one line, commit SHA, local command result.
```
