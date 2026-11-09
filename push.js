// Rest alerts for the web app: a notification when the rest timer ends while the app is in the background.
// Needs config.js vapidPublicKey (tools/vapid.mjs), push.sql, and the rest-push function; without the key nothing here shows up.
(function () {
  const cfg = window.YC_CONFIG || {};
  const FLAG = 'yc-push';
  const store = { get: () => { try { return localStorage.getItem(FLAG) === '1'; } catch (e) { return false; } }, set: (on) => { try { if (on) localStorage.setItem(FLAG, '1'); else localStorage.removeItem(FLAG); } catch (e) { /* storage off */ } } };
  const t = (s) => (window.YC_I18N && window.YC_I18N.t && window.YC_I18N.t(s)) || s; // English has no translation: the text itself
  const supported = () => !!(cfg.vapidPublicKey && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window);
  const standalone = () => { try { return navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches; } catch (e) { return false; } };
  // on an iPhone the browser tab can not receive pushes: the app has to be on the home screen first
  const needsInstall = () => !!cfg.vapidPublicKey && /iP(hone|ad|od)/.test(navigator.userAgent) && !standalone() && !('PushManager' in window);
  const key = () => { const s = cfg.vapidPublicKey.replace(/-/g, '+').replace(/_/g, '/'); const bin = atob(s.padEnd(Math.ceil(s.length / 4) * 4, '=')); return Uint8Array.from(bin, (c) => c.charCodeAt(0)); };
  const sb = () => window.YC_API && window.YC_API.sb;
  const reg = async () => { const r = await navigator.serviceWorker.register('sw.js'); await navigator.serviceWorker.ready; return r; };
  // the words for the notification, in the language of the app
  const sendText = async (r) => {
    const w = r.active || r.waiting || r.installing;
    if (w) w.postMessage({ type: 'text', title: t('Rest is over'), body: t('Time for the next set.') });
  };
  const save = async (sub) => {
    const j = sub.toJSON();
    const res = await sb().from('push_subs').upsert({ endpoint: j.endpoint, p256dh: (j.keys && j.keys.p256dh) || '', auth: (j.keys && j.keys.auth) || '' }, { onConflict: 'user_id,endpoint' });
    if (res && res.error) throw res.error;
  };
  const status = async () => {
    if (!supported()) return 'off';
    if (Notification.permission === 'denied') return 'blocked';
    if (!store.get()) return 'off';
    try { const r = await navigator.serviceWorker.getRegistration(); const s = r && (await r.pushManager.getSubscription()); return s ? 'on' : 'off'; } catch (e) { return 'off'; }
  };
  const enable = async () => {
    try {
      const r = await reg();
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') return { ok: false, reason: perm === 'denied' ? 'blocked' : 'dismissed' };
      const sub = (await r.pushManager.getSubscription()) || (await r.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key() }));
      await save(sub);
      await sendText(r);
      store.set(true);
      return { ok: true };
    } catch (e) { return { ok: false, reason: 'error' }; }
  };
  const disable = async () => {
    store.set(false);
    try {
      const r = await navigator.serviceWorker.getRegistration();
      const s = r && (await r.pushManager.getSubscription());
      if (s) { const ep = s.endpoint; await s.unsubscribe(); await sb().from('push_subs').delete().eq('endpoint', ep); }
    } catch (e) { /* the device is forgotten the next time the push service says it is gone */ }
  };
  // after sign-in: keep the saved device and the words up to date (the language may have changed)
  const sync = async () => {
    if (!supported() || !store.get() || Notification.permission !== 'granted') return;
    try { const r = await reg(); const s = await r.pushManager.getSubscription(); if (s) { await save(s); await sendText(r); } else store.set(false); } catch (e) { /* try again next time */ }
  };
  const call = async (body) => {
    const s = sb();
    const { data } = await s.auth.getSession();
    const token = data && data.session && data.session.access_token;
    if (!token) return null;
    const r = await fetch(cfg.supabaseUrl + '/functions/v1/rest-push', { method: 'POST', keepalive: true, headers: { authorization: 'Bearer ' + token, apikey: cfg.supabaseAnonKey, 'content-type': 'application/json' }, body: JSON.stringify(body) });
    return r.ok ? r.json() : null;
  };
  window.YC_PUSH = {
    supported, needsInstall, on: () => supported() && store.get(), status, enable, disable, sync,
    schedule: (seconds) => call({ action: 'schedule', seconds }).then((j) => (j && j.scheduled ? j.id : null)).catch(() => null),
    cancel: (id) => call({ action: 'cancel', id }).catch(() => null),
  };
})();
