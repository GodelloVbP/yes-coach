// Yes Coach! Strava connection: people connect their Strava account once, and finished workouts are posted to it.
// One file, no dependencies. Deploy as the Supabase Edge Function "strava" with "Verify JWT" switched off (it checks the sign-in itself):
//   supabase functions deploy strava --project-ref <project> --no-verify-jwt
// Secrets: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET (from strava.com/settings/api). SUPABASE_SERVICE_ROLE_KEY is there already.
//
// Sign-in with Strava is the usual OAuth redirect: the app asks this function for the address ("start"), the person agrees on Strava,
// Strava sends them back here ("callback") with a code, the function swaps it for tokens and keeps them in strava_links (strava.sql),
// then sends the person back to the app. The tokens never go to the browser. The service key is used only for that table, and only
// after the person's own sign-in token has been checked.
//
// A workout is posted as a Strava activity of the type Weight Training, with the exercises and sets in the description.

declare const Deno: any;

type Env = { url: string; anonKey: string; serviceKey: string; clientId: string; clientSecret: string; publicUrl: string; appUrl: string };
type Json = any;

const SCOPE = 'activity:write';
const STRAVA = 'https://www.strava.com';
const CORS = { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'authorization, content-type, apikey, x-client-info', 'access-control-allow-methods': 'POST, GET, OPTIONS' };
const reply = (body: Json, status = 200) => new Response(body == null ? null : JSON.stringify(body), { status, headers: { ...CORS, ...(body == null ? {} : { 'content-type': 'application/json' }) } });
const enc = new TextEncoder();
const b64u = (bytes: Uint8Array | string): string => {
  const b = typeof bytes === 'string' ? enc.encode(bytes) : bytes;
  let s = '';
  b.forEach((c) => { s += String.fromCharCode(c); });
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};
const fromB64u = (s: string): Uint8Array => { const t = s.replace(/-/g, '+').replace(/_/g, '/'); return Uint8Array.from(atob(t.padEnd(Math.ceil(t.length / 4) * 4, '=')), (c) => c.charCodeAt(0)); };
const claimsOf = (token: string): Json => { try { return JSON.parse(new TextDecoder().decode(fromB64u(token.split('.')[1]))); } catch (e) { return null; } };
const str = (v: Json, max: number): string => (v == null ? '' : String(v).trim().slice(0, max));

