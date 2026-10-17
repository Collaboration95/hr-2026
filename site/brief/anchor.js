/* Deep links (#framing … #contact) land on their heading even though figures, fonts and the pinned layer stack
   change the page height after load: re-snap to the target while the layout settles, until the reader scrolls. */
(() => {
  const id = decodeURIComponent(location.hash.slice(1));
  const el = id && document.getElementById(id);
  if (!el) return;
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  let user = false;
  const stop = () => { user = true; };
  ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach(e => addEventListener(e, stop, { once: true, passive: true }));
  const snap = () => { if (!user) el.scrollIntoView({ block: 'start', behavior: 'instant' }); };
  const ro = new ResizeObserver(snap);
  ro.observe(document.body);
  addEventListener('load', () => { snap(); setTimeout(() => { snap(); ro.disconnect(); }, 3000); });
})();
