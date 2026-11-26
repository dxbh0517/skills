# `.ship.md` format

A short Markdown file at the repo root. Agents read it top to bottom. Keep
each step to one line of intent, the command, and how to verify it.

```markdown
# Ship

## Before PR
- `pnpm -C web lint && pnpm -C web typecheck && pnpm -C web test`
- Never include: `docs/local-models/**`, `skills/**`

## After merge
1. Deploy: Vercel deploys `main` automatically (project `web`).
   Verify the production deployment for the merge SHA is READY.
2. Migration (only if `web/prisma/migrations/` changed):
   `pnpm -C web prisma migrate deploy`
   Database: Neon (host ends in `.neon.tech`). Stop if DATABASE_URL points elsewhere.
3. Local instance: `cd ~/apps/myapp && git pull && docker compose up -d --build api`
   Verify `docker compose ps api` shows healthy.
4. Upstream: push to `fork-feature` so upstream PR #12 updates.

## Never
- Run `prisma migrate reset` or `db push --accept-data-loss` against production.
- Submit to the App Store without asking.
```

## Notes

- Write steps as the user would say them. "Update the local switchyard
  container" is better than a bare command with no context.
- Name the database **provider** next to every migration step. The detector
  prints the provider each env var points to; a mismatch is the most common
  shipping mistake.
- Conditional steps ("only if X changed") save time: check the merged diff
  before running them.
- Paths in the ship file may be machine-specific. That is fine for a private
  repo; for a public repo, add `.ship.md` to `.gitignore` or keep paths
  relative.
