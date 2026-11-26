// Layout check for the current page. Paste as a browser expression
// (T3 preview_evaluate, Playwright page.evaluate, or DevTools console).
// Returns a JSON-serialisable summary; reads the DOM only, changes nothing.
(() => {
  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;
  const touch = vw <= 1024;
  const MAX = 12;
  const describe = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += "#" + el.id;
    const cls = typeof el.className === "string" ? el.className.trim().split(/\s+/).slice(0, 3) : [];
    if (cls.length && cls[0]) s += "." + cls.join(".");
    const text = (el.innerText || el.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ");
    return text ? `${s} "${text.slice(0, 40)}"` : s;
  };
  const visible = (el) => {
    const st = getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden" || Number(st.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const all = Array.from(document.body.querySelectorAll("*")).filter(visible);

  // Horizontal overflow and its culprits (deepest elements past the right edge).
  const docW = document.documentElement.scrollWidth;
  const wide = all.filter((el) => {
    const r = el.getBoundingClientRect();
    return r.right > vw + 1 || r.left < -1;
  });
  const culprits = wide.filter((el) => !wide.some((o) => o !== el && el.contains(o)));
  const insideScroller = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === "auto" || ox === "scroll" || ox === "hidden" || ox === "clip") return true;
    }
    return false;
  };
  const offscreen = culprits.filter((el) => !insideScroller(el)).slice(0, MAX).map((el) => {
    const r = el.getBoundingClientRect();
    return { el: describe(el), left: Math.round(r.left), right: Math.round(r.right) };
  });

  // Content clipped by overflow hidden without ellipsis.
  const clipped = all.filter((el) => {
    const st = getComputedStyle(el);
    if (!/(hidden|clip)/.test(st.overflow + st.overflowX + st.overflowY)) return false;
    if (st.textOverflow === "ellipsis" || st.webkitLineClamp !== "none" && st.webkitLineClamp) return false;
    const textish = el.children.length === 0 && (el.innerText || "").trim().length > 0;
    const img = el.querySelector(":scope > img, :scope > video");
    const cutText = textish && (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2);
    const cutImg = img && getComputedStyle(img).objectFit === "cover" && el.dataset.cropOk === undefined
      && img.naturalWidth && Math.abs(img.naturalWidth / img.naturalHeight - el.clientWidth / el.clientHeight) > 0.35;
    return cutText || cutImg;
  }).slice(0, MAX).map((el) => ({ el: describe(el), scroll: [el.scrollWidth, el.scrollHeight], box: [el.clientWidth, el.clientHeight] }));

  // Dialogs taller than the viewport that cannot scroll.
  const dialogs = Array.from(document.querySelectorAll('dialog[open], [role="dialog"], [role="alertdialog"], [data-state="open"][data-radix-dialog-content], [data-vaul-drawer]')).filter(visible);
  const tallDialogs = dialogs.filter((d) => {
    const r = d.getBoundingClientRect();
    const scrolls = (n) => /(auto|scroll)/.test(getComputedStyle(n).overflowY) && n.scrollHeight > n.clientHeight;
    const canScroll = scrolls(d) || Array.from(d.querySelectorAll("*")).some(scrolls);
    return (r.bottom > vh + 1 || r.top < -1 || r.right > vw + 1) && !canScroll;
  }).map((d) => { const r = d.getBoundingClientRect(); return { el: describe(d), top: Math.round(r.top), bottom: Math.round(r.bottom), height: Math.round(r.height), viewport: vh }; });

  // Small tap targets on touch widths.
  const smallTargets = touch ? Array.from(document.querySelectorAll('a[href], button, [role="button"], input:not([type="hidden"]), select, summary'))
    .filter(visible).filter((el) => { const r = el.getBoundingClientRect(); return r.width < 44 && r.height < 44; })
    .slice(0, MAX).map((el) => { const r = el.getBoundingClientRect(); return { el: describe(el), size: [Math.round(r.width), Math.round(r.height)] }; }) : [];

  // Sticky / fixed bars that do not reach their edge.
  const stickyGaps = all.filter((el) => /(sticky|fixed)/.test(getComputedStyle(el).position)).map((el) => {
    const st = getComputedStyle(el); const r = el.getBoundingClientRect();
    const wantsTop = st.top !== "auto" && parseFloat(st.top) === 0;
    const fullWidth = r.width >= vw - 2;
    const gapTop = wantsTop && r.top > 1 && r.top < 200 ? Math.round(r.top) : 0;
    const gapSides = fullWidth || r.width < vw * 0.8 ? 0 : Math.round(vw - r.width);
    return { el: describe(el), gapTop, gapSides };
  }).filter((g) => g.gapTop || g.gapSides).slice(0, MAX);

  const result = {
    url: location.pathname,
    viewport: [vw, vh],
    overflowX: docW > vw + 1 ? { docWidth: docW, culprits: culprits.slice(0, MAX).map(describe) } : null,
    offscreen, clipped, tallDialogs, smallTargets, stickyGaps,
  };
  result.pass = !result.overflowX && !offscreen.length && !clipped.length && !tallDialogs.length && !stickyGaps.length;
  return JSON.stringify(result);
})()
