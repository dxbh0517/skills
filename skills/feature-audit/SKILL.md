---
name: feature-audit
description: Go through every feature of an app and check that each one actually works end to end — builds an inventory from routes, API handlers, jobs, and the database schema, tests each feature in the browser or against the API, and returns a pass/broken/partial table with evidence, fixing small breaks along the way. Use when the user says "re-evaluate all the features", "make sure each feature is working as intended", "audit the app", "check everything works", "what's broken", or reports that several features silently stopped working ("no recommendations", "suggestions not visible anywhere", "stats page no longer loads").
---

# Feature audit

The goal is a trustworthy answer to "does everything work?", not a code
review. Every row in the result has evidence: a screenshot, a response, or a
query result.

## 1. Inventory

```bash
python3 <this skill>/scripts/inventory.py [app_dir]          # Markdown table
python3 <this skill>/scripts/inventory.py [app_dir] --json
```

It lists page routes and API endpoints (Next.js app and pages routers,
Astro, SvelteKit, Remix/React Router file routes, Express/Hono/Fastify
handlers found by pattern), cron and background jobs (`vercel.json` crons,
queue workers), and database tables (Prisma models, SQL `CREATE TABLE`,
Drizzle tables).

Group the output into **features** a user would name ("barcode scan",
"recommendations", "admin: upgrade user", "price alerts"), not files. Add
features from the README, nav, settings pages, and admin tools that the
scanner cannot see. Write the inventory to `docs/feature-audit.md` (or the
scratchpad if the user does not want it in the repo) with one row per
feature: name, entry point, data it needs, roles that can use it.

## 2. Plan the checks

For each feature pick the cheapest check that proves it works for a real
user:

- **UI flow:** open the page in the preview browser, perform the action,
  confirm the visible result. Use a test account; ask for one if login is
  needed and none exists.
- **API:** call the endpoint with realistic input; check status and shape.
- **Data:** read-only SQL to confirm the feature has data to show
  (recommendations need rows; a stats page needs aggregates). Empty data is
  a finding, not a pass.
- **Jobs:** last run time and result from logs or the jobs table.
- **Roles:** an admin-only action must fail for a normal user.

Never write to production data to test. Use preview/staging or a local
database. Ask before testing anything that sends email, charges money, or
posts publicly.

## 3. Run

Large apps: split by area (auth, core, admin, billing, integrations) and run
areas in parallel. Under `conductor`, delegate one area per child with the
inventory rows and the rules above; children are read-only except for the
audit file.

Status per feature:

- **pass** — works with evidence.
- **broken** — errors, wrong result, or the UI never appears.
- **partial** — works for some inputs, roles, or screen sizes.
- **no data** — code works but nothing to show (missing job, empty table,
  unlinked external IDs).
- **untested** — could not test; say why.

## 4. Fix

Default: fix **small** breaks (one or two files, clear cause) during the
audit, re-test, and mark them `fixed`. List larger ones with cause and a
suggested fix, and ask which to take on. If the user said "fix everything",
fix all of them, one commit per feature. Use `responsive-qa` for any UI fix
and `ship` if the user wants it merged.

## 5. Report

The table first, worst status first:

| Feature | Status | Evidence | Cause / fix |
| --- | --- | --- | --- |

Then: what was fixed, what needs a decision, and what could not be tested.
Keep the audit file updated so a later audit can diff against it.
