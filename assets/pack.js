/* Plotline explainer pack: shared behaviour.
   A page sets <body data-page="slug"> and loads this file at the end of <body>.
   It adds the masthead, the table of contents (from <section id> + its first h2), the prev/next pager,
   scroll reveals, count-ups, bar fills, and a tiny "instrument" helper for animations that play on view. */
(() => {
  /* Two zones. "ext" pages live in presentation/ and hold only what the demo and slides use; they never link to "int" pages.
     "int" pages are the normal project pages at the site root and may link to the presentation pages. */
  const SITE = new URL('../', document.currentScript.src).href;
  const PAGES = [
    { slug: 'start',    zone: 'ext', path: 'presentation/start/',    title: 'Overview' },
    { slug: 'solution', zone: 'ext', path: 'presentation/solution/', title: 'How Plotline works' },
    { slug: 'speed',    zone: 'ext', path: 'presentation/speed/',    title: 'Performance' },
    { slug: 'findings', zone: 'ext', path: 'presentation/findings/', title: 'What the plots show' },
    { slug: 'event',    zone: 'int', path: 'event/',                 title: 'The event and the brief' },
    { slug: 'company',  zone: 'int', path: 'company/',               title: 'SystemEarth and the EUDR' },
    { slug: 'data',     zone: 'int', path: 'data/',                  title: 'The data' },
    { slug: 'glossary', zone: 'int', path: 'glossary/',              title: 'Glossary' },
    { slug: 'pitch',    zone: 'int', path: 'pitch/',                 title: 'Presentation guide' },
    { slug: 'submit',   zone: 'int', path: 'submit/',                title: 'Submission readiness' },
  ];
  const REDUCE = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const slug = document.body.dataset.page;
  const page = PAGES.find(p => p.slug === slug);
  const zone = PAGES.filter(p => page && p.zone === page.zone);
  const i = zone.indexOf(page);
  const hub = SITE + (page && page.zone === 'ext' ? 'presentation/' : '');

  /* masthead */
  if (slug) {
    const mast = document.createElement('div');
    mast.className = 'mast';
    mast.innerHTML = `<div class="mast-in"><a href="${hub}"><span class="dot"></span><b>Plotline</b></a>
      <span class="where">${i >= 0 ? `<span>${i + 1} / ${zone.length}</span>` : ''}<a href="${hub}">All pages ↗</a></span></div><div class="progress"></div>`;
    document.body.prepend(mast);
    const bar = $('.progress', mast);
    const prog = () => { const h = document.documentElement; bar.style.width = (100 * h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight)) + '%'; };
    addEventListener('scroll', prog, { passive: true }); prog();
  }

  /* persistent QR code on every page: it points at the presentation hub */
  const qr = document.createElement('a');
  qr.className = 'qr-fixed'; qr.href = SITE + 'presentation/'; qr.setAttribute('aria-label', 'Plotline presentation pages');
  qr.innerHTML = `<img src="${SITE}assets/qr.svg" alt="QR code for the Plotline presentation pages" width="180" height="180">`;
  document.body.append(qr);

  /* table of contents */
  const secs = $$('main section[id]').filter(s => $('h2', s));
  if (slug && secs.length > 2) {
    const toc = document.createElement('nav');
    toc.className = 'toc'; toc.setAttribute('aria-label', 'On this page');
    toc.innerHTML = '<b>On this page</b>' + secs.map(s => `<a href="#${s.id}">${s.dataset.toc || $('h2', s).textContent}</a>`).join('');
    document.body.append(toc);
    const links = $$('a', toc);
    const sync = () => { let k = 0; secs.forEach((s, j) => { if (s.getBoundingClientRect().top < 140) k = j; }); links.forEach((a, j) => a.classList.toggle('on', j === k)); };
    addEventListener('scroll', sync, { passive: true }); sync();
  }

  /* pager */
  if (i >= 0) {
    const prev = zone[i - 1], next = zone[i + 1];
    const pg = document.createElement('nav');
    pg.className = 'pager'; pg.setAttribute('aria-label', 'Pages');
    pg.innerHTML = (prev ? `<a class="prev" href="${SITE + prev.path}"><small>← Previous</small><span>${prev.title}</span></a>` : '<span></span>')
      + (next ? `<a class="next" href="${SITE + next.path}"><small>Next →</small><span>${next.title}</span></a>` : `<a class="next" href="${hub}"><small>Done →</small><span>All pages</span></a>`);
    ($('main') || document.body).append(pg);
  }

  /* count-ups: <span data-count="744732" data-dec="0" data-suffix="×"></span> */
  const fmt = (v, d) => v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
  const countUp = el => {
    const to = +el.dataset.count, d = +(el.dataset.dec || 0), suf = el.dataset.suffix || '', pre = el.dataset.prefix || '';
    if (REDUCE) { el.textContent = pre + fmt(to, d) + suf; return; }
    const t0 = performance.now(), dur = +(el.dataset.ms || 1400);
    const tick = now => { const t = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - t, 3); el.textContent = pre + fmt(to * e, d) + suf; if (t < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  };
  $$('[data-count]').forEach(el => { el.textContent = (el.dataset.prefix || '') + fmt(0, +(el.dataset.dec || 0)) + (el.dataset.suffix || ''); });

  /* reveal on view: .rv elements, [data-count], and bar fills (.track i[data-w="0-100"]) */
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return;
    const el = e.target; io.unobserve(el);
    if (el.classList.contains('rv')) el.classList.add('in');
    if (el.dataset.count) countUp(el);
    if (el.dataset.w) el.style.width = el.dataset.w + '%';
  }), { threshold: 0.25 });
  $$('.rv, [data-count], .track i[data-w]').forEach(el => io.observe(el));

  /* instrument: an animation that plays once when 40% visible; a .replay button inside restarts it.
     Pack.instrument(el, { ms: 4000, render(t) {} })  t goes 0 → 1. With reduced motion it renders t = 1. */
  const instrument = (el, { ms = 3000, render }) => {
    let raf = 0, done = false;
    const play = () => {
      cancelAnimationFrame(raf);
      if (REDUCE) { render(1); done = true; return; }
      const t0 = performance.now();
      const tick = now => { const t = Math.min(1, (now - t0) / ms); render(t); if (t < 1) raf = requestAnimationFrame(tick); else done = true; };
      raf = requestAnimationFrame(tick);
    };
    render(0);
    new IntersectionObserver((es, ob) => es.forEach(e => { if (e.intersectionRatio >= 0.4 && !done) { ob.disconnect(); play(); } }), { threshold: [0, 0.4] }).observe(el);
    $$('.replay', el).forEach(b => b.addEventListener('click', play));
    return { play };
  };

  /* stepper: Pack.stepper(el, n, show) wires .steps buttons (created here) plus optional .prev/.next buttons. */
  const stepper = (el, n, show) => {
    const box = $('.steps', el); let k = 0;
    if (box) box.innerHTML = Array.from({ length: n }, (_, j) => `<button type="button" aria-label="Step ${j + 1}">${j + 1}</button>`).join('');
    const go = j => { k = Math.max(0, Math.min(n - 1, j)); show(k); if (box) $$('button', box).forEach((b, m) => { b.classList.toggle('on', m === k); b.classList.toggle('done', m < k); }); };
    if (box) $$('button', box).forEach((b, j) => b.addEventListener('click', () => go(j)));
    $$('.prev', el).forEach(b => b.addEventListener('click', () => go(k - 1)));
    $$('.next', el).forEach(b => b.addEventListener('click', () => go(k + 1)));
    go(0);
    return { go, get step() { return k; } };
  };

  const ease = t => 1 - Math.pow(1 - t, 3);
  const seg = (t, a, b) => Math.max(0, Math.min(1, (t - a) / (b - a))); // local 0→1 progress of t within [a, b]
  window.Pack = { PAGES, REDUCE, $, $$, instrument, stepper, ease, seg, fmt };
})();
