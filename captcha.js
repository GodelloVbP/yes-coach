// Cloudflare Turnstile. The script loads only when a sign-in form is on screen, so signed-in people never contact Cloudflare.
// Without a site key in config.js everything here is a no-op and Supabase gets no token.
(() => {
  const KEY = (window.YC_CONFIG || {}).turnstileKey;
  const SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
  let loading = null;
  let widget = null;
  let token = null;
  let waiting = [];
  let failed = false;

  const load = () => loading || (loading = new Promise((resolve, reject) => {
    if (window.turnstile) { resolve(); return; }
    const s = document.createElement('script');
    s.src = SRC;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => { loading = null; reject(new Error('captcha-load')); };
    document.head.append(s);
  }));

  const give = (t) => { token = t; if (t) waiting.splice(0).forEach((f) => f.ok(t)); };

  // draw the widget into `box` (once); it stays hidden unless Cloudflare wants an answer from the person
  const mount = async (box) => {
    if (!KEY || widget !== null || !box) return;
    widget = -1;
    failed = false;
    try {
      await load();
      widget = window.turnstile.render(box, {
        sitekey: KEY,
        appearance: 'interaction-only',
        theme: 'auto',
        'refresh-expired': 'auto',
        callback: give,
        'expired-callback': () => { token = null; },
        'error-callback': () => { token = null; },
      });
    } catch (e) { widget = null; failed = true; waiting.splice(0).forEach((w) => w.no(new Error('captcha-load'))); }
  };

  // resolves with a token, undefined when no key is set; rejects when the check cannot run or takes too long
  const get = () => {
    if (!KEY) return Promise.resolve(undefined);
    if (token) return Promise.resolve(token);
    if (failed) return Promise.reject(new Error('captcha-load'));
    return new Promise((ok, no) => {
      const w = { ok, no };
      waiting.push(w);
      setTimeout(() => { const i = waiting.indexOf(w); if (i >= 0) { waiting.splice(i, 1); no(new Error('captcha-timeout')); } }, 20000);
    });
  };

  // a token works once: call this after every request that used it
  const spent = () => {
    token = null;
    if (KEY && widget !== null && widget !== -1 && window.turnstile) { try { window.turnstile.reset(widget); } catch (e) { /* the widget is gone */ } }
  };

  window.YC_CAPTCHA = { enabled: !!KEY, mount, get, spent };
})();
