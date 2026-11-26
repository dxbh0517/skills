---
name: ship
description: Take finished work all the way out — open the PR, get checks green, merge, then run the repo's post-merge steps (deploy, database migration on the right database, update the local instance or container, sync an upstream PR, cut an app build) and verify each one. Use when the user says "ship it", "create a PR and merge it", "PR and merge if checks pass", "merge and deploy", "merge and update the local version", "push the migration", or "redeploy". Not for multi-model orchestration (use conductor).
---

# Ship

One request, one finished outcome: merged **and** live where it needs to be.
The user should not have to send "now redeploy", "now push the migration",
"now update the local container" as follow-ups.

If `conductor` is already running this task, it owns the PR; use only the
post-merge part of this skill (step 5) after its merge.

"full stop" → stop at the merge gate, PR ready and unmerged, no post-merge
steps. Otherwise invoking this skill authorizes the merge once the gate passes.

## 1. Read the ship file

Look for `.ship.md` at the repo root. It lists the checks to run before the
PR, the ordered post-merge steps, and things never to do. Format and an
example: [references/shipfile.md](references/shipfile.md).

No ship file → run the detector and propose one:

```bash
python3 <this skill>/scripts/detect.py            # human summary
python3 <this skill>/scripts/detect.py --json     # machine-readable
```

It finds deploy targets (Vercel, Netlify, Fly, Railway, Cloudflare), migration
tools (Prisma, Drizzle, Supabase, Alembic, Knex), which database provider each
`DATABASE_URL`-style variable points at (provider and host only, never
credentials), compose files and matching running containers, a fork's
`upstream` remote, and iOS/Android release config. Show the proposed
`.ship.md` in one block, use it for this run, and ask once at the end whether
to commit it. Do not block the ship on that answer.

## 2. Pre-flight

1. `git fetch`; rebase the branch on the latest base. Never ship from the
   default branch — branch first.
2. Read the full diff against the base. It must match the user's goal; drop
   stray files (local model docs, scratch, secrets, `.env*`) the user did not
   mean to ship. If the user said what to exclude, check that explicitly.
3. Run the ship file's pre-PR checks (else the repo's lint, typecheck, test,
   build — whatever `package.json`/`Makefile`/CI config runs). Fix real
   failures before opening the PR.
4. If the change includes a migration, confirm the migration files are
   committed and generated from the current schema.

## 3. PR

Follow the `file-pr` skill if installed (title from repo conventions, problem
first, model and harness line at the end). Reuse an existing PR for the
branch. In T3 Code use `pull_request_create`.

## 4. Green and merge

Handle what is already known (failed checks, conflicts, open review threads),
then wait with one watcher (`watch_pull_request` in T3 Code; `babysit-pr`'s
`pr-wait` elsewhere) and end the turn. On every wake follow the `pr-triage`
skill: preview-deploy bot comments are not events; failed checks, conflicts,
and real review findings are.

Merge gate, checked right after `git fetch`: required checks green on the
latest head, no unresolved real findings, not BEHIND or DIRTY, no base commits
since the last green run touching the PR's files. Then merge with the repo's
usual method. Never bypass protection.

## 5. Post-merge steps

Run the ship file's "After merge" steps **in order**, each with its
verification. Defaults when the ship file is silent:

| Step | Do | Verify |
| --- | --- | --- |
| Deploy | If the host deploys `main` on push, do not deploy by hand. Otherwise run the documented deploy command. | The production deployment for the **merge commit SHA** is `READY` (Vercel MCP `list_deployments`/`get_deployment`, or `vercel ls`, or the host's CLI). On failure, read the build log, fix forward in a new PR. |
| Migration | Run the migrate-deploy command (`prisma migrate deploy`, `drizzle-kit migrate`, `supabase db push`, `alembic upgrade head`) against production. | **Before running**, run `detect.py` and confirm the target provider and host match what the ship file says (e.g. Neon, not Railway). Mismatch → stop and ask. After: the migrations table lists the new migration. |
| Local instance | `git pull` in the local checkout the ship file names, then rebuild/restart (`docker compose up -d --build <service>` or the listed command). | Container is `running`/`healthy` and reports the new version or commit. |
| Upstream PR | For forks: push the merged change to the branch behind the upstream PR, or open one if the ship file says so. | The upstream PR shows the new commits. |
| App build | Trigger the listed build (Codemagic, fastlane, EAS). | Build started and its ID/link is reported. Do not wait for store review. |

Production data changes, destructive migrations (drops, column removals with
data), and store submissions need the user's go-ahead unless the ship file or
the request grants it.

## 6. Report

Short: PR link and merged SHA, then one line per post-merge step with its
result and evidence (deployment URL, migration name, container status, build
link). List anything skipped and why. If you created or changed `.ship.md`,
say so.
