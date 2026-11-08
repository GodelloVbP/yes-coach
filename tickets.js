// Feedback & Requests: a tab where users send a bug, an idea or feedback, follow it, and get told when it is done.
// The owner sees and answers every ticket in the same tab. Web only: it needs the account (window.YC_API from web.js).
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
  const whenAt = (iso) => { const d = new Date(iso); return when(iso) + ', ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); };
  const plural = (n, word) => n + ' ' + word + (n === 1 ? '' : 's');

  // ------------------------------------------------------------------ words
  const TYPES = { bug: 'Something is broken', feature: 'A feature I would like', feedback: 'Feedback' };
  const HINT = {
    bug: 'What happened, and what did you expect?',
    feature: 'What would you like to be able to do?',
    feedback: 'What is on your mind?',
  };
  const DEFAULT_OUTCOME = { bug: 'fixed', feature: 'built', feedback: 'thanks' };
  // what to choose from, in a line each; and what the list of each kind is called
  const TILES = [
    { type: 'bug', note: 'What happened, and on which screen' },
    { type: 'feature', note: 'Something you want it to do' },
    { type: 'feedback', note: 'What you like, what feels off' },
  ];
  const GROUPS = [
    { type: 'feature', title: 'Feature requests' },
    { type: 'bug', title: 'Bug reports' },
    { type: 'feedback', title: 'Feedback' },
  ];
  const isFinal = (t) => t.status === 'resolved' || t.status === 'declined';
  const statusLabel = (t) => (t.status === 'resolved'
    ? { built: 'Built', fixed: 'Fixed', thanks: 'Thank you!' }[t.outcome]
    : { open: 'Received', needs_info: 'We have a question', planned: 'Planned', declined: 'Not planned' }[t.status]);
  // the pop-up when a ticket is done: what you sent, what we did with it, our note if any, a thank you
  const KIND = { feature: 'feature request', bug: 'bug report', feedback: 'feedback' };
  const POPUP_LABEL = { feature: 'Your request', bug: 'Your bug report', feedback: 'Your feedback' };
  const VERB = { built: 'built', fixed: 'fixed', thanks: 'read' };
  const verdict = (t) => (t.status === 'resolved'
    ? 'Yes Coach! ' + (VERB[t.outcome] || 'handled') + ' your ' + KIND[t.type] + ' "' + t.title + '".'
    : 'We decided not to go ahead with your ' + KIND[t.type] + ' "' + t.title + '".');
  const thanksLine = (t) => (t.status === 'declined' ? 'Sorry about that. You are welcome to send a new one. ' : '') + 'Thank you for contributing.';
  const problem = (e) => (e.code === 'unavailable' ? 'No connection. Try again when you are online.'
    : /too_many_tickets/.test(e.message) ? 'Daily limit of 5 reached. Try again tomorrow.'
    : /too_many_messages/.test(e.message) ? 'Too many messages for one day. Try again tomorrow.'
    : 'That did not go through. Try again in a moment.');

  // ------------------------------------------------------------------ data
  const db = () => window.YC_API.sb;
  const run = (query) => window.YC_API.call(query);
  const MY_COLS = 'id,type,title,body,first_name,status,outcome,resolution_note,created_at,resolved_at,user_seen_at';
  const version = () => { const m = $('meta[name="yc-build"]'); return (m && m.content) || 'dev'; };
  // sent with every ticket so a bug can be found: device and screen only, never training data
  const deviceInfo = () => ({
    ua: navigator.userAgent.slice(0, 200),
    screen: screen.width + 'x' + screen.height,
    viewport: innerWidth + 'x' + innerHeight,
    lang: navigator.language,
    installed: matchMedia('(display-mode: standalone)').matches || navigator.standalone === true,
  });
  const sendTicket = (type, firstName, title, body) => run(db().from('tickets').insert({ type, first_name: firstName, title, body, app_version: version(), context: deviceInfo() }).select('id'));
  const sendReply = (id, body) => run(db().from('ticket_messages').insert({ ticket_id: id, author: 'user', body }));

  // ------------------------------------------------------------------ cards shared by the user lists and the owner list
  const chip = (t) => h('span', 'chip ' + ({ needs_info: 'tk-ask', resolved: 'tk-done', declined: 'tk-no' }[t.status] || ''), statusLabel(t));
  const message = (label, text, author, at) => { const p = h('p', 'tk-msg ' + author); p.append(h('span', 'lab', label + (at ? ' · ' + whenAt(at) : '')), text); return p; };
  // a labelled block inside an owner card
  const sec = (title, ...kids) => { const d = h('div', 'tk-sec'); d.append(h('span', 'lab', title), ...kids); return d; };
  // viewer is 'user' or 'admin': it decides what each side of the thread is called
  const loadThread = async (t, box, viewer) => {
    try {
      const rows = await run(db().from('ticket_messages').select('id,author,body,created_at').eq('ticket_id', t.id).order('created_at'));
      box.dataset.state = 'done';
      const them = viewer === 'admin' ? (t.first_name || 'User') : 'You';
      const label = (m) => (m.author === 'admin' ? (viewer === 'admin' ? 'You' : 'Yes Coach!') : them);
      box.replaceChildren(...(rows.length ? rows.map((m) => message(label(m), m.body, m.author, m.created_at)) : [h('p', 'note', 'No replies yet.')]));
    } catch (e) {
      delete box.dataset.state; // opening the card again retries
      box.replaceChildren(h('p', 'note', 'Could not load the conversation. Close and reopen to retry.'));
    }
  };
  const card = (t, open, viewer, info, extra) => {
    const d = h('details', 'tk-card');
    d.dataset.id = t.id;
    const head = h('summary');
    head.append(h('span', 'tk-title', t.title), chip(t));
    const thread = h('div', 'tk-thread');
    const body = h('div', 'tk-body');
    if (viewer === 'admin') {
      body.append(info, sec('Their message', h('p', 'tk-text', t.body)), sec('Conversation', thread));
      if (t.resolution_note) body.append(sec('Your closing note, shown to them', message('You', t.resolution_note, 'admin', t.resolved_at)));
    } else {
      body.append(h('p', 'note', info), h('p', 'tk-text', t.body));
      if (t.resolution_note) body.append(message('Yes Coach!', t.resolution_note, 'admin'));
      body.append(thread);
    }
    body.append(extra(t));
    d.append(head, body);
    const ensure = () => { if (!thread.dataset.state) { thread.dataset.state = 'loading'; loadThread(t, thread, viewer); } };
    d.addEventListener('toggle', () => { if (d.open) ensure(); });
    if (open) { d.open = true; ensure(); }
    return d;
  };
  // repaint a list of cards and keep the ones that were open
  const paintCards = (list, tickets, make, empty) => {
    const open = new Set($$('.tk-card[open]', list).map((d) => d.dataset.id));
    list.replaceChildren(...(tickets.length ? tickets.map((t) => make(t, open.has(t.id))) : empty ? [h('p', 'note', empty)] : []));
  };

  // ------------------------------------------------------------------ the user: send something
  let composeNow = null;
  let mine = [];
  const lastName = () => (mine.find((t) => t.first_name) || {}).first_name || '';
  const newForm = (onSent) => {
    const form = h('form', 'tk-form');
    form.noValidate = true;
    form.hidden = true;
    let kind = 'bug';
    const name = h('input');
    name.type = 'text';
    name.maxLength = 40;
    name.autocomplete = 'given-name';
    const title = h('input');
    title.type = 'text';
    title.maxLength = 120;
    title.autocomplete = 'off';
    const text = textarea(5, 4000);
    const msg = liveNote();
    const go = h('button', 'skew pop');
    go.type = 'submit';
    go.append(h('span', '', 'Send'));
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      if (title.value.trim().length < 3) { msg.textContent = 'Add a short title.'; title.focus(); return; }
      if (text.value.trim().length < 10) { msg.textContent = 'Write at least 10 characters.'; text.focus(); return; }
      if (!name.value.trim()) { msg.textContent = 'Add your first name, so we can thank you.'; name.focus(); return; }
      go.disabled = true;
      msg.textContent = 'Sending…';
      try {
        await sendTicket(kind, name.value.trim(), title.value.trim(), text.value.trim());
        title.value = '';
        text.value = '';
        msg.textContent = '';
        onSent();
      } catch (e) { msg.textContent = problem(e); }
      go.disabled = false;
    });
    const row = h('div', 'foot-row');
    row.append(go, textBtn('Cancel', () => { form.hidden = true; if (form.onClose) form.onClose(); }));
    form.append(field('In a few words', title), field('Tell us more', text), field('Your first name', name),
      h('p', 'note tk-priv', 'Sent with it: your first name, sign-in email, app version and device. Never your training data.'), row, msg);
    form.setKind = (k) => { if (!TYPES[k]) return; kind = k; form.setAttribute('aria-label', TYPES[k]); text.placeholder = HINT[k]; if (form.onKind) form.onKind(k); };
    form.prefill = (k, ttl) => { form.setKind(k); if (ttl && !title.value) title.value = ttl; };
    form.open = (k) => { form.hidden = false; form.setKind(k || kind); if (!name.value) name.value = lastName(); title.focus(); };
    form.setKind(kind);
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
  let loadedAt = 0;
  const summaryLine = () => {
    const done = mine.filter((t) => t.status === 'resolved' && t.outcome !== 'thanks').length;
    const planned = mine.filter((t) => t.status === 'planned').length;
    const parts = [done && done + ' built or fixed', planned && planned + ' planned'].filter(Boolean);
    return 'Sent ' + plural(mine.length, 'request') + (parts.length ? ': ' + parts.join(', ') : '') + '.';
  };
  let loadFailed = false;
  const paintMine = () => {
    const info = (t) => 'Sent ' + when(t.created_at) + (t.resolved_at ? ' · closed ' + when(t.resolved_at) : '');
    const make = (open) => (t, was) => card(t, open || was, 'user', info(t), (x) => (isFinal(x) ? h('span') : replyForm(x)));
    const asked = mine.filter((t) => t.status === 'needs_info');
    paintCards($('#tk-ask-list'), asked, make(true));
    $('#tk-ask').hidden = !asked.length;
    const rest = mine.filter((t) => t.status !== 'needs_info');
    GROUPS.forEach((g) => {
      const these = rest.filter((t) => t.type === g.type);
      paintCards($('#tk-list-' + g.type), these, make(false));
      $('#tk-group-' + g.type).hidden = !these.length;
    });
    $('#tk-sum').textContent = mine.length ? summaryLine() : loadFailed ? 'Could not load your requests right now.' : '';
    $('#tk-count').textContent = mine.length ? String(mine.length) : '';
    $('#tk-mine').hidden = !mine.length && !loadFailed;
  };
  // a dot on the tab when we are waiting for an answer
  const paintDot = () => {
    const ask = mine.some((t) => t.status === 'needs_info');
    const tab = $('#tab-feedback');
    tab.classList.toggle('tk-dot', ask);
    if (ask) { tab.title = 'You have a question'; tab.setAttribute('aria-description', 'You have a question'); } else { tab.removeAttribute('title'); tab.removeAttribute('aria-description'); }
  };
  const refresh = async (force) => {
    if (!force && Date.now() - loadedAt < 30000) return;
    loadedAt = Date.now();
    // the owner can read every ticket, so "mine" must say whose
    try { mine = await run(db().from('tickets').select(MY_COLS).eq('user_id', window.YC_API.uid()).order('created_at', { ascending: false }).limit(100)); } catch (e) { loadedAt = 0; loadFailed = !mine.length; paintMine(); return; }
    loadFailed = false;
    paintMine();
    paintDot();
    showPopup(mine.filter((t) => isFinal(t) && !t.user_seen_at && !seen.has(t.id)));
  };

  // ------------------------------------------------------------------ the pop-up when something is done
  let popup = null;
  const seen = new Set(); // tickets whose pop-up was closed in this visit, whether or not saving that has finished
  // saving "seen" is best effort: if it fails the pop-up shows again next time
  const markSeen = (items) => {
    if (!items.length) return;
    const now = new Date().toISOString();
    items.forEach((t) => { t.user_seen_at = now; seen.add(t.id); });
    run(db().from('tickets').update({ user_seen_at: now }).in('id', items.map((t) => t.id))).catch(() => {});
  };
  // one pop-up for everything that is done: arrows and "2 of 5" when there is more than one.
  // Only the tickets you actually saw count as seen; close early and the rest come back next visit.
  const showPopup = (items) => {
    if (popup || !items.length) return;
    const before = document.activeElement;
    const wrap = h('div', 'tk-pop');
    const box = h('div', 'tk-pop-in');
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-labelledby', 'tk-pop-h');
    const head = h('h2');
    head.id = 'tk-pop-h';
    const sent = h('div', 'tk-pop-sent');
    const sentTitle = h('strong', 'tk-pop-st');
    const sentBody = h('p', 'tk-pop-sb');
    sent.append(sentTitle, sentBody);
    const lead = h('p', 'tk-pop-p');
    const note = h('p', 'tk-pop-note');
    const tail = h('p', 'tk-pop-p');
    const count = h('span', 'tk-count');
    count.setAttribute('aria-live', 'polite');
    const viewed = new Set();
    let i = 0;
    const show = (n) => {
      i = n;
      const t = items[i];
      viewed.add(t.id);
      head.textContent = POPUP_LABEL[t.type] + ':';
      sentTitle.textContent = t.title;
      sentBody.textContent = t.body || '';
      sentBody.hidden = !t.body;
      lead.textContent = verdict(t);
      note.textContent = t.resolution_note || '';
      note.hidden = !t.resolution_note;
      tail.textContent = thanksLine(t);
      count.textContent = (i + 1) + ' of ' + items.length;
      prev.disabled = i === 0;
      next.disabled = i === items.length - 1;
      if (document.activeElement && document.activeElement.disabled) ok.focus(); // the arrow you just used may be the last one
    };
    const close = () => {
      wrap.remove(); popup = null; document.removeEventListener('keydown', keys);
      items.forEach((t) => seen.add(t.id)); // not again during this visit, even the ones you skipped
      markSeen(items.filter((t) => viewed.has(t.id)));
      if (before && before.focus) before.focus();
    };
    const arrow = (label, glyph, step) => { const b = skew('small', glyph, () => { show(i + step); }); b.setAttribute('aria-label', label); return b; };
    const prev = arrow('Previous', '←', -1);
    const next = arrow('Next', '→', 1);
    const ok = skew('pop', 'Close', close);
    const nav = h('div', 'tk-nav');
    nav.append(prev, count, next);
    const focusable = () => [prev, next, ok].filter((b) => !b.disabled);
    const keys = (ev) => {
      if (ev.key === 'Escape') close();
      else if (ev.key === 'ArrowLeft' && !prev.disabled) { show(i - 1); }
      else if (ev.key === 'ArrowRight' && !next.disabled) { show(i + 1); }
      else if (ev.key === 'Tab') {
        const f = focusable();
        const at = f.indexOf(document.activeElement);
        ev.preventDefault();
        f[(at + (ev.shiftKey ? -1 : 1) + f.length) % f.length].focus();
      }
    };
    box.append(head, sent, lead, note, tail);
    if (items.length > 1) box.append(nav);
    box.append(ok);
    wrap.append(box);
    show(0);
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
    box.append(field('Message', text), row, msg);
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
    box.append(field('Status', status), outcomeF, field('Closing note, also shown on duplicates', note), field('Duplicate of', dup), row, msg);
    return box;
  };
  const adminExtra = (t) => { const w = h('div', 'tk-owner'); w.append(sec('Your reply', adminReply(t)), sec('Decision', adminDecide(t))); return w; };
  // who it is from, then the device it came from, as two labelled blocks
  const adminInfo = (t) => {
    const c = t.context || {};
    const row = (k, v) => { const r = h('div', 'tk-row'); r.append(h('span', 'tk-k', k), h('span', 'tk-v', v)); return r; };
    const from = h('div', 'tk-rows');
    from.append(row('Name', t.first_name || 'not given'), row('Email', t.user_email || 'unknown'), row('Type', TYPES[t.type]), row('Sent', whenAt(t.created_at)));
    if (t.resolved_at) from.append(row('Closed', whenAt(t.resolved_at)));
    const dev = h('div', 'tk-rows');
    dev.append(row('Used', c.installed ? 'Installed app' : 'Browser'), row('Screen', [c.screen, c.viewport && '(window ' + c.viewport + ')'].filter(Boolean).join(' ') || 'unknown'),
      row('Language', c.lang || 'unknown'), row('App build', t.app_version || 'unknown'), row('Browser', c.ua || 'unknown'));
    const wrap = h('div', 'tk-info');
    wrap.append(sec('From', from), sec('Their device', dev));
    return wrap;
  };
  // the shown tickets as plain text (no emails) to paste into a chat with Claude
  const FILTER_NAMES = { open: 'waiting for me', planned: 'planned', closed: 'closed', all: 'all' };
  const ticketsText = (rows, msgs) => {
    const lines = ['Yes Coach! tickets: ' + rows.length + ' (' + FILTER_NAMES[show] + '). The texts come from users.', ''];
    rows.forEach((t, n) => {
      const c = t.context || {};
      lines.push('#' + (n + 1) + ' ' + TYPES[t.type] + ' | ' + statusLabel(t) + ' | sent ' + when(t.created_at) + ' | from ' + (t.first_name || 'no name') + (t.duplicate_of ? ' | duplicate of another ticket' : ''));
      lines.push('Title: ' + t.title, 'Text: ' + t.body);
      const dev = [c.installed ? 'installed app' : 'browser', c.screen, c.ua].filter(Boolean).join(', ');
      if (dev) lines.push('Device: ' + dev);
      msgs.filter((m) => m.ticket_id === t.id).forEach((m) => lines.push((m.author === 'admin' ? 'We wrote: ' : (t.first_name || 'User') + ' wrote: ') + m.body));
      if (t.resolution_note) lines.push('Closing note: ' + t.resolution_note);
      lines.push('');
    });
    return lines.join('\n');
  };
  const copyTickets = async (msg, fallback) => {
    const rows = all.filter(FILTERS[show]);
    fallback.hidden = true;
    if (!rows.length) { msg.textContent = 'Nothing to copy.'; return; }
    msg.textContent = 'Copying…';
    let msgs = [];
    try {
      for (let i = 0; i < rows.length; i += 40) {
        msgs = msgs.concat(await run(db().from('ticket_messages').select('ticket_id,author,body,created_at').in('ticket_id', rows.slice(i, i + 40).map((t) => t.id)).order('created_at')));
      }
    } catch (e) { msg.textContent = 'Could not load the conversations. Try again.'; return; }
    const text = ticketsText(rows, msgs);
    try { await navigator.clipboard.writeText(text); msg.textContent = 'Copied ' + plural(rows.length, 'ticket') + '. Paste them in the chat.'; } catch (e) {
      fallback.value = text; fallback.hidden = false; fallback.focus(); fallback.select();
      msg.textContent = 'Your browser blocked copying. Select the text below and copy it.';
    }
  };
  const paintAdmin = () => {
    const rows = all.filter(FILTERS[show]);
    const waiting = all.filter(FILTERS.open).length;
    $('#tk-bar-title').textContent = 'Tickets (owner)' + (waiting ? ' · ' + waiting + ' waiting' : '');
    $('#tk-admin-sum').textContent = plural(rows.length, 'ticket') + ' shown.';
    paintCards($('#tk-admin-list'), rows, (t, open) => card(t, open, 'admin', adminInfo(t), adminExtra), 'Nothing here.');
  };
  const loadAdmin = async () => {
    try { all = await run(db().from('tickets').select('*').order('created_at', { ascending: false }).limit(200)); paintAdmin(); } catch (e) { $('#tk-admin-sum').textContent = 'Could not load tickets: ' + e.message; }
  };

  // ------------------------------------------------------------------ the tab
  const section = (id, title) => {
    const sec = document.createElement('section');
    sec.id = id;
    sec.className = 'p-sec blk';
    sec.setAttribute('aria-labelledby', 'h-' + id);
    const head = h('div', 'p-head');
    const h2 = h('h2', '', title);
    h2.id = 'h-' + id;
    head.append(h2);
    sec.append(head);
    return sec;
  };
  // the top block: pick what you want to send, and the form opens under your choice
  const buildIntro = () => {
    const sec = section('tk', 'Send us something');
    const state = liveNote();
    const form = newForm(() => { form.hidden = true; paintTiles(); state.textContent = 'Sent. Thank you! You can follow it below.'; refresh(true); });
    const tiles = h('div', 'tk-types');
    tiles.setAttribute('role', 'group');
    tiles.setAttribute('aria-label', 'What do you want to send?');
    const btns = TILES.map(({ type, note }) => {
      const b = h('button', 'tk-type angled');
      b.type = 'button';
      b.dataset.type = type;
      b.append(h('b', '', TYPES[type]), h('span', 'tk-type-note', note));
      b.addEventListener('click', () => { state.textContent = ''; form.open(type); });
      tiles.append(b);
      return [type, b];
    });
    const paintTiles = (k) => btns.forEach(([type, b]) => b.setAttribute('aria-pressed', String(!form.hidden && type === k)));
    form.onKind = (k) => paintTiles(k);
    form.onClose = () => paintTiles();
    composeNow = (kind, ttl) => { state.textContent = ''; form.open(kind); form.prefill(kind, ttl); form.scrollIntoView({ block: 'center' }); const t = form.querySelector('textarea'); if (t) t.focus(); };
    sec.append(h('p', 'tk-lead', 'Built by one person. You hear back when it is built or fixed.'), tiles, state, form);
    return sec;
  };
  // a question from us waits at the top, open
  const buildAsk = () => {
    const sec = section('tk-ask', 'We have a question');
    sec.hidden = true;
    const list = h('div', 'tk-list');
    list.id = 'tk-ask-list';
    sec.append(list);
    return sec;
  };
  // everything you sent, by kind; a kind you have not used does not show
  const buildMine = () => {
    const sec = section('tk-mine', 'Your messages');
    sec.hidden = true;
    const count = h('span', 'p-count');
    count.id = 'tk-count';
    sec.firstChild.append(count);
    const sum = h('p', 'note');
    sum.id = 'tk-sum';
    sec.append(sum);
    GROUPS.forEach((g) => {
      const grp = h('div', 'tk-group');
      grp.id = 'tk-group-' + g.type;
      grp.hidden = true;
      const list = h('div', 'tk-list');
      list.id = 'tk-list-' + g.type;
      grp.append(h('h3', 'tk-group-h', g.title), list);
      sec.append(grp);
    });
    return sec;
  };
  // the extra bar for the owner: every ticket, to read, answer and close
  const buildAdmin = () => {
    const bar = h('details', 'tk-bar');
    const head = h('summary');
    head.id = 'tk-bar-title';
    head.textContent = 'Tickets (owner)';
    const filter = select([['open', 'Waiting for me'], ['planned', 'Planned'], ['closed', 'Closed'], ['all', 'All']]);
    filter.addEventListener('change', () => { show = filter.value; paintAdmin(); });
    const sum = h('p', 'note');
    sum.id = 'tk-admin-sum';
    const list = h('div', 'tk-list');
    list.id = 'tk-admin-list';
    const body = h('div', 'tk-bar-body');
    const copyNote = liveNote();
    const copyBox = textarea(6, 200000);
    copyBox.readOnly = true;
    copyBox.hidden = true;
    const copyRow = h('div', 'foot-row');
    copyRow.append(skew('small', 'Copy these tickets', () => copyTickets(copyNote, copyBox)), copyNote);
    body.append(field('Show', filter), sum, copyRow, copyBox, list);
    bar.append(head, body);
    return bar;
  };
  const style = () => {
    const css = h('style');
    css.textContent = `
#tab-feedback { position: relative; }
#v-feedback section { scroll-margin-top: calc(var(--stick-h, 48px) + 8px); }
.tk-wrap { display: flex; flex-direction: column; gap: 1rem; padding-block: 1.25rem 3rem; }
.tk-lead { margin: 0; font-weight: 500; }
.tk-types { display: flex; flex-direction: column; gap: 0.625rem; padding-inline: 0.375rem; }
@media (min-width: 40rem) { .tk-types { flex-direction: row; } .tk-type { flex: 1 1 0; min-width: 0; } }
.tk-type { --ang-bg: var(--paper); display: flex; flex-direction: column; align-items: flex-start; gap: 0.125rem; width: 100%; min-height: 56px; padding: 0.625rem 1.25rem; border: 0; background: none; color: var(--ink); font: inherit; text-align: left; cursor: pointer; }
.tk-type b { font-family: var(--f-head); font-size: var(--t3); font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.tk-type-note { font-size: var(--t2); font-weight: 500; color: var(--ink-soft); }
.tk-type[aria-pressed="true"] { --ang-bg: var(--ink); --ang-bd: var(--ink); color: var(--bg); }
.tk-type[aria-pressed="true"] .tk-type-note { color: inherit; opacity: 0.85; }
.tk-type:focus-visible { outline: 3px solid var(--pop); outline-offset: 3px; }
.tk-form { display: flex; flex-direction: column; gap: 0.875rem; padding: 0.875rem; background: var(--paper); border-left: 4px solid var(--ink); align-items: flex-start; }
#tk-ask .tk-card .chip { display: none; } /* the block already says it */
.tk-priv { margin: 0; }
.tk-group { display: flex; flex-direction: column; gap: 0.25rem; margin-top: 0.75rem; }
.tk-group-h { margin: 0; font-family: var(--f-head); font-size: var(--t2); text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-soft); }
.tk-form > .ed-f { width: 100%; }
.tk-list { display: flex; flex-direction: column; }
.tk-bar { border-bottom: 1px solid var(--line); margin-bottom: 1rem; }
.tk-bar > summary { list-style: none; cursor: pointer; display: flex; align-items: center; min-height: 48px; font-family: var(--f-head); font-size: var(--t3); font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.tk-bar > summary::-webkit-details-marker { display: none; }
.tk-bar > summary::after { content: '+'; margin-left: auto; font-size: var(--t4); line-height: 1; }
.tk-bar[open] > summary::after { content: '\\2212'; }
.tk-bar-body { display: flex; flex-direction: column; gap: 0.5rem; padding-bottom: 1rem; }
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
.tk-msg .lab { display: block; }
.tk-msg.user { background: var(--faint); }
.tk-msg.admin { background: transparent; border: 2px solid var(--pop); border-left-width: 6px; margin-left: 1rem; }
.tk-sec { display: flex; flex-direction: column; gap: 0.5rem; padding-top: 0.75rem; border-top: 2px solid var(--line); }
.tk-sec > .lab { color: var(--ink-soft); }
.tk-info { display: flex; flex-direction: column; gap: 0.75rem; }
.tk-rows { display: flex; flex-direction: column; gap: 0.25rem; }
.tk-row { display: grid; grid-template-columns: 5.5rem minmax(0, 1fr); gap: 0.5rem; }
.tk-k { color: var(--ink-soft); }
.tk-v { overflow-wrap: anywhere; user-select: text; }
.tk-owner { gap: 0.75rem; }
.tk-pop { position: fixed; inset: 0; z-index: 60; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(16, 20, 43, 0.6); }
.tk-pop-in { width: 100%; max-width: 26rem; max-height: 85vh; overflow: auto; display: flex; flex-direction: column; gap: 0.875rem; align-items: flex-start; padding: 1.25rem; background: var(--paper); border: 2px solid var(--ink); box-shadow: 0 8px 24px rgba(16, 20, 43, 0.35); }
.tk-pop-p, .tk-pop-note, .tk-pop-sb { margin: 0; overflow-wrap: anywhere; }
.tk-pop-sent { display: flex; flex-direction: column; gap: 0.25rem; align-self: stretch; padding: 0.625rem 0.75rem; background: var(--faint); border: 2px solid var(--ctl); }
.tk-pop-sb { display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; color: var(--ink-soft); white-space: pre-wrap; }
.tk-pop-note { align-self: stretch; padding-left: 0.75rem; border-left: 4px solid var(--pop); white-space: pre-wrap; }
.tk-pop-in h2 { margin: 0; }
.tk-nav { display: flex; align-items: center; gap: 0.75rem; align-self: stretch; justify-content: space-between; }
.tk-count { font-family: var(--f-head); font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; font-variant-numeric: tabular-nums; }
.tk-nav .skew:disabled { opacity: 0.35; cursor: default; }`;
    document.head.append(css);
  };
  const init = async () => {
    await window.claude.use('db'); // resolves once the user is signed in
    if (document.readyState === 'loading') await new Promise((r) => document.addEventListener('DOMContentLoaded', r));
    style();
    const wrap = h('div', 'tk-wrap in');
    wrap.append(buildIntro(), buildAsk(), buildMine());
    $('#v-feedback').replaceChildren(wrap);
    $('#tab-feedback').hidden = false;
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') refresh(); });
    refresh(true);
    let owner = false;
    try { owner = (await run(db().rpc('is_admin'))) === true; } catch (e) { /* the database part is not installed yet */ }
    if (owner) { wrap.prepend(buildAdmin()); loadAdmin(); }
  };
  // the app calls this when the tab is opened; before the tab is built there is nothing to refresh
  window.YC_FEEDBACK = { show: () => { if ($('#tk-sum')) refresh(); }, compose: (kind, ttl) => { if (composeNow) composeNow(kind, ttl); } };
  init().catch(() => {});
})();
