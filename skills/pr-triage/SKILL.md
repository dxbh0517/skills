---
name: pr-triage
description: Decide in one step what a pull-request wake-up needs — nothing (deploy-preview bot comments, duplicate or stale events), a CI fix, a rebase, a review-finding fix, or the merge — and act without spending tokens on noise. Use whenever a PR watcher wakes you ("Update on pull request #N…", "checks failed", "conflicts with its base branch", "new comment"), and inside ship, conductor, or babysit-pr loops.
---

# PR triage

Most PR wake-ups are noise. A Vercel preview comment is not news. Handle each
wake in this order and stop at the first match. Do not re-read the diff,
re-summarize the PR, or post "still waiting" for noise.

## 1. Classify the event

| Event | Class |
| --- | --- |
| Comment from a deploy-preview bot: `vercel`, `netlify`, `cloudflare-pages` / `cloudflare-workers-and-pages`, `railway-app`, `render`, `fly-io`, `github-actions` deploy summaries, `[vc]:` payloads, "Preview deployment ready/updated" | **noise** |
| Comment from `codecov`, `changeset-bot`, `sonarcloud` summary, `dependabot` notices, bundle-size or Lighthouse bots, unless they report a **failure** that blocks merge | **noise** |
| Same event already handled (same SHA, same check, same comment id) | **noise** |
| Event about an older SHA than the current head | **noise** |
| Required check failed on the head SHA | **ci-fail** |
| Conflicts with base / BEHIND / DIRTY | **rebase** |
| Review-bot finding (CodeRabbit, Greptile, Macroscope, Copilot, Cursor Bugbot, Claude) or human comment/review | **finding** |
| All required checks passed on the head SHA | **green** |
| PR merged or closed | **done** |

A deploy-preview comment that says the **deployment failed** is **ci-fail**,
not noise. Read its build log through the host (Vercel MCP
`get_deployment` + build logs, or `vercel inspect --logs`).

A wake can carry several events. Handle the highest-impact one first:
done > rebase > ci-fail > finding > green > noise.

## 2. Act

- **noise** → if the PR is still yours to watch, re-arm the watcher
  (`watch_pull_request` in T3 Code; leave `pr-wait` running elsewhere) and end
  the turn **with no message**. Nothing else: no file reads, no summaries.
- **ci-fail** → read only the failing job's log (`ci_logs`, or
  `gh run view <id> --log-failed`). Infra flake (runner died, network, 5xx,
  timeout with no test failure, rate limit) → rerun once (`ci_rerun`). Second
  identical failure or a real error → fix it on the branch (or delegate, under
  conductor), push, watch again.
- **rebase** → `git fetch`, rebase onto the base, resolve, run the checks the
  conflict touched, `git push --force-with-lease` to this PR's branch only,
  watch again.
- **finding** → verify against the source before changing anything. Real bug
  in the intended path → fix. Otherwise reply with a short reason (use
  `leaving-pr-comments` if installed) and resolve. Keep scope: decline
  speculative edge cases, extra tests, and refactors as follow-ups.
- **green** → if merging was authorized (ship, conductor, "merge it", "full
  send"), run the merge gate: `git fetch`, head unchanged, not BEHIND/DIRTY,
  no unresolved real findings, review bots finished. Then merge. If not
  authorized, `unwatch_pull_request` and report "ready" in one line.
- **done** → stop. Run post-merge steps if `ship` is driving.

## 3. Cut the noise at the source (once per repo)

If deploy-preview comments keep waking you, tell the user once (do not change
settings without asking):

- **Vercel:** turn off pull-request comments for the project in the Vercel
  dashboard's Git settings. Previews still deploy and still report as a
  GitHub check, which is the signal that matters.
- **Netlify / Cloudflare:** disable deploy-preview comments in the site's
  build or Git settings; keep the commit status.

Verify the current option name in the host's docs before giving steps; these
settings move.

## Rules

- One watcher per PR. Children never watch.
- Never sleep, poll, or loop on `gh pr checks --watch`.
- Never merge on a stale head or with `--admin`.
