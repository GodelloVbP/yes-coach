/* Yes Coach! languages. The app is written in English; this file shows it in the language a person chose.
   It translates what is on screen (text and a few attributes) from a dictionary per language in i18n/<code>.json,
   so the app's own logic never sees a translated word. Dates come from the browser (Intl). */
(() => {
  'use strict';
  const LANGS = [['nl', 'Nederlands', 'Dutch'], ['en', 'English', 'English'], ['es', 'Español', 'Spanish'], ['de', 'Deutsch', 'German'], ['fr', 'Français', 'French'], ['it', 'Italiano', 'Italian']];
  const KEY = 'yc-lang';
  const store = {
    get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } },
    set(v) { try { localStorage.setItem(KEY, v); } catch (e) { /* private mode: the choice lasts until the page closes */ } },
  };
  // small inline flags (emoji flags do not show on Windows)
  const NS = 'http://www.w3.org/2000/svg';
  const FLAGS = {
    nl: [['#AE1C28', 0, 0, 60, 14], ['#FFFFFF', 0, 14, 60, 13], ['#21468B', 0, 27, 60, 13]],
    de: [['#000000', 0, 0, 60, 14], ['#DD0000', 0, 14, 60, 13], ['#FFCE00', 0, 27, 60, 13]],
    fr: [['#0055A4', 0, 0, 20, 40], ['#FFFFFF', 20, 0, 20, 40], ['#EF4135', 40, 0, 20, 40]],
    it: [['#009246', 0, 0, 20, 40], ['#FFFFFF', 20, 0, 20, 40], ['#CE2B37', 40, 0, 20, 40]],
    es: [['#AA151B', 0, 0, 60, 10], ['#F1BF00', 0, 10, 60, 20], ['#AA151B', 0, 30, 60, 10]],
  };
  const flag = (code) => {
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 60 40');
    svg.setAttribute('width', '27');
    svg.setAttribute('height', '18');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    svg.setAttribute('class', 'flag');
    const add = (tag, attrs) => { const e = document.createElementNS(NS, tag); Object.keys(attrs).forEach((k) => e.setAttribute(k, attrs[k])); svg.append(e); };
    if (code === 'en') {
      add('rect', { width: 60, height: 40, fill: '#012169' });
      add('path', { d: 'M0 0L60 40M60 0L0 40', stroke: '#FFFFFF', 'stroke-width': 7 });
      add('path', { d: 'M0 0L60 40M60 0L0 40', stroke: '#C8102E', 'stroke-width': 2.5 });
      add('path', { d: 'M30 0V40M0 20H60', stroke: '#FFFFFF', 'stroke-width': 11 });
      add('path', { d: 'M30 0V40M0 20H60', stroke: '#C8102E', 'stroke-width': 6.5 });
    } else (FLAGS[code] || []).forEach(([fill, x, y, w, h]) => add('rect', { x, y, width: w, height: h, fill }));
    add('rect', { x: 0.5, y: 0.5, width: 59, height: 39, fill: 'none', stroke: 'rgba(0,0,0,.3)', 'stroke-width': 1 });
    return svg;
  };

  const valid = (c) => LANGS.some((l) => l[0] === c);
  let lang = store.get();
  if (!valid(lang)) lang = null;
  const chosen = lang;
  if (!lang) lang = 'en';
  document.documentElement.lang = lang;

  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  let dayNames = {};
  let monthNames = {};
  const initDates = () => {
    dayNames = {}; monthNames = {};
    if (lang === 'en') return;
    const clean = (s) => s.replace(/\.$/, '');
    try {
      const wd = new Intl.DateTimeFormat(lang, { weekday: 'short', timeZone: 'UTC' });
      const mo = new Intl.DateTimeFormat(lang, { month: 'short', timeZone: 'UTC' });
      DAYS.forEach((d, i) => { dayNames[d] = clean(wd.format(Date.UTC(2026, 0, 5 + i))); });
      MONTHS.forEach((m, i) => { monthNames[m] = clean(mo.format(Date.UTC(2026, i, 15))); });
    } catch (e) { dayNames = {}; monthNames = {}; }
  };
  const dayRe = new RegExp('\\b(' + DAYS.join('|') + ')\\b', 'g');
  const dateRe = new RegExp('\\b(\\d{1,2}) (' + MONTHS.join('|') + ')\\b', 'g');
  const dateFix = (s) => {
    if (lang === 'en' || !dayNames.Mon) return s;
    // "Mon 5 Nov", "5 Nov", and lists such as "Mon, Wed, Fri": only when the whole text is made of these words
    const only = s.split(/[\s,·–-]+/).every((w) => !w || /^\d{1,2}$/.test(w) || DAYS.includes(w) || MONTHS.includes(w));
    let out = s.replace(dateRe, (m, d, mo) => d + ' ' + monthNames[mo]);
    if (only) out = out.replace(dayRe, (m) => dayNames[m]).replace(new RegExp('\\b(' + MONTHS.join('|') + ')\\b', 'g'), (m) => monthNames[m]);
    else out = out.replace(new RegExp('\\b(' + DAYS.join('|') + ') (?=\\d{1,2} )', 'g'), (m, d) => dayNames[d] + ' ');
    return out;
  };

  // ---- dictionary
  let exact = new Map();
  let pats = [];
  const norm = (s) => s.replace(/\s+/g, ' ').trim();
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const build = (d) => {
    exact = new Map();
    pats = [];
    Object.keys(d).forEach((k) => {
      const v = d[k];
      if (typeof v !== 'string' || !v) return;
      const key = norm(k);
      if (!/\{\d+\}/.test(key)) { exact.set(key, v); return; }
      const parts = key.split(/\{\d+\}/);
      const idx = (key.match(/\{(\d+)\}/g) || []).map((x) => Number(x.slice(1, -1)));
      const body = parts.map(esc).join('([\\s\\S]*?)');
      let re;
      try { re = new RegExp('^' + body + '$'); } catch (e) { return; }
      const weight = parts.join('').length;
      pats.push({ re, idx, to: v, weight, strict: /^\{\d+\}/.test(key) && weight <= 14 });
    });
    pats.sort((a, b) => b.weight - a.weight);
  };
  const lookup = (s, depth) => {
    const hit = exact.get(s);
    if (hit != null) return hit;
    if (depth > 2) return null;
    // "a; b; c" where every item is known: translate item by item, so one pattern cannot swallow the whole list
    if (s.includes('; ')) {
      const items = s.split('; ');
      const out = items.map((x) => lookup(x, depth + 1));
      if (out.every((x) => x != null)) return out.join('; ');
    }
    for (const p of pats) {
      const m = p.re.exec(s);
      if (!m) continue;
      // a pattern must not swallow several sentences, and a short one that starts with a gap ("{0} sets") only takes numbers
      if (m.slice(1).some((c) => /[.!?] [A-Z]/.test(c) || (p.strict && !/^(?:\d[\d.,/×x –+-]*|[A-Z])$/.test(c)))) continue;
      const parts = {};
      p.idx.forEach((n, i) => { const raw = m[i + 1]; const t = lookup(norm(raw), depth + 1); parts[n] = t != null ? t : dateFix(raw); });
      return p.to.replace(/\{(\d+)\}/g, (x, n) => (parts[n] != null ? parts[n] : x));
    }
    return null;
  };
  // pieces glued with separators ("a · b", "a, b", two sentences): translate the pieces that are known
  const pieces = (s) => {
    // sentences: take the longest run that is known, then go on from there
    const sents = s.split(/(?<=[.!?]) /);
    if (sents.length > 1) {
      const out = [];
      let any = false;
      for (let i = 0; i < sents.length;) {
        let hit = null;
        let to = i + 1;
        for (let j = sents.length; j > i; j -= 1) {
          const t = lookup(norm(sents.slice(i, j).join(' ')), 2);
          if (t != null) { hit = t; to = j; break; }
        }
        if (hit != null) { any = true; out.push(hit); } else out.push(dateFix(sents[i]));
        i = to;
      }
      if (any) return out.join(' ');
    }
    const tries = [(x) => x.split(' · '), (x) => x.split('; '), (x) => x.split(', ')];
    const joins = [' · ', '; ', ', '];
    for (let i = 0; i < tries.length; i += 1) {
      const bits = tries[i](s);
      if (bits.length < 2) continue;
      let any = false;
      const out = bits.map((b) => { const t = lookup(norm(b), 2); if (t != null) { any = true; return t; } return dateFix(b); });
      if (any) return out.join(joins[i]);
    }
    return null;
  };
  const translate = (s) => {
    const k = norm(s);
    if (!k || !/[A-Za-z]/.test(k)) return null;
    let t = lookup(k, 0);
    if (t == null) t = pieces(k);
    const fixed = dateFix(t != null ? t : k);
    if (t == null && fixed === k) return null;
    return fixed;
  };

  // ---- the page
  const ATTRS = ['aria-label', 'title', 'placeholder', 'alt', 'aria-description'];
  const SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1, CODE: 1 };
  const shownText = new WeakMap();
  const shownAttr = new WeakMap();
  const text = (node) => {
    const p = node.parentNode;
    if (!p || SKIP[p.nodeName] || (p.closest && p.closest('[translate="no"]'))) return;
    const val = node.data;
    if (shownText.get(node) === val) return;
    const t = translate(val);
    if (t == null) return;
    const lead = val.match(/^\s*/)[0];
    const trail = val.match(/\s*$/)[0];
    const next = lead + t + trail;
    if (next === val) return;
    shownText.set(node, next);
    node.data = next;
  };
  const attrs = (el) => {
    if (el.closest && el.closest('[translate="no"]')) return;
    let rec = shownAttr.get(el);
    ATTRS.forEach((a) => {
      const val = el.getAttribute(a);
      if (!val || (rec && rec[a] === val)) return;
      const t = translate(val);
      if (t == null || t === val) return;
      if (!rec) { rec = {}; shownAttr.set(el, rec); }
      rec[a] = t;
      el.setAttribute(a, t);
    });
  };
  const walk = (root) => {
    if (!root) return;
    if (root.nodeType === 3) { text(root); return; }
    if (root.nodeType !== 1 && root.nodeType !== 9 && root.nodeType !== 11) return;
    if (root.nodeType === 1) { if (root.nodeName === 'SCRIPT' || root.nodeName === 'STYLE') return; attrs(root); }
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let n = tw.nextNode();
    while (n) {
      if (n.nodeType === 3) text(n);
      else if (n.nodeName !== 'SCRIPT' && n.nodeName !== 'STYLE') attrs(n);
      n = tw.nextNode();
    }
  };
  let pending = [];
  let scheduled = false;
  const flush = () => {
    scheduled = false;
    const list = pending;
    pending = [];
    list.forEach((m) => {
      if (m.type === 'characterData') text(m.target);
      else if (m.type === 'attributes') attrs(m.target);
      else m.addedNodes.forEach(walk);
    });
  };
  const observe = () => {
    new MutationObserver((muts) => { pending.push(...muts); if (!scheduled) { scheduled = true; queueMicrotask(flush); } })
      .observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  };
  const title = () => { const t = translate(document.title); if (t) document.title = t; };

  // ---- loading, and the first-start picker
  const hide = document.createElement('style');
  hide.textContent = 'html{visibility:hidden}';
  const reveal = () => { if (hide.parentNode) hide.remove(); };
  const ready = (fn) => { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn); else fn(); };
  const start = () => {
    initDates();
    if (lang === 'en') { reveal(); return; }
    document.documentElement.append(hide);
    const timer = setTimeout(reveal, 2500);
    fetch('i18n/' + lang + '.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : {})).then((d) => {
      build(d || {});
      ready(() => { walk(document.documentElement); title(); observe(); clearTimeout(timer); reveal(); });
    }).catch(() => { clearTimeout(timer); reveal(); });
  };

  const picker = () => {
    const css = document.createElement('style');
    css.textContent = '.yl{position:fixed;inset:0;z-index:100;display:flex;align-items:center;justify-content:center;padding:1rem;background:rgba(10,14,40,.7)}'
      + '.yl-box{width:min(100%,24rem);background:var(--paper,#fff);color:var(--ink,#26358f);border:2px solid var(--ink,#26358f);padding:1.25rem;display:flex;flex-direction:column;gap:.875rem;max-height:100%;overflow:auto}'
      + '.yl-box h2{font-family:var(--f-head,inherit);font-size:1.5rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;line-height:1.15;margin:0}'
      + '.yl-box p{margin:0;font-weight:500;color:var(--ink-soft,#5c6378)}'
      + '.yl-b{display:flex;align-items:center;gap:.75rem;min-height:52px;font:inherit;font-size:1.125rem;font-weight:700;text-align:left;padding:0 1rem;color:var(--ink,#26358f);background:var(--paper,#fff);border:2px solid var(--ctl,#6873b6);cursor:pointer;border-radius:0}'
      + '.yl-b:hover,.yl-b:focus-visible{border-color:var(--ink,#26358f);outline:none;background:var(--faint,#eef0fb)}'
      + '.yl-b[data-guess]{border-color:var(--ink,#26358f)}';
    document.head.append(css);
    const wrap = document.createElement('div');
    wrap.className = 'yl';
    wrap.setAttribute('translate', 'no');
    const box = document.createElement('div');
    box.className = 'yl-box';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', 'Language · Taal · Idioma · Sprache · Langue · Lingua');
    const h = document.createElement('h2');
    h.textContent = 'Language · Taal · Idioma · Sprache · Langue · Lingua';
    box.append(h);
    const guess = (navigator.languages || [navigator.language || 'en']).map((l) => String(l).slice(0, 2).toLowerCase()).find(valid) || 'en';
    let first = null;
    LANGS.forEach(([code, name]) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'yl-b';
      b.lang = code;
      const label = document.createElement('span');
      label.textContent = name;
      b.append(flag(code), label);
      if (code === guess) { b.dataset.guess = '1'; first = b; }
      b.addEventListener('click', () => { store.set(code); location.reload(); });
      box.append(b);
    });
    wrap.append(box);
    document.body.append(wrap);
    (first || box.querySelector('button')).focus();
  };

  start();
  if (!chosen && !document.documentElement.hasAttribute('data-nopick')) ready(picker);

  window.YC_I18N = {
    langs: LANGS.map(([code, name, english]) => ({ code, name, english })),
    current: () => lang,
    t: (x) => translate(String(x)),
    flag,
    set: (code) => { if (!valid(code) || code === lang) return; store.set(code); location.reload(); },
  };
})();
