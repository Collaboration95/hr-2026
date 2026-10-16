/* Tiny SVG sprite engine for the static Plotline explainer. */
(function () {
  'use strict';
  const names = ['pip', 'stump', 'chippy', 'squish', 'lossy', 'zippy', 'hansen', 'jrc'];
  const spriteBase = new URL('./sprites/', document.currentScript.src);
  const cache = new Map(), states = new WeakMap(), reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));
  const safe = (name) => names.includes(name) ? name : '';

  async function load(name) {
    name = safe(name); if (!name) throw new Error('Unknown sprite');
    if (!cache.has(name)) cache.set(name, fetch(new URL(`${name}.svg`, spriteBase))
      .then(r => { if (!r.ok) throw new Error('Sprite unavailable'); return r.text(); })
      .then(txt => new DOMParser().parseFromString(txt, 'image/svg+xml'))
      .then(doc => { if (doc.querySelector('parsererror') || !doc.documentElement.matches('svg')) throw new Error('Invalid sprite'); return doc.documentElement; }));
    return cache.get(name);
  }
  function meta(svg) {
    const poses = [...svg.querySelectorAll(':scope > .pose[data-pose]')].map(g => g.dataset.pose);
    const desc = svg.querySelector('desc')?.textContent || '';
    const lines = {};
    for (const m of desc.matchAll(/\b([\w-]+)\s*:\s*["“]([^"”]+)["”]/g)) lines[m[1]] = m[2];
    return { poses, lines, title: svg.querySelector('title')?.textContent?.trim() || 'Forest friend' };
  }
  function state(el) {
    let s = states.get(el); if (!s) states.set(el, s = { pose: 'idle', timer: 0, base: 'idle', info: { poses: [], lines: {}, title: el.dataset.sprite || 'Forest friend' } }); return s;
  }
  function say(el, text, ms = 2400) {
    if (!el?.isConnected) return;
    let bubble = el.querySelector(':scope > .sprite-bubble');
    if (!bubble) { bubble = document.createElement('span'); bubble.className = 'sprite-bubble'; bubble.setAttribute('role', 'status'); el.append(bubble); }
    bubble.textContent = String(text); bubble.hidden = false;
    clearTimeout(state(el).sayTimer); state(el).sayTimer = setTimeout(() => { bubble.hidden = true; }, Math.max(0, Number(ms) || 0));
  }
  function pose(el, name, options = {}) {
    const s = state(el), duration = Number(options.hold) || 0;
    if (!s.info.poses.includes(name) && name !== 'idle') return;
    s.pose = name; const svg = el.querySelector('svg'); if (svg) { svg.dataset.pose = name;
      svg.querySelectorAll('.pose[data-pose]').forEach(g => { g.style.display = g.dataset.pose === name ? 'inline' : 'none'; }); }
    if (duration) { clearTimeout(s.timer); s.timer = setTimeout(() => pose(el, s.base || 'idle'), duration); }
  }
  function mount(el) {
    if (el.dataset.mounted) return;
    const name = safe(el.dataset.sprite); if (!name) return;
    el.dataset.mounted = 'loading';
    load(name).then(source => {
      if (!el.isConnected) return;
      const svg = document.importNode(source, true), s = state(el); s.info = meta(svg); s.base = el.dataset.pose || 'idle';
      svg.dataset.pose = s.base; svg.setAttribute('aria-hidden', 'true'); svg.setAttribute('focusable', 'false');
      el.style.setProperty('--sprite-size', `${Math.max(8, Math.min(512, Number(el.dataset.size) || 64))}px`);
      el.append(svg); el.dataset.mounted = 'yes';
      if (el.hasAttribute('data-click') && el.tagName !== 'BUTTON') {
        const button = document.createElement('button'); button.type = 'button'; button.className = el.className;
        [...el.attributes].filter(a => !['class','style'].includes(a.name)).forEach(a => button.setAttribute(a.name, a.value));
        button.style.cssText = el.style.cssText; button.dataset.mounted = 'yes'; button.append(...el.childNodes); el.replaceWith(button); el = button;
      }
      const now = state(el); now.info = s.info; now.base = el.dataset.pose || 'idle';
      pose(el, now.base);
      if (el.tagName === 'BUTTON') el.setAttribute('aria-label', s.info.title);
      const speakPose = p => say(el, now.info.lines[p] || now.info.lines.idle || s.info.title);
      el.addEventListener('pointerenter', () => { if (el.dataset.hover) { pose(el, el.dataset.hover); speakPose(el.dataset.hover); } });
      el.addEventListener('pointerleave', () => { if (el.dataset.hover) pose(el, now.base); });
      el.addEventListener('focus', () => { if (el.dataset.hover) pose(el, el.dataset.hover); });
      el.addEventListener('blur', () => { if (el.dataset.hover) pose(el, now.base); });
      if (el.hasAttribute('data-click')) el.addEventListener('click', () => {
        const choices = now.info.poses.filter(p => p !== 'idle'), current = choices.indexOf(now.pose);
        const p = choices[(current + 1) % Math.max(1, choices.length)] || el.dataset.click;
        pose(el, p, {hold: 2600}); speakPose(p); burst(el);
      });
      if (el.hasAttribute('data-idle-fidget') && !reduced.matches) (async () => {
        while (el.isConnected) { await wait(8000 + Math.random() * 7000); if (!el.isConnected) break;
          const choices = now.info.poses.filter(p => p !== 'idle'); if (!choices.length) continue;
          const p = choices[Math.floor(Math.random() * choices.length)]; pose(el, p, {hold: 1500});
        }
      })();
      el.dispatchEvent(new CustomEvent('sprite-ready', {bubbles:true, detail: now.info}));
    }).catch(() => { el.dataset.mounted = 'missing'; });
  }
  // Click animation: each creature moves in its own way, plus a little puff of pixel leaves.
  const moves = { pip: 'jump', stump: 'wobble', chippy: 'hop2', squish: 'squash', lossy: 'jitter', zippy: 'dash', hansen: 'tilt', jrc: 'tilt' };
  function burst(el) {
    if (reduced.matches || !el?.isConnected) return;
    const cls = 'sprite-do-' + (moves[el.dataset.sprite] || 'jump');
    el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls);
    setTimeout(() => el.classList.remove(cls), 900);
    const puff = document.createElement('span'); puff.className = 'sprite-puff'; puff.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < 8; i++) { const b = document.createElement('i'); b.style.setProperty('--a', `${i * 45 + Math.random() * 20}deg`); b.style.setProperty('--d', `${22 + Math.random() * 18}px`); puff.append(b); }
    el.append(puff); setTimeout(() => puff.remove(), 800);
  }
  function allSprites() { return [...document.querySelectorAll('.sprite[data-sprite]')]; }

  const api = window.Sprites = { pose, say, burst, companion(name) { name = safe(name); if (!name) return null;
    const old = document.querySelector('.sprite-companion'); if (old) old.remove();
    try { if (localStorage.getItem('sprite-companion-dismissed') === 'yes') return null; } catch (_) {}
    const wrap = document.createElement('div'); wrap.className = 'sprite sprite-companion'; wrap.dataset.sprite = name; wrap.dataset.size = '64'; wrap.dataset.idleFidget = '';
    wrap.setAttribute('aria-label', 'Page companion'); const close = document.createElement('button'); close.className = 'sprite-companion-close'; close.type = 'button'; close.setAttribute('aria-label','Dismiss companion'); close.textContent = '×';
    wrap.append(close); document.body.append(wrap); mount(wrap);
    close.addEventListener('click', () => { try { localStorage.setItem('sprite-companion-dismissed','yes'); } catch (_) {} wrap.remove(); });
    const sections = [...document.querySelectorAll('section')]; let last = null;
    function update() { if (reduced.matches || innerWidth < 640) return; const mid = innerHeight * .55; const cur = sections.find(x => { const r=x.getBoundingClientRect(); return r.top <= mid && r.bottom > mid; });
      if (cur && cur !== last) { last=cur; const index=sections.indexOf(cur); wrap.style.setProperty('--walk-x', `${(index % 3 - 1) * 14}px`); wrap.classList.remove('hop'); void wrap.offsetWidth; wrap.classList.add('hop');
        const line=cur.dataset.spriteSay; if(line) say(wrap,line,3600); const p=cur.dataset.spritePose; if(p) pose(wrap,p,{hold:1300}); }
    }
    addEventListener('scroll', update, {passive:true}); addEventListener('resize',update); update(); return wrap;
  }};

  let keyBuffer = '';
  document.addEventListener('keydown', e => {
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      keyBuffer = (keyBuffer + e.key.toLowerCase()).slice(-5);
      if (keyBuffer === 'forest') allSprites().forEach(el => { const s=state(el); const p=s.info.poses.includes('happy')?'happy':s.info.poses.includes('dance')?'dance':''; if(p){pose(el,p,{hold:1800});say(el,s.info.lines[p]||'A little forest magic.',1800);} });
    }
    if (e.key.toLowerCase() === 'p' && !e.ctrlKey && !e.metaKey && !e.altKey && !reduced.matches) {
      const old = document.querySelector('.sprite-leaf-field'); if (old) old.remove();
      else { const field = document.createElement('div'); field.className = 'sprite-leaf-field'; field.setAttribute('aria-hidden','true');
        for (let i=0;i<36;i++) { const leaf=document.createElement('i'); leaf.className='sprite-leaf'; leaf.style.left=`${Math.random()*100}%`; leaf.style.animationDelay=`${Math.random()*2}s`; leaf.style.animationDuration=`${3+Math.random()*3}s`; field.append(leaf); }
        document.body.append(field); setTimeout(()=>field.remove(),7000); }
    }
  });
  let scrollAt=0, scrollTime=performance.now(); addEventListener('scroll', () => {
    if (reduced.matches) return; const now=performance.now(), speed=Math.abs(scrollY-scrollAt)/Math.max(1,now-scrollTime); scrollAt=scrollY; scrollTime=now;
    if (speed > 1.2) allSprites().filter(x=>x.hasAttribute('data-scroll-react')).forEach(el=>{ const s=state(el); const p=s.info.poses.find(x=>x!=='idle'); if(p) pose(el,p,{hold:850}); });
  }, {passive:true});
  const boot = () => document.querySelectorAll('.sprite[data-sprite]').forEach(mount);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',boot); else boot();
})();
