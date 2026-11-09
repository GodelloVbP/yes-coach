// Yes Coach! rest alerts: sends a Web Push when the rest timer of a person ends while their app is in the background.
// One file, no dependencies. Deploy as the Supabase Edge Function "rest-push" with "Verify JWT" switched off (it checks the sign-in itself):
//   supabase functions deploy rest-push --project-ref <project> --no-verify-jwt
// Secrets (see tools/vapid.mjs): VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT.
//
// The app asks "alert me in N seconds" when it goes to the background during a rest, and cancels when it comes back. The function
// answers at once and keeps waiting in the background (in hops, because an Edge Function can only run so long), then sends an empty
// push (no payload, so nothing about the workout travels through the push service) to the devices the person allowed.
// Every database call carries the person's own token, so row-level security (push.sql) keeps people apart. No admin key is used.

declare const Deno: any;
declare const EdgeRuntime: any;

type Env = { url: string; anonKey: string; vapidPublic: string; vapidPrivate: string; vapidSubject: string; publicUrl?: string };
type Hooks = { sleep: (ms: number) => Promise<void>; waitUntil: (p: Promise<unknown>) => void; now: () => number; hopMs: number };
type Json = any;

const MAX_SECONDS = 900;
const CORS = { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'authorization, content-type, apikey, x-client-info', 'access-control-allow-methods': 'POST, OPTIONS' };
const reply = (body: Json, status = 200) => new Response(body == null ? null : JSON.stringify(body), { status, headers: { ...CORS, ...(body == null ? {} : { 'content-type': 'application/json' }) } });

const enc = new TextEncoder();
const b64u = (bytes: Uint8Array | string): string => {
  const b = typeof bytes === 'string' ? enc.encode(bytes) : bytes;
  let s = '';
  b.forEach((c) => { s += String.fromCharCode(c); });
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};
const fromB64u = (s: string): Uint8Array => {
  const t = s.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(t.padEnd(Math.ceil(t.length / 4) * 4, '='));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
};
const claimsOf = (token: string): Json => { try { return JSON.parse(new TextDecoder().decode(fromB64u(token.split('.')[1]))); } catch (e) { return null; } };

