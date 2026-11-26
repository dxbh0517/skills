# Known Safari / WebKit breaks

Check the changed CSS for these when a WebKit screenshot isn't possible.

| Symptom | Cause | Fix |
| --- | --- | --- |
| Frosted/blur effect missing, or a gradient overlay shows where blur should be | `backdrop-filter` without `-webkit-backdrop-filter` (Safari < 18), or blur on an element with `overflow: hidden` + `border-radius` | Add `-webkit-backdrop-filter`; test the fallback background; avoid stacking a gradient that only exists for the blur. Tailwind's `backdrop-blur-*` emits both. |
| Blur/fade "stuck" on cards after an animation | `will-change`/`transform` creating a layer that keeps the filter | Remove `will-change` after the animation; avoid animating `backdrop-filter`. |
| Sticky header or sidebar does not stick, or stops early | An ancestor has `overflow: hidden/auto`, or the sticky element is in a flex child with no height | Remove ancestor overflow (use `overflow: clip` instead), set `align-self: start` on the sticky child. |
| Bar does not extend to the top behind the status bar / header | Missing `top: 0` with safe area, or a parent's padding | Use `top: 0`, `padding-top: env(safe-area-inset-top)`, `viewport-fit=cover` in the viewport meta. |
| Layout jumps or is cut off at the bottom on iPhone | `100vh` includes the hidden URL bar | Use `100dvh` (or `100svh`) with a `100vh` fallback. |
| Inputs zoom the page on focus | Font size below 16 px on inputs | `font-size: 16px` (or larger) on inputs on touch widths. |
| Masks/fades not applied | `mask-image` without `-webkit-mask-image` (older Safari) | Add the prefixed property. |
| Gap missing in flex rows | Very old Safari (< 14.1) | Usually ignore now; use margins only if analytics show those versions. |
| Smooth scroll / scroll-snap jitter | `scroll-behavior` + snap on the root in iOS | Snap on an inner container, not `html`. |
| Date or select controls look unstyled | Native WebKit appearance | `appearance: none` plus the project's styled component. |
