---
name: design-pass
description: One entry point for improving how a page, component, or whole app looks and feels. Picks the right one or two installed design skills for the surface (marketing page, app UI, motion, data, mobile), audits with screenshots, implements within the project's own components and tokens, verifies with responsive-qa, and can run a multi-model taste review. Use when the user says "improve the design", "make it look less generic", "use the taste skill", "apple design this", "design pass", "polish the UI", "taste council", or names several design skills at once.
---

# Design pass

The user should not have to remember which three design skills to combine.
You pick, you stay inside the project's design system, and you prove the
result with screenshots.

## 1. Scope and surface

From the request, decide:

- **Scope:** one section, one page, one flow, or the whole app. "The entire
  app" means a page list first (`feature-audit`'s inventory script lists
  routes) and one page per step, not one giant diff.
- **Surface type** (pick one): marketing/landing, product UI (dashboards,
  forms, settings, lists, modals), motion/interaction, data display, native
  or mobile-web feel.
- **Goal words** the user used ("generic", "lackluster", "cluttered",
  "Apple-like", "loud"). Keep them; they are the acceptance criteria.

## 2. Pick at most two skills

Use the routing table in [references/routing.md](references/routing.md):
one **primary** for the surface, at most one **secondary** for a specific
gap. If the user named skills, use those and skip routing. Load only the
ones you picked. If a skill in the table is not installed, use the next one
in its row.

## 3. Learn the project's system first

Before designing anything, find and follow:

- The component library (`components/ui/`, shadcn `components.json`, a
  shared chart/table kit, Storybook). New UI reuses these; do not hand-roll
  a modal, button, or chart the project already has.
- Tokens: CSS variables, Tailwind theme, `DESIGN.md`/`AGENTS.md` notes.
- What the rest of the app looks like now, so one page does not drift.

## 4. Audit with evidence

Open the page in the preview browser (T3 `preview_*` tools, or Playwright)
at mobile (390 px) and desktop (1440 px). Capture before screenshots. List at
most 8 problems against the goal words and the chosen skill's rules, worst
first. Show the list in a few lines before large rewrites.

## 5. Implement

Change the fewest files that fix the listed problems. Keep copy, data, and
behaviour unless the user asked to change them. Respect
`prefers-reduced-motion` for any motion you add. No new dependency without
saying why.

## 6. Verify

Run the `responsive-qa` skill on every page you changed. Capture after
screenshots at the same widths. A pass is not done while responsive-qa
reports overflow, clipped content, or a Safari/WebKit break.

## 7. Taste review (optional)

Run when the user asks for a "taste council", asks several models to
evaluate the design, or the scope is a whole app. Use the `council` skill
with these changes: give each member the before/after screenshots plus the
paths of the changed files, ask for a score out of 10 against the goal words
and the primary skill's principles, and cap at 2 rounds. Members are
read-only.

## 8. Report

Per page: the skills used, the 3–5 most visible changes, and before/after
screenshots. Then what you declined or left for later.
