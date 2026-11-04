// Feedback and requests: send a bug, an idea or feedback, follow it, and get told when it is done.
// The owner sees and answers every ticket in the same place. Web only: it needs the account (window.YC_API from web.js).
// Everything a user typed is shown with textContent, never as HTML.
(() => {
  'use strict';
  if (!window.YC_WEB) return;

  // ------------------------------------------------------------------ small helpers
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.textContent = text; return e; };
  const skew = (cls, label, onClick) => { const b = h('button', 'skew ' + cls); b.type = 'button'; b.append(h('span', '', label)); b.addEventListener('click', onClick); return b; };
  const textBtn = (label, onClick) => { const b = h('button', 'textbtn', label); b.type = 'button'; b.addEventListener('click', onClick); return b; };
  const field = (label, control) => { const l = h('label', 'ed-f'); l.append(h('span', 'lab', label), control); return l; };
  const textarea = (rows, max) => { const t = h('textarea', 'nt-text'); t.rows = rows; t.maxLength = max; return t; };
  const select = (options) => { const s = h('select'); options.forEach(([v, l]) => { const o = h('option', '', l); o.value = v; s.append(o); }); return s; };
  const liveNote = () => { const p = h('p', 'note'); p.setAttribute('aria-live', 'polite'); return p; };
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const when = (iso) => { const d = new Date(iso); return d.getDate() + ' ' + MON[d.getMonth()]; };
  const plural = (n, word) => n + ' ' + word + (n === 1 ? '' : 's');

  // ------------------------------------------------------------------ words
  const TYPES = { bug: 'Something is broken', feature: 'A feature I would like', feedback: 'Feedback' };
  const HINT = {
    bug: 'What happened, and what did you expect? Which screen were you on?',
    feature: 'What would you like to be able to do?',
    feedback: 'What is on your mind?',
  };
  const DEFAULT_OUTCOME = { bug: 'fixed', feature: 'built', feedback: 'thanks' };
  const isFinal = (t) => t.status === 'resolved' || t.status === 'declined';
  const statusLabel = (t) => (t.status === 'resolved'
    ? { built: 'Built', fixed: 'Fixed', thanks: 'Thank you!' }[t.outcome]
    : { open: 'Received', needs_info: 'We have a question', planned: 'Planned', declined: 'Not planned' }[t.status]);
  // the pop-up when a ticket is done: [first part, last part]; the owner's note goes in between
  const POPUP = {
    built: (t) => ['Your request "' + t.title + '" has been added to Yes Coach!', ' Thank you very much!'],
    fixed: (t) => ['The bug you reported, "' + t.title + '", has been fixed.', ' Thank you very much!'],
    thanks: (t) => ['We read your feedback "' + t.title + '". It helps us make Yes Coach! better.', ' Thank you very much!'],
    declined: (t) => ['We looked at "' + t.title + '" and could not take it further.', ' Our apologies! If you would like to create a new ticket, feel free to. Happy training!'],
  };
  const popupText = (t) => { const [a, b] = POPUP[t.status === 'resolved' ? t.outcome : 'declined'](t); return a + (t.resolution_note ? ' ' + t.resolution_note : '') + b; };
  const problem = (e) => (e.code === 'unavailable' ? 'No connection. Try again when you are online.'
    : /too_many_tickets/.test(e.message) ? 'You have sent 5 today, which is the daily limit. Try again tomorrow.'
    : /too_many_messages/.test(e.message) ? 'That is a lot of messages for one day. Try again tomorrow.'
    : 'That did not go through. Try again in a moment.');

  // ------------------------------------------------------------------ data
  const db = () => window.YC_API.sb;
  const run = (query) => window.YC_API.call(query);
  const MY_COLS = 'id,type,title,body,status,outcome,resolution_note,created_at,resolved_at,user_seen_at';
  const version = () => { const m = $('meta[name="yc-build"]'); return (m && m.content) || 'dev'; };
  // sent with every ticket so a bug can be found: device and screen only, never training data
  const deviceInfo = () => ({
    ua: navigator.userAgent.slice(0, 200),
    screen: screen.width + 'x' + screen.height,
    viewport: innerWidth + 'x' + innerHeight,
    lang: navigator.language,
    installed: matchMedia('(display-mode: standalone)').matches || navigator.standalone === true,
  });
  const sendTicket = (type, title, body) => run(db().from('tickets').insert({ type, title, body, app_version: version(), context: deviceInfo() }).select('id'));
  const sendReply = (id, body) => run(db().from('ticket_messages').insert({ ticket_id: id, author: 'user', body }));

  // ------------------------------------------------------------------ cards shared by the user list and the owner list
  const chip = (t) => h('span', 'chip ' + ({ needs_info: 'tk-ask', resolved: 'tk-done', declined: 'tk-no' }[t.status] || ''), statusLabel(t));
  const message = (label, text, author) => { const p = h('p', 'tk-msg ' + author); p.append(h('span', 'lab', label), text); return p; };
  // viewer is 'user' or 'admin': it decides what each side of the thread is called
  const loadThread = async (t, box, viewer) => {
    try {
      const rows = await run(db().from('ticket_messages').select('id,author,body,created_at').eq('ticket_id', t.id).order('created_at'));
      box.dataset.state = 'done';
      box.replaceChildren(...rows.map((m) => message(m.author === viewer ? 'You' : m.author === 'admin' ? 'Yes Coach!' : 'User', m.body, m.author)));
    } catch (e) {
      delete box.dataset.state; // opening the card again retries
      box.replaceChildren(h('p', 'note', 'Could not load the conversation. Close this and open it again to retry.'));
    }
  };
  const card = (t, open, viewer, info, extra) => {
    const d = h('details', 'tk-card');
    d.dataset.id = t.id;
    const head = h('summary');
    head.append(h('span', 'tk-title', t.title), chip(t));
    const thread = h('div', 'tk-thread');
    const body = h('div', 'tk-body');
    body.append(h('p', 'note', info), h('p', 'tk-text', t.body));
    if (t.resolution_note) body.append(message(viewer === 'admin' ? 'Note shown to the user' : 'Yes Coach!', t.resolution_note, 'admin'));
    body.append(thread, extra(t));
    d.append(head, body);
    const ensure = () => { if (!thread.dataset.state) { thread.dataset.state = 'loading'; loadThread(t, thread, viewer); } };
    d.addEventListener('toggle', () => { if (d.open) ensure(); });
    if (open) { d.open = true; ensure(); }
    return d;
  };
  // repaint a list of cards and keep the ones that were open
  const paintCards = (list, tickets, make, empty) => {
    const open = new Set($$('.tk-card[open]', list).map((d) => d.dataset.id));
    list.replaceChildren(...(tickets.length ? tickets.map((t) => make(t, open.has(t.id))) : [h('p', 'note', empty)]));
  };

  // ------------------------------------------------------------------ the user: send something
  const newForm = (onSent) => {
    const form = h('form', 'tk-form');
    form.noValidate = true;
    form.hidden = true;
    const type = select(Object.entries(TYPES));
    const title = h('input');
    title.type = 'text';
    title.maxLength = 120;
    title.autocomplete = 'off';
    const text = textarea(5, 4000);
    text.placeholder = HINT.bug;
    const msg = liveNote();
    const go = h('button', 'skew pop');
    go.type = 'submit';
    go.append(h('span', '', 'Send'));
    type.addEventListener('change', () => { text.placeholder = HINT[type.value]; });
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      if (title.value.trim().length < 3) { msg.textContent = 'Add a few words as a title.'; title.focus(); return; }
      if (text.value.trim().length < 10) { msg.textContent = 'Tell us a bit more (at least 10 characters).'; text.focus(); return; }
      go.disabled = true;
      msg.textContent = 'Sending…';
      try {
        await sendTicket(type.value, title.value.trim(), text.value.trim());
        title.value = '';
        text.value = '';
        msg.textContent = '';
        onSent();
      } catch (e) { msg.textContent = problem(e); }
      go.disabled = false;
    });
    form.append(field('What is it about?', type), field('In a few words', title), field('Tell us more', text), go, msg, textBtn('Cancel', () => { form.hidden = true; }));
    return form;
  };
  const replyForm = (t) => {
    const box = h('div', 'tk-reply');
    const text = textarea(3, 2000);
    const msg = liveNote();
    const go = skew('small', 'Send', async () => {
      const body = text.value.trim();
      if (!body) return;
      go.disabled = true;
      try { await sendReply(t.id, body); await refresh(true); } catch (e) { msg.textContent = problem(e); }
      go.disabled = false;
    });
    box.append(field(t.status === 'needs_info' ? 'Your answer' : 'Add a message', text), go, msg);
    return box;
  };

  // ------------------------------------------------------------------ the user: follow what was sent
  let mine = [];
  let loadedAt = 0;
  const summaryLine = () => {
    const done = mine.filter((t) => t.status === 'resolved' && t.outcome !== 'thanks').length;
    const planned = mine.filter((t) => t.status === 'planned').length;
    const parts = [done && done + ' built or fixed', planned && planned + ' planned'].filter(Boolean);
    return 'You have sent ' + plural(mine.length, 'request') + (parts.length ? ': ' + parts.join(', ') : '') + '.';
  };
  const paintMine = () => {
    $('#tk-sum').textContent = mine.length ? summaryLine() : '';
    paintCards($('#tk-list'), mine, (t, open) => card(t, open, 'user',
      TYPES[t.type] + ' · sent ' + when(t.created_at) + (t.resolved_at ? ' · closed ' + when(t.resolved_at) : ''), (x) => (isFinal(x) ? h('span') : replyForm(x))),
    'Nothing sent yet.');
  };
  // a dot on the gear and a hint on the section when we are waiting for an answer
  const paintDot = () => {
    const ask = mine.some((t) => t.status === 'needs_info');
    const tab = $('#tab-settings');
    tab.classList.toggle('tk-dot', ask);
    tab.setAttribute('aria-label', ask ? 'Settings. You have a question in Feedback and requests.' : 'Settings');
    ($('#h-tk .set-tog span') || $('#h-tk')).textContent = ask ? 'Feedback and requests (a question for you)' : 'Feedback and requests';
  };
  const refresh = async (force) => {
    if (!force && Date.now() - loadedAt < 30000) return;
    loadedAt = Date.now();
    // the owner can read every ticket, so "mine" must say whose
    try { mine = await run(db().from('tickets').select(MY_COLS).eq('user_id', window.YC_API.uid()).order('created_at', { ascending: false }).limit(100)); } catch (e) { loadedAt = 0; if (!mine.length) $('#tk-sum').textContent = 'Could not load your requests right now.'; return; }
    paintMine();
    paintDot();
    showPopup(mine.filter((t) => isFinal(t) && !t.user_seen_at && !seen.has(t.id)));
  };

  // ------------------------------------------------------------------ the pop-up when something is done
  let popup = null;
  const seen = new Set(); // tickets whose pop-up was closed in this visit, even if saving that is still on its way
  const markSeen = (items) => {
    const now = new Date().toISOString();
    items.forEach((t) => { t.user_seen_at = now; seen.add(t.id); });
    run(db().from('tickets').update({ user_seen_at: now }).in('id', items.map((t) => t.id))).catch(() => {}); // if this fails it shows again next time
  };
  const showPopup = (items) => {
    if (popup || !items.length) return;
    const before = document.activeElement;
    const wrap = h('div', 'tk-pop');
    const box = h('div', 'tk-pop-in');
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-labelledby', 'tk-pop-h');
    const head = h('h2', '', items.some((t) => t.status === 'resolved') ? 'Thank you!' : 'An update on your request');
    head.id = 'tk-pop-h';
    const close = () => { wrap.remove(); popup = null; document.removeEventListener('keydown', keys); markSeen(items); if (before && before.focus) before.focus(); };
    const ok = skew('pop', 'Close', close);
    const keys = (ev) => { if (ev.key === 'Escape') close(); else if (ev.key === 'Tab') { ev.preventDefault(); ok.focus(); } };
    box.append(head, ...items.map((t) => h('p', 'tk-pop-p', popupText(t))), ok);
    wrap.append(box);
    document.body.append(wrap);
    document.addEventListener('keydown', keys);
    popup = wrap;
    ok.focus();
  };

  // ------------------------------------------------------------------ the owner
  const STATUSES = [['open', 'Received'], ['needs_info', 'Question sent'], ['planned', 'Planned'], ['resolved', 'Resolved'], ['declined', 'Declined']];
  let all = [];
  let show = 'open';
  const FILTERS = { open: (t) => t.status === 'open' || t.status === 'needs_info', planned: (t) => t.status === 'planned', closed: isFinal, all: () => true };
  const adminReply = (t) => {
    const box = h('div', 'tk-reply');
    const text = textarea(3, 2000);
    const msg = liveNote();
    const send = (ask) => async () => {
      const body = text.value.trim();
      if (!body) return;
      try { await run(db().rpc('admin_reply', { p_ticket: t.id, p_body: body, p_ask: ask })); await loadAdmin(); } catch (e) { msg.textContent = e.message; }
    };
    const row = h('div', 'foot-row');
    row.append(skew('small', 'Ask a question', send(true)), skew('small', 'Send message', send(false)));
    box.append(field('Write to the user', text), row, msg);
    return box;
  };
  const adminDecide = (t) => {
    const box = h('div', 'tk-decide');
    const status = select(STATUSES);
    status.value = t.status;
    const outcome = select([['built', 'Built'], ['fixed', 'Fixed'], ['thanks', 'Thank you']]);
    outcome.value = t.outcome || DEFAULT_OUTCOME[t.type];
    const note = textarea(3, 2000);
    note.value = t.resolution_note || '';
    note.placeholder = 'Message to the user, in plain words';
    const hasKids = all.some((x) => x.duplicate_of === t.id);
    const dup = select([['', 'Not a duplicate'], ...all.filter((x) => x.id !== t.id && !x.duplicate_of).map((x) => [x.id, TYPES[x.type].slice(0, 12) + ' · ' + x.title.slice(0, 40) + ' · ' + x.id.slice(0, 6)])]);
    dup.value = t.duplicate_of || '';
    dup.disabled = hasKids;
    const outcomeF = field('Outcome', outcome);
    const mirror = () => { const d = !!dup.value; status.disabled = outcome.disabled = note.disabled = d; outcomeF.hidden = status.value !== 'resolved'; };
    status.addEventListener('change', mirror);
    dup.addEventListener('change', mirror);
    mirror();
    const msg = liveNote();
    const save = skew('pop small', 'Save', async () => {
      try {
        await run(db().rpc('admin_set_ticket', { p_id: t.id, p_status: status.value, p_outcome: status.value === 'resolved' ? outcome.value : null, p_note: note.value, p_duplicate_of: dup.value || null }));
        await loadAdmin();
      } catch (e) { msg.textContent = e.message; }
    });
    let armed = 0;
    const del = skew('danger small', 'Delete', async () => {
      if (!armed) { armed = setTimeout(() => { armed = 0; del.firstChild.textContent = 'Delete'; }, 5000); del.firstChild.textContent = 'Tap again to delete'; return; }
      clearTimeout(armed);
      try { await run(db().rpc('admin_delete_ticket', { p_id: t.id })); await loadAdmin(); } catch (e) { msg.textContent = e.message; }
    });
    const row = h('div', 'foot-row');
    row.append(save, del);
    box.append(field('Status', status), outcomeF, field('Note shown to the user, and to anyone whose request is a duplicate of this one', note), field('Duplicate of', dup), row, msg);
    return box;
  };
  const adminExtra = (t) => { const w = h('div', 'tk-owner'); w.append(adminReply(t), adminDecide(t)); return w; };
  const adminInfo = (t) => {
    const c = t.context || {};
    const device = [c.screen && 'screen ' + c.screen, c.lang, c.installed ? 'installed app' : 'browser', c.ua].filter(Boolean).join(' · ');
    return TYPES[t.type] + ' · sent ' + when(t.created_at) + ' · user ' + t.user_id.slice(0, 8) + ' · build ' + (t.app_version || '?') + ' · ' + device;
  };
  const paintAdmin = () => {
    const rows = all.filter(FILTERS[show]);
    $('#tk-admin-sum').textContent = plural(rows.length, 'ticket') + ' shown, ' + all.filter(FILTERS.open).length + ' waiting.';
    paintCards($('#tk-admin-list'), rows, (t, open) => card(t, open, 'admin', adminInfo(t), adminExtra), 'Nothing here.');
  };
  const loadAdmin = async () => {
    try { all = await run(db().from('tickets').select('*').order('created_at', { ascending: false }).limit(200)); paintAdmin(); } catch (e) { $('#tk-admin-sum').textContent = 'Could not load tickets: ' + e.message; }
  };

  // ------------------------------------------------------------------ the page
  const section = (id, title) => {
    const sec = document.createElement('section');
    sec.id = id;
    sec.setAttribute('aria-labelledby', 'h-' + id);
    const head = h('h2', '', title);
    head.id = 'h-' + id;
    sec.append(head);
    return sec;
  };
  const buildSection = () => {
    const sec = section('tk', 'Feedback and requests');
    const state = liveNote();
    const form = newForm(() => { form.hidden = true; state.textContent = 'Sent. Thank you! You can follow it below.'; refresh(true); });
    const open = skew('pop', 'Send something', () => { form.hidden = false; state.textContent = ''; $('select', form).focus(); });
    const row = h('div', 'foot-row');
    row.append(open);
    const sum = h('p', 'note');
    sum.id = 'tk-sum';
    const list = h('div', 'tk-list');
    list.id = 'tk-list';
    sec.append(
      h('p', 'note', 'Found a bug, want a feature, or have something to say? Send it here. If something is unclear we may reply right here in the app.'),
      h('p', 'note', 'Your app version, device and screen size are sent along so we can find bugs. Never your training data.'),
      row, state, form, h('span', 'lab', 'My requests'), sum, list);
    return sec;
  };
  const buildAdmin = () => {
    const sec = section('tk-admin', 'Tickets (owner)');
    const filter = select([['open', 'Waiting for me'], ['planned', 'Planned'], ['closed', 'Closed'], ['all', 'All']]);
    filter.addEventListener('change', () => { show = filter.value; paintAdmin(); });
    const sum = h('p', 'note');
    sum.id = 'tk-admin-sum';
    const list = h('div', 'tk-list');
    list.id = 'tk-admin-list';
    sec.append(field('Show', filter), sum, list);
    return sec;
  };
  // Home gets a way in, and Settings opens the section
  const openSection = () => {
    $('#tab-settings').click();
    const sec = $('#tk');
    const tog = $('.set-tog', sec);
    if (tog && tog.getAttribute('aria-expanded') !== 'true') tog.click();
    requestAnimationFrame(() => sec.scrollIntoView({ block: 'start' }));
  };
  const style = () => {
    const css = h('style');
    css.textContent = `
#tk, #tk-admin { scroll-margin-top: calc(var(--stick-h, 48px) + 8px); }
#tab-settings.tk-dot { position: relative; }
#tab-settings.tk-dot::after { content: ''; position: absolute; top: 6px; right: 4px; width: 10px; height: 10px; border-radius: 50%; background: var(--pop); border: 2px solid var(--bg); }
.tk-form { display: flex; flex-direction: column; gap: 0.875rem; padding: 0.75rem; background: var(--faint); border-left: 4px solid var(--ink); align-items: flex-start; }
.tk-form > .ed-f { width: 100%; }
.tk-list { display: flex; flex-direction: column; }
.tk-card { border-bottom: 1px solid var(--line); }
.tk-card > summary { list-style: none; cursor: pointer; display: flex; gap: 0.75rem; align-items: center; justify-content: space-between; min-height: 44px; padding-block: 0.5rem; font-weight: 600; }
.tk-card > summary::-webkit-details-marker { display: none; }
.tk-title { min-width: 0; overflow-wrap: anywhere; }
.tk-card .chip { flex: none; }
.chip.tk-done { border-color: var(--good); color: var(--good); }
.chip.tk-ask { border-color: var(--pop); background: var(--pop); color: var(--on-pop); }
.chip.tk-no { border-color: var(--line); color: var(--ink-soft); }
.tk-body, .tk-owner, .tk-decide, .tk-reply, .tk-thread { display: flex; flex-direction: column; gap: 0.625rem; }
.tk-body { padding-bottom: 1rem; }
.tk-reply, .tk-decide { align-items: flex-start; }
.tk-reply > .ed-f, .tk-decide > .ed-f { width: 100%; }
.tk-text, .tk-msg { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.tk-msg { padding: 0.5rem 0.75rem; background: var(--faint); border-left: 4px solid var(--ctl); }
.tk-msg.admin { border-left-color: var(--pop); }
.tk-msg .lab { display: block; }
.tk-pop { position: fixed; inset: 0; z-index: 60; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(16, 20, 43, 0.6); }
.tk-pop-in { width: 100%; max-width: 26rem; max-height: 85vh; overflow: auto; display: flex; flex-direction: column; gap: 0.875rem; align-items: flex-start; padding: 1.25rem; background: var(--paper); border: 2px solid var(--ink); box-shadow: 0 8px 24px rgba(16, 20, 43, 0.35); }
.tk-pop-p { margin: 0; overflow-wrap: anywhere; }`;
    document.head.append(css);
  };
  const init = async () => {
    await window.claude.use('db'); // resolves once the user is signed in
    if (document.readyState === 'loading') await new Promise((r) => document.addEventListener('DOMContentLoaded', r));
    style();
    const sec = buildSection();
    const acct = $('#acct');
    if (acct) acct.after(sec); else $('#v-settings .set-wrap').prepend(sec);
    const row = $('#v-home .foot-row');
    if (row) row.append(textBtn('Feedback and requests', openSection));
    $('#tab-settings').addEventListener('click', () => refresh());
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') refresh(); });
    refresh(true);
    let owner = false;
    try { owner = (await run(db().rpc('is_admin'))) === true; } catch (e) { /* the database part is not installed yet */ }
    if (owner) { sec.after(buildAdmin()); loadAdmin(); }
  };
  init().catch(() => {});
})();
