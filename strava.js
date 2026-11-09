// Strava for the web app: connect once, then finished workouts are posted as a Weight Training activity with the sets in the description.
// Needs config.js strava: true, strava.sql and the strava function; without that nothing here shows up.
(function () {
  const cfg = window.YC_CONFIG || {};
  const enabled = () => !!cfg.strava;
  const sb = () => window.YC_API && window.YC_API.sb;
  let known = { v: null, at: 0 };
  const call = async (body) => {
    const { data } = await sb().auth.getSession();
    const token = data && data.session && data.session.access_token;
    if (!token) return { status: 401, json: null };
    const r = await fetch(cfg.supabaseUrl + '/functions/v1/strava', { method: 'POST', headers: { authorization: 'Bearer ' + token, apikey: cfg.supabaseAnonKey, 'content-type': 'application/json' }, body: JSON.stringify(body) });
    return { status: r.status, json: await r.json().catch(() => null) };
  };
  const setKnown = (v) => { known = { v, at: Date.now() }; };
  window.YC_STRAVA = {
    enabled,
    // what was last heard: true, false, or null when not asked yet
    cached: () => known.v,
    status: async () => { if (known.v !== null && Date.now() - known.at < 60000) return known.v; try { const r = await call({ action: 'status' }); setKnown(!!(r.json && r.json.connected)); } catch (e) { /* keep what was known */ } return known.v === true; },
    connect: async () => { try { const r = await call({ action: 'start' }); if (r.json && r.json.url) { window.location.href = r.json.url; return true; } } catch (e) { /* below */ } return false; },
    disconnect: async () => { try { await call({ action: 'disconnect' }); setKnown(false); return true; } catch (e) { return false; } },
    // {ok, id, url} or {ok: false, reason: 'reconnect' | 'busy' | 'error'}
    post: async (p) => {
      try {
        const r = await call({ action: 'post', ...p });
        if (r.json && r.json.posted) { setKnown(true); return { ok: true, id: r.json.id, url: r.json.url }; }
        if (r.status === 409) { setKnown(false); return { ok: false, reason: 'reconnect' }; }
        return { ok: false, reason: r.status === 429 ? 'busy' : 'error' };
      } catch (e) { return { ok: false, reason: 'error' }; }
    },
  };
})();