export const createHandler = (env: Env, f: typeof fetch = fetch, hooks: Partial<Hooks> = {}) => {
  const h: Hooks = {
    sleep: hooks.sleep || ((ms) => new Promise((r) => setTimeout(r, ms))),
    waitUntil: hooks.waitUntil || ((p) => { try { EdgeRuntime.waitUntil(p); } catch (e) { p.catch(() => {}); } }),
    now: hooks.now || (() => Date.now()),
    hopMs: hooks.hopMs || 100000,
  };
  let signKey: Promise<CryptoKey> | null = null;
  const key = () => {
    if (!signKey) {
      const pub = fromB64u(env.vapidPublic);
      signKey = crypto.subtle.importKey('jwk', { kty: 'EC', crv: 'P-256', d: env.vapidPrivate, x: b64u(pub.slice(1, 33)), y: b64u(pub.slice(33, 65)), ext: true }, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
    }
    return signKey;
  };
  // the proof for the push service that this server is allowed to send (RFC 8292)
  const vapid = async (endpoint: string): Promise<string> => {
    const head = b64u(JSON.stringify({ typ: 'JWT', alg: 'ES256' }));
    const claims = b64u(JSON.stringify({ aud: new URL(endpoint).origin, exp: Math.floor(h.now() / 1000) + 12 * 3600, sub: env.vapidSubject }));
    const sig = new Uint8Array(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, await key(), enc.encode(head + '.' + claims)));
    return 'vapid t=' + head + '.' + claims + '.' + b64u(sig) + ', k=' + env.vapidPublic;
  };
  const db = (token: string) => async (path: string, init: RequestInit = {}): Promise<Json> => {
    const r = await f(env.url + '/rest/v1/' + path, { ...init, headers: { apikey: env.anonKey, authorization: 'Bearer ' + token, 'content-type': 'application/json', ...((init.headers as Record<string, string>) || {}) } });
    if (!r.ok) throw new Error('database ' + r.status);
    const raw = await r.text();
    return raw ? JSON.parse(raw) : null;
  };
  const who = async (token: string): Promise<string | null> => {
    const c = claimsOf(token);
    if (!c || c.client_id) return null; // a connected AI app has no business here
    const r = await f(env.url + '/auth/v1/user', { headers: { apikey: env.anonKey, authorization: 'Bearer ' + token } }).catch(() => null);
    if (!r || !r.ok) return null;
    const u = await r.json().catch(() => null);
    return u && u.id ? u.id : null;
  };

  const sendAll = async (token: string): Promise<{ sent: number; gone: number }> => {
    const q = db(token);
    const subs: Json[] = (await q('push_subs?select=endpoint')) || [];
    let sent = 0, gone = 0;
    for (const s of subs) {
      try {
        const r = await f(s.endpoint, { method: 'POST', headers: { authorization: await vapid(s.endpoint), ttl: '300', urgency: 'high' } });
        if (r.status === 404 || r.status === 410) { gone += 1; await q('push_subs?endpoint=eq.' + encodeURIComponent(s.endpoint), { method: 'DELETE' }); } else if (r.ok) sent += 1;
      } catch (e) { /* one bad device does not stop the others */ }
    }
    return { sent, gone };
  };
  // wait for the time, in hops; the last hop sends if the alert was not cancelled meanwhile
  const wake = async (token: string, id: string, until: number, selfUrl: string): Promise<void> => {
    const q = db(token);
    let left = until - h.now();
    if (left > 0) await h.sleep(Math.min(left, h.hopMs));
    left = until - h.now();
    const alive = ((await q('rest_alerts?select=id&id=eq.' + encodeURIComponent(id))) || []).length > 0;
    if (!alive) return; // cancelled, or replaced by a newer rest
    if (left > 500) {
      await f(selfUrl, { method: 'POST', headers: { authorization: 'Bearer ' + token, 'content-type': 'application/json' }, body: JSON.stringify({ action: 'continue', id, until }) });
      return;
    }
    await q('rest_alerts?id=eq.' + encodeURIComponent(id), { method: 'DELETE' });
    await sendAll(token);
  };

  return async (req: Request): Promise<Response> => {
    if (req.method === 'OPTIONS') return reply(null, 204);
    if (req.method !== 'POST') return reply({ error: 'POST only' }, 405);
    const token = (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '');
    const uid = token ? await who(token) : null;
    if (!uid) return reply({ error: 'Sign in again.' }, 401);
    let a: Json;
    try { a = await req.json(); } catch (e) { return reply({ error: 'Bad request.' }, 400); }
    const q = db(token);
    const selfUrl = env.publicUrl || req.url;
    try {
      if (a.action === 'schedule') {
        const seconds = Number(a.seconds);
        if (!(seconds >= 1 && seconds <= MAX_SECONDS)) return reply({ error: 'seconds has to be from 1 to ' + MAX_SECONDS + '.' }, 400);
        const subs = (await q('push_subs?select=endpoint&limit=1')) || [];
        if (!subs.length) return reply({ scheduled: false, reason: 'no_devices' });
        await q('rest_alerts?id=not.is.null', { method: 'DELETE' }); // a new rest replaces the one before it
        const until = h.now() + Math.round(seconds * 1000);
        const rows = await q('rest_alerts', { method: 'POST', headers: { prefer: 'return=representation' }, body: JSON.stringify({ fire_at: new Date(until).toISOString() }) });
        const id = rows && rows[0] && rows[0].id;
        if (!id) throw new Error('no id');
        h.waitUntil(wake(token, id, until, selfUrl).catch(() => {}));
        return reply({ scheduled: true, id });
      }
      if (a.action === 'continue') {
        const id = String(a.id || '');
        const until = Number(a.until);
        if (!id || !Number.isFinite(until)) return reply({ error: 'Bad request.' }, 400);
        h.waitUntil(wake(token, id, until, selfUrl).catch(() => {}));
        return reply({ ok: true }, 202);
      }
      if (a.action === 'cancel') {
        const id = String(a.id || '');
        if (!id) return reply({ error: 'Bad request.' }, 400);
        await q('rest_alerts?id=eq.' + encodeURIComponent(id), { method: 'DELETE' });
        return reply({ cancelled: true });
      }
      return reply({ error: 'Unknown action.' }, 400);
    } catch (e) {
      return reply({ error: 'Not now. Try again.' }, 502);
    }
  };
};

// Supabase runs the file as a server; tests import createHandler instead
if (typeof Deno !== 'undefined' && Deno.serve && Deno.env) {
  const get = (k: string) => Deno.env.get(k) || '';
  Deno.serve(createHandler({ url: get('SUPABASE_URL'), anonKey: get('YC_ANON_KEY') || get('SUPABASE_ANON_KEY'), vapidPublic: get('VAPID_PUBLIC_KEY'), vapidPrivate: get('VAPID_PRIVATE_KEY'), vapidSubject: get('VAPID_SUBJECT'), publicUrl: get('REST_PUSH_URL') || get('SUPABASE_URL') + '/functions/v1/rest-push' }));
}
