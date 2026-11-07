// Yes Coach! on the web: sign-in, and the same storage interface the app uses inside claude.ai (window.claude.use),
// backed by Supabase. The app does not know which one it runs on, apart from window.YC_WEB for web-only screens.
(() => {
  'use strict';
  const cfg = window.YC_CONFIG || {};
  window.YC_WEB = true;
  const $ = (s) => document.querySelector(s);
  const sb = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });
  let uid = null;
  let email = '';
  let resolveSignedIn;
  const signedIn = new Promise((r) => { resolveSignedIn = r; });

  // ------------------------------------------------------------------ documents: an in-memory copy of the user's rows, kept live
  const cache = new Map(); // path -> data
  const subs = new Set(); // {kind: 'doc'|'col', path, cb}
  const clone = (o) => (o === undefined ? undefined : JSON.parse(JSON.stringify(o)));
  const merge = (a, b) => {
    Object.keys(b).forEach((k) => {
      if (k === '__proto__' || k === 'constructor' || k === 'prototype') return; // a crafted key must never reach Object.prototype
      const v = b[k];
      if (v && typeof v === 'object' && !Array.isArray(v) && a[k] && typeof a[k] === 'object' && !Array.isArray(a[k])) merge(a[k], v);
      else a[k] = v;
    });
    return a;
  };
  // the app addresses data as data/users/<id>/yc/...; the table stores it as yc/... per user
  const strip = (p) => p.replace(/^data\/users\/[^/]+\//, '');
  const fire = (l) => {
    if (l.kind === 'doc') { const d = cache.get(l.path); l.cb({ exists: d !== undefined, data: () => clone(d) }); return; }
    const pre = l.path + '/';
    const docs = [];
    cache.forEach((d, p) => { if (p.startsWith(pre) && !p.slice(pre.length).includes('/')) docs.push({ id: p.slice(pre.length), data: () => clone(d) }); });
    l.cb({ docs });
  };
  let queued = false;
  const notify = () => { if (queued) return; queued = true; setTimeout(() => { queued = false; subs.forEach(fire); }, 0); };
  // network trouble reads as code 'unavailable', which the app retries quietly
  const asError = (e) => {
    const err = new Error((e && e.message) || 'Something went wrong');
    const net = !navigator.onLine || (e && (e.name === 'TypeError' || /fetch|network|load failed/i.test(e.message || '')));
    err.code = net ? 'unavailable' : e && e.code === 'P0002' ? 'not-found' : (e && e.code) || 'error';
    return err;
  };
  const call = async (q) => {
    let res;
    try { res = await q; } catch (e) { throw asError(e); }
    if (res.error) throw asError(res.error);
    return res.data;
  };
  const resync = async () => {
    const rows = [];
    for (let from = 0; ; from += 1000) {
      const page = await call(sb.from('docs').select('path,data').order('path').range(from, from + 999));
      rows.push(...page);
      if (page.length < 1000) break;
    }
    cache.clear();
    rows.forEach((r) => cache.set(r.path, r.data));
    notify();
  };
  const listen = (kind, path, cb, onErr) => { const l = { kind, path, cb, onErr }; subs.add(l); setTimeout(() => fire(l), 0); return () => subs.delete(l); };
  const docRef = (full) => {
    const p = strip(full);
    return {
      get: async () => {
        const rows = await call(sb.from('docs').select('data').eq('path', p).limit(1));
        if (rows.length) cache.set(p, rows[0].data);
        return { exists: rows.length > 0, data: () => clone(rows.length ? rows[0].data : undefined) };
      },
      set: async (d) => {
        cache.set(p, clone(d));
        notify();
        try { await call(sb.from('docs').upsert({ user_id: uid, path: p, data: d, updated_at: new Date().toISOString() }, { onConflict: 'user_id,path' })); } catch (e) { resync().catch(() => {}); throw e; }
      },
      update: async (patch) => {
        if (cache.has(p)) { cache.set(p, merge(clone(cache.get(p)), clone(patch))); notify(); }
        try { const d = await call(sb.rpc('yc_update', { p_path: p, p_patch: patch })); cache.set(p, d); } catch (e) { resync().catch(() => {}); throw e; }
      },
      delete: async () => {
        cache.delete(p);
        notify();
        try { await call(sb.from('docs').delete().eq('path', p)); } catch (e) { resync().catch(() => {}); throw e; }
      },
      onSnapshot: (cb, onErr) => listen('doc', p, cb, onErr),
      collection: (name) => colRef(full + '/' + name),
    };
  };
  const colRef = (full) => ({ doc: (id) => docRef(full + '/' + id), onSnapshot: (cb, onErr) => listen('col', strip(full), cb, onErr) });
  const startSync = () => {
    sb.channel('docs-' + uid)
      .on('postgres_changes', { event: '*', schema: 'public', table: 'docs', filter: 'user_id=eq.' + uid }, (ev) => {
        if (ev.eventType === 'DELETE') { if (ev.old && ev.old.path) cache.delete(ev.old.path); } else if (ev.new && ev.new.path) cache.set(ev.new.path, ev.new.data);
        notify();
      })
      .subscribe();
    // catch up after the phone slept or lost signal
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') resync().catch(() => {}); });
    window.addEventListener('online', () => resync().catch(() => {}));
  };

  // ------------------------------------------------------------------ what the app asks for
  const saveFile = ({ filename, data }) => {
    const url = URL.createObjectURL(new Blob([data], { type: /\.json$/.test(filename) ? 'application/json' : /\.csv$/.test(filename) ? 'text/csv' : 'text/plain' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    return Promise.resolve();
  };
  // for the screens that talk to the database themselves (tickets.js); they wait for sign-in through window.claude.use
  window.YC_API = { sb, call, uid: () => uid };
  // how many people have an account, for the Home page; null when it cannot be read
  window.YC_USERS = async () => { try { return await call(sb.rpc('user_count')); } catch (e) { return null; } };
  window.claude = {
    use: async (what) => {
      await signedIn;
      if (what === 'db') return { doc: docRef };
      if (what === 'user') return { id: async () => uid, isOwner: async () => true, canEdit: async () => true, can: async () => true };
      if (what === 'downloads') return { save: saveFile };
      return null; // no in-page Claude on the web: the plan builder uses copy and paste instead
    },
  };

  // ------------------------------------------------------------------ sign-in screen
  let mode = 'in'; // in | up | reset | newpass
  const COPY = {
    in: { h: 'Sign in', go: 'Sign in', alt: 'New here? Create an account' },
    up: { h: 'Create your account', go: 'Create account', alt: 'Have an account? Sign in' },
    reset: { h: 'Reset your password', go: 'Send reset link', alt: 'Back to sign in' },
    newpass: { h: 'Choose a new password', go: 'Save password', alt: '' },
  };
  const say = (msg, bad, good) => { const m = $('#au-msg'); m.textContent = msg || ''; m.classList.toggle('bad', !!bad); m.classList.toggle('good', !!good); };
  let sentTo = ''; // the address a confirmation email went to, for Send the email again
  const paint = () => {
    const c = COPY[mode];
    $('#au-h').textContent = c.h;
    $('#au-go span').textContent = c.go;
    $('#au-alt').textContent = c.alt;
    $('#au-alt').hidden = !c.alt;
    $('#au-email-f').hidden = mode === 'newpass';
    $('#au-pass-f').hidden = mode === 'reset';
    $('#au-forgot').hidden = mode !== 'in';
    $('#au-back').hidden = mode === 'newpass';
    $('#au-pass').autocomplete = mode === 'in' ? 'current-password' : 'new-password';
    $('#au-pw-hint').hidden = !(mode === 'up' || mode === 'newpass');
    $('#au-resend').hidden = true;
    // a new mode starts with the password hidden again
    $('#au-pass').type = 'password';
    $('#au-show').setAttribute('aria-pressed', 'false');
    $('#au-show').textContent = 'Show password';
    say('');
  };
  // signed out, people see Home first; the sign-in form opens from its buttons
  const openAuth = () => {
    $('#auth').hidden = false;
    document.body.classList.add('authing');
    YC_CAPTCHA.mount($('#au-cap'));
    window.scrollTo({ top: 0 });
  };
  $('#hm-login').addEventListener('click', () => { mode = 'in'; paint(); openAuth(); $('#au-email').focus(); });
  $('#hm-signup').addEventListener('click', () => { mode = 'up'; paint(); openAuth(); $('#au-email').focus(); });
  $('#au-back').addEventListener('click', () => { document.body.classList.remove('authing'); window.scrollTo({ top: 0 }); });
  $('#au-alt').addEventListener('click', () => { mode = mode === 'in' ? 'up' : 'in'; paint(); });
  $('#au-forgot').addEventListener('click', () => { mode = 'reset'; paint(); });
  $('#au-show').addEventListener('click', () => {
    const on = $('#au-pass').type === 'password';
    $('#au-pass').type = on ? 'text' : 'password';
    $('#au-show').setAttribute('aria-pressed', String(on));
    $('#au-show').textContent = on ? 'Hide password' : 'Show password';
  });
  $('#au-resend').addEventListener('click', async () => {
    const b = $('#au-resend');
    b.disabled = true;
    say('One moment…');
    let res;
    try {
      const captchaToken = await YC_CAPTCHA.get();
      res = await sb.auth.resend({ type: 'signup', email: sentTo, options: { emailRedirectTo: cfg.appUrl, captchaToken } });
    } catch (e) { res = { error: e }; }
    YC_CAPTCHA.spent();
    b.disabled = false;
    if (res && res.error) say(/rate limit/i.test(res.error.message || '') ? 'Too many tries. Wait a few minutes and try again.' : 'The email could not be sent. Try again in a minute.', true);
    else say('Sent again to ' + sentTo + '. Check your spam folder too.', false, true);
  });
  $('#au-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const em = $('#au-email').value.trim();
    const pw = $('#au-pass').value;
    if (mode !== 'newpass' && !/^\S+@\S+\.\S+$/.test(em)) { say('Enter your email address.', true); $('#au-email').focus(); return; }
    if (mode !== 'reset' && pw.length < 8) { say('Use a password of at least 8 characters.', true); $('#au-pass').focus(); return; }
    const go = $('#au-go');
    go.disabled = true;
    say('One moment…');
    let res;
    let captchaToken;
    if (mode !== 'newpass') {
      const slow = setTimeout(() => say('Tick the box above to continue.'), 3000);
      try { captchaToken = await YC_CAPTCHA.get(); clearTimeout(slow); } catch (e) {
        clearTimeout(slow);
        go.disabled = false;
        say(e && e.message === 'captcha-timeout' ? 'The human check did not finish. Reload the page and try again.' : 'The human check could not run. Turn off content blockers for this site and try again.', true);
        YC_CAPTCHA.mount($('#au-cap'));
        return;
      }
    }
    try {
      if (mode === 'in') res = await sb.auth.signInWithPassword({ email: em, password: pw, options: { captchaToken } });
      else if (mode === 'up') res = await sb.auth.signUp({ email: em, password: pw, options: { emailRedirectTo: cfg.appUrl, captchaToken } });
      else if (mode === 'reset') res = await sb.auth.resetPasswordForEmail(em, { redirectTo: cfg.appUrl, captchaToken });
      else res = await sb.auth.updateUser({ password: pw });
    } catch (e) { res = { error: e }; }
    if (mode !== 'newpass') YC_CAPTCHA.spent();
    go.disabled = false;
    if (res.error) {
      const m = res.error.message || '';
      say(/invalid login/i.test(m) ? 'Email or password is wrong.' : /already registered/i.test(m) ? 'That email already has an account. Sign in instead.' : /captcha/i.test(m) ? 'The human check failed. Try again.' : /rate limit/i.test(m) ? 'Too many tries. Wait a few minutes and try again.' : !navigator.onLine ? 'No connection. Try again when you are online.' : m, true);
      return;
    }
    if (mode === 'reset') { say('If that email has an account, a reset link is on its way.'); return; }
    if (mode === 'up' && !(res.data && res.data.session)) {
      mode = 'in'; paint();
      sentTo = em;
      say('We sent a confirmation link to ' + em + '. Open it, then sign in here.', false, true);
      $('#au-resend').hidden = false;
      return;
    }
    if (mode === 'newpass') { history.replaceState(null, '', location.pathname); start(res.data.user); }
  });

  // ------------------------------------------------------------------ account section in Settings
  const accountSection = () => {
    const wrap = $('#v-settings .set-wrap');
    if (!wrap || $('#acct')) return;
    const sec = document.createElement('section');
    sec.id = 'acct';
    sec.setAttribute('aria-labelledby', 'h-acct');
    sec.innerHTML = '<h2 id="h-acct">Account</h2><p class="note" id="acct-who"></p>'
      + '<div class="ex-acts"><button class="skew" type="button" id="acct-out"><span>Sign out</span></button>'
      + '<button class="skew danger" type="button" id="acct-del"><span>Delete my account</span></button></div>'
      + '<p class="note" id="acct-msg" aria-live="polite"></p><p class="note"><a class="link" href="privacy.html">Privacy</a></p>';
    wrap.prepend(sec);
    $('#acct-who').textContent = 'Signed in as ' + email + '. Your data syncs between your devices.';
    $('#acct-out').addEventListener('click', async () => { await sb.auth.signOut(); location.reload(); });
    let armed = 0;
    $('#acct-del').addEventListener('click', async () => {
      if (!armed) {
        armed = setTimeout(() => { armed = 0; $('#acct-del span').textContent = 'Delete my account'; $('#acct-msg').textContent = ''; }, 6000);
        $('#acct-del span').textContent = 'Tap again to delete everything';
        $('#acct-msg').textContent = 'This deletes your account, your log, your plan and your notes for good. Make a Full backup first if you may want them back.';
        return;
      }
      clearTimeout(armed);
      $('#acct-msg').textContent = 'Deleting…';
      try { await call(sb.rpc('delete_me')); await sb.auth.signOut(); location.reload(); } catch (e) { $('#acct-msg').textContent = 'Not deleted: ' + e.message; }
    });
  };

  // ------------------------------------------------------------------ start
  let started = false;
  const start = async (user) => {
    if (started || !user) return;
    started = true;
    uid = user.id;
    email = user.email || '';
    document.body.classList.remove('signed-out', 'authing');
    $('#auth').hidden = true;
    try { await resync(); } catch (e) { /* the app shows what it can; writes retry */ }
    startSync();
    accountSection();
    resolveSignedIn();
  };
  sb.auth.onAuthStateChange((event, session) => {
    if (event === 'PASSWORD_RECOVERY') { mode = 'newpass'; paint(); $('#auth').hidden = false; document.body.classList.add('signed-out'); openAuth(); return; }
    if (session && mode !== 'newpass') start(session.user);
  });
  sb.auth.getSession().then(({ data }) => {
    if (data && data.session && mode !== 'newpass') start(data.session.user);
    else if (!started) { $('#auth').hidden = false; paint(); }
  });
})();
