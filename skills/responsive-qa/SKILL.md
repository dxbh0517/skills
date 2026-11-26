---
name: responsive-qa
description: Prove a UI change works on phone, tablet, and desktop and in Safari/WebKit before calling it fixed — measures horizontal overflow, clipped or off-screen content, modals taller than the viewport, unwrapped long text, sticky/fixed bars, tap-target size, and WebKit-only breaks such as backdrop-filter, and checks the change reuses the project's own components. Use after any UI change, and when the user reports "overflowing", "not fully visible", "cut off", "covering", "doesn't extend to the top", "broken on mobile", or "still showing on Safari".
---

# Responsive QA

"Fixed" means measured, not eyeballed at one width. Run this before telling
the user a layout bug is fixed or a UI change is done.

## 1. Targets

- The pages the change touches (and the page the user reported, by URL).
- Widths: **390×844** (phone), **768×1024** (tablet), **1440×900**
  (desktop). Add **360** when the user reported a mobile bug.
- Engines: Chromium plus **WebKit** whenever the user mentioned Safari or
  iOS, or the change touches `backdrop-filter`, `position: sticky`, viewport
  units, `mask`, or scroll snapping.
- States that matter: open modal/sheet, long content (longest real title in
  the data), empty state, logged-in vs. logged-out if both render the page.

## 2. Measure in the browser

For each page × width: open it in the preview browser (T3 `preview_open`,
`preview_resize`; or Playwright), wait for content, then evaluate
[scripts/layout-check.js](scripts/layout-check.js) with `preview_evaluate`
(paste the file's contents as the expression). It returns JSON:

- `overflowX` — page wider than the viewport, and the elements causing it.
- `offscreen` — visible elements cut off by the viewport edge.
- `clipped` — elements whose content is cut off by `overflow: hidden`
  (truncated text, cropped images) without an ellipsis.
- `tallDialogs` — dialogs/sheets taller than the viewport with no scrolling.
- `smallTargets` — buttons and links under 44×44 px on touch widths.
- `stickyGaps` — sticky/fixed bars that do not reach the edge they stick to.

Take a screenshot at each width as evidence. Read the screenshot too: the
script misses overlap and z-index problems a look catches immediately.

## 3. WebKit check

If Playwright is available:

```bash
npx playwright install webkit   # once
npx playwright screenshot --browser=webkit --viewport-size="390,844" --full-page <url> /tmp/<page>-webkit-390.png
```

Compare with the Chromium shot. If WebKit cannot run on this machine, say
so and review the CSS for the known breaks in
[references/webkit.md](references/webkit.md) instead. Never claim Safari is
fixed without either a WebKit screenshot or that review.

## 4. Component and token check

On the diff (`git diff <base>...HEAD -- '*.tsx' '*.jsx' '*.vue' '*.svelte' '*.astro' '*.css'`):

- New modal, dialog, sheet, button, input, select, table, chart, or toast
  markup where the project already has one in `components/ui/` (shadcn) or
  its shared kit → replace it with the existing component.
- Hard-coded colors, radii, or shadows where tokens exist → use the tokens.

## 5. Fix loop

Fix what the checks found, then re-run only the failing page × width. Common
fixes: `min-width: 0` on flex/grid children, `overflow-wrap: anywhere` on
user titles, `max-height: 100dvh` plus internal scroll on dialogs,
`object-fit: contain` when the whole image must show, removing a fixed width.

## 6. Report

A small table: page × width × engine → pass, or the issue and the fix.
Attach the after screenshots for the pages the user reported. State plainly
anything you could not test (for example WebKit unavailable).