export const createHandler = (env: Env, f: typeof fetch = fetch, now: () => number = () => Date.now()) => {
  let hmacKey: Promise<CryptoKey> | null = null;
  const key = () => (hmacKey = hmacKey || crypto.subtle.importKey('raw', enc.encode(env.clientSecret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']));
  // the state that travels through Strava and back: who started it and until when, signed so it can not be made up
  const sign = async (uid: string): Promise<string> => {
    const body = b64u(JSON.stringify({ u: uid, e: now() + 10 * 60 * 1000 }));
    return body + '.' + b64u(new Uint8Array(await crypto.subtle.sign('HMAC', await key(), enc.encode(body))));
  };
  const unsign = async (state: string): Promise<string | null> => {
    const [body, sig] = state.split('.');
    if (!body || !sig) return null;
    let good = false;
    try { good = await crypto.subtle.verify('HMAC', await key(), fromB64u(sig), enc.encode(body)); } catch (e) { return null; }
    if (!good) return null;
    try { const d = JSON.parse(new TextDecoder().decode(fromB64u(body))); return d && d.e > now() && typeof d.u === 'string' ? d.u : null; } catch (e) { return null; }
  };
  const who = async (token: string): Promise<string | null> => {
    const c = claimsOf(token);
    if (!c || c.client_id) return null; // a connected AI app has no business here
    const r = await f(env.url + '/auth/v1/user', { headers: { apikey: env.anonKey, authorization: 'Bearer ' + token } }).catch(() => null);
    if (!r || !r.ok) return null;
    const u = await r.json().catch(() => null);
    return u && u.id ? u.id : null;
  };
  // the links table, with the service key (see strava.sql)
  const links = async (path: string, init: RequestInit = {}): Promise<Json> => {
    const r = await f(env.url + '/rest/v1/strava_links' + path, { ...init, headers: { apikey: env.serviceKey, authorization: 'Bearer ' + env.serviceKey, 'content-type': 'application/json', ...((init.headers as Record<string, string>) || {}) } });
    if (!r.ok) throw new Error('database ' + r.status);
    const raw = await r.text();
    return raw ? JSON.parse(raw) : null;
  };
  const getLink = async (uid: string): Promise<Json | null> => ((await links('?select=*&user_id=eq.' + encodeURIComponent(uid))) || [])[0] || null;
  const saveLink = (uid: string, t: Json, scope: string) => links('?on_conflict=user_id', { method: 'POST', headers: { prefer: 'resolution=merge-duplicates,return=minimal' }, body: JSON.stringify({ user_id: uid, athlete_id: (t.athlete && t.athlete.id) || null, access_token: t.access_token, refresh_token: t.refresh_token, expires_at: new Date(t.expires_at * 1000).toISOString(), scope }) });
  const token = async (body: Record<string, string>): Promise<{ ok: boolean; status: number; json: Json }> => {
    const r = await f(STRAVA + '/oauth/token', { method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ client_id: env.clientId, client_secret: env.clientSecret, ...body }).toString() });
    return { ok: r.ok, status: r.status, json: await r.json().catch(() => null) };
  };
  // why: a short reason for the person (and whoever helps them), never a secret; the app shows it with the error
  const back = (result: string, why = '') => new Response(null, { status: 302, headers: { location: env.appUrl + '?strava=' + result + (why ? '&why=' + encodeURIComponent(why.replace(/[^a-zA-Z0-9_ .-]/g, '').slice(0, 40)) : '') + '#settings', 'cache-control': 'no-store' } });
  // what Strava said was wrong, e.g. "client_secret invalid", without the values themselves
  const stravaWhy = (t: { status: number; json: Json }): string => { const e = t.json && Array.isArray(t.json.errors) ? t.json.errors[0] : null; return 'Strava ' + t.status + (e ? ' ' + str(e.field, 20) + ' ' + str(e.code, 20) : ''); };
  // an access token that is good for a while, refreshed when it is about to end; null when the link is gone or was cancelled in Strava
  const fresh = async (uid: string): Promise<string | null> => {
    const l = await getLink(uid);
    if (!l) return null;
    if (new Date(l.expires_at).getTime() - now() > 120000) return l.access_token;
    const t = await token({ grant_type: 'refresh_token', refresh_token: l.refresh_token });
    if (!t.ok || !t.json || !t.json.access_token) { if (t.status === 400 || t.status === 401) await links('?user_id=eq.' + encodeURIComponent(uid), { method: 'DELETE' }); return null; }
    await saveLink(uid, { ...t.json, athlete: { id: l.athlete_id } }, l.scope);
    return t.json.access_token;
  };

  return async (req: Request): Promise<Response> => {
    if (req.method === 'OPTIONS') return reply(null, 204);
    const url = new URL(req.url);
    // Strava sends the person back here
    if (req.method === 'GET' && url.pathname.endsWith('/callback')) {
      if (url.searchParams.get('error')) return back('denied');
      const uid = await unsign(url.searchParams.get('state') || '');
      const code = url.searchParams.get('code') || '';
      if (!uid || !code) return back('error', !code ? 'no code' : 'state expired or invalid');
      // the person has to have agreed to what the app asks for
      const granted = url.searchParams.get('scope') || '';
      if (!granted.split(',').includes(SCOPE)) return back('scope');
      try {
        const t = await token({ grant_type: 'authorization_code', code });
        if (!t.ok || !t.json || !t.json.access_token) return back('error', stravaWhy(t));
        try { await saveLink(uid, t.json, granted); } catch (e) { return back('error', String((e as Error).message || 'database')); }
        return back('ok');
      } catch (e) { return back('error', 'no answer from Strava'); }
    }
    if (req.method !== 'POST') return reply({ error: 'POST only' }, 405);
    const bearer = (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '');
    const uid = bearer ? await who(bearer) : null;
    if (!uid) return reply({ error: 'Sign in again.' }, 401);
    let a: Json;
    try { a = await req.json(); } catch (e) { return reply({ error: 'Bad request.' }, 400); }
    try {
      if (a.action === 'status') return reply({ connected: !!(await getLink(uid)) });
      if (a.action === 'start') {
        const q = new URLSearchParams({ client_id: env.clientId, redirect_uri: env.publicUrl + '/callback', response_type: 'code', approval_prompt: 'auto', scope: SCOPE, state: await sign(uid) });
        return reply({ url: STRAVA + '/oauth/authorize?' + q.toString() });
      }
      if (a.action === 'disconnect') {
        const l = await getLink(uid);
        if (l) {
          await f(STRAVA + '/oauth/deauthorize', { method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ access_token: l.access_token }).toString() }).catch(() => null);
          await links('?user_id=eq.' + encodeURIComponent(uid), { method: 'DELETE' });
        }
        return reply({ connected: false });
      }
      if (a.action === 'post') {
        const name = str(a.name, 100);
        const description = str(a.description, 3000);
        const seconds = Math.round(Number(a.seconds));
        const start = str(a.start, 25);
        if (!name) return reply({ error: 'The workout needs a name.' }, 400);
        if (!(seconds >= 60 && seconds <= 86400)) return reply({ error: 'seconds has to be from 60 to 86400.' }, 400);
        if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(start) || Number.isNaN(Date.parse(start + 'Z'))) return reply({ error: 'start has to be like 2026-11-09T08:30:00.' }, 400);
        const at = await fresh(uid);
        if (!at) return reply({ error: 'reconnect' }, 409);
        const r = await f(STRAVA + '/api/v3/activities', { method: 'POST', headers: { authorization: 'Bearer ' + at, 'content-type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ name, sport_type: 'WeightTraining', start_date_local: start + 'Z', elapsed_time: String(seconds), description }).toString() });
        if (r.status === 401 || r.status === 403) { await links('?user_id=eq.' + encodeURIComponent(uid), { method: 'DELETE' }); return reply({ error: 'reconnect' }, 409); }
        if (r.status === 429) return reply({ error: 'busy' }, 429);
        const j = await r.json().catch(() => null);
        if (!r.ok || !j || !j.id) return reply({ error: 'Strava did not take it.' }, 502);
        return reply({ posted: true, id: j.id, url: STRAVA + '/activities/' + j.id });
      }
      return reply({ error: 'Unknown action.' }, 400);
    } catch (e) {
      return reply({ error: 'Not now. Try again.' }, 502);
    }
  };
};

if (typeof Deno !== 'undefined' && Deno.serve && Deno.env) {
  const get = (k: string) => Deno.env.get(k) || '';
  const url = get('SUPABASE_URL');
  Deno.serve(createHandler({ url, anonKey: get('YC_ANON_KEY') || get('SUPABASE_ANON_KEY'), serviceKey: get('SUPABASE_SERVICE_ROLE_KEY'), clientId: get('STRAVA_CLIENT_ID'), clientSecret: get('STRAVA_CLIENT_SECRET'), publicUrl: get('STRAVA_PUBLIC_URL') || url + '/functions/v1/strava', appUrl: get('YC_APP_URL') || 'https://godellovbp.github.io/yes-coach/' }));
}
