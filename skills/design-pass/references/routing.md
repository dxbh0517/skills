# Design skill routing

Pick one **primary** for the surface and at most one **secondary** for a
specific gap. Names refer to skills you may have installed from other
collections. If the first choice in a cell is missing, use the next.

| Surface | Primary | Good secondary |
| --- | --- | --- |
| Marketing / landing page, "looks generic", "AI slop" | `design-taste-frontend` → `high-end-visual-design` → `impeccable` | `animate` for one hero moment |
| Redesign of an existing site | `redesign-existing-projects` → `impeccable` | `design-taste-frontend` |
| Product UI: dashboards, settings, lists, forms, modals | `impeccable` → `ui-ux-pro-max` | `emil-design-eng` for polish |
| "Apple-like", native feel, sheets, gestures, springs, materials | `apple-design` | `emil-design-eng` |
| Small-detail polish: buttons, inputs, toasts, empty states | `emil-design-eng` | `impeccable` |
| Motion: transitions, page transitions, scroll stories | `animate` (new) / `review-animations` (critique) / `improve-animations` (whole codebase) | `apple-design` |
| Charts, KPIs, tables of numbers | `dataviz` | `impeccable` |
| Mobile app (React Native / Expo) | `animate-expo` for motion, `apple-design` for feel | — |
| Distinct style asked by name | `minimalist-ui`, `industrial-brutalist-ui`, `stitch-design-taste` | `impeccable` |

## Signals in the request

- Names a skill → use it; route only the remaining gap.
- "Taste", "taste skill" → `design-taste-frontend`.
- "Lackluster animation", "animation for the sake of it" → `review-animations`
  first; remove before adding.
- "Overflowing", "not fully visible", "cut off on mobile" → this is a bug,
  not taste: run `responsive-qa` first, then design.

## Conflicts

When two skills disagree (for example dense dashboard vs. generous
whitespace), the primary wins for its surface, and the project's existing
design system beats both.
