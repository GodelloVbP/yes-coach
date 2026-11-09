// Tests for the rest-alert function against a mock Supabase (auth + PostgREST with row-level rule) and a fake push service.
// Run: node --experimental-strip-types --no-warnings supabase/tests/rest-push.test.mjs
import http from 'node:http';
import assert from 'node:assert/strict';
import { generateKeyPairSync, webcrypto } from 'node:crypto';
import { createHandler } from '../functions/rest-push/index.ts';

const b64u = (b) => Buffer.from(b).toString('base64url');
const { privateKey } = generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
const jwk = privateKey.export({ format: 'jwk' });
const pubBytes = Buffer.concat([Buffer.from([4]), Buffer.from(jwk.x, 'base64url'), Buffer.from(jwk.y, 'base64url')]);
const VAPID_PUBLIC = b64u(pubBytes);
const jwt = (uid, extra = {}) => ['x', b64u(JSON.stringify({ sub: uid, role: 'authenticated', ...extra })), 'sig'].join('.').replace(/^x/, b64u('{"alg":"ES256"}'));
const TOK = { anna: jwt('u-anna'), ben: jwt('u-ben'), app: jwt('u-anna', { client_id: 'c-claude' }) };
const USERS = Object.fromEntries(Object.entries(TOK).map(([k, v]) => [v, k === 'ben' ? 'u-ben' : 'u-anna']));

const subs = []; // {user_id, endpoint}
let alerts = []; // {id, user_id, fire_at}
let nextId = 1;
const pushLog = []; // what the fake push service received
let pushStatus = 201;

const push = http.createServer((req, res) => { pushLog.push({ url: req.url, headers: req.headers }); res.writeHead(req.url.includes('gone') ? 410 : pushStatus); res.end(); });
await new Promise((r) => push.listen(0, r));
const pushBase = 'http://127.0.0.1:' + push.address().port;

const mock = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const tok = (req.headers.authorization || '').replace('Bearer ', '');
  const uid = USERS[tok];
  const send = (code, body) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(body == null ? '' : JSON.stringify(body)); };
  let buf = '';
  req.on('data', (c) => (buf += c));
  req.on('end', () => {
    if (url.pathname === '/auth/v1/user') return uid ? send(200, { id: uid }) : send(401, {});
    if (!uid) return send(401, {});
    const t = url.pathname.replace('/rest/v1/', '');
    const mine = (rows) => rows.filter((r) => r.user_id === uid); // row-level security
    const eq = (k) => { const v = url.searchParams.get(k); return v && v.startsWith('eq.') ? v.slice(3) : null; };
    if (t === 'push_subs') {
      if (req.method === 'GET') return send(200, mine(subs).map((s) => ({ endpoint: s.endpoint })));
      if (req.method === 'DELETE') { const e = eq('endpoint'); for (let i = subs.length - 1; i >= 0; i -= 1) if (subs[i].user_id === uid && subs[i].endpoint === e) subs.splice(i, 1); return send(204); }
    }
    if (t === 'rest_alerts') {
      if (req.method === 'GET') { const id = eq('id'); return send(200, mine(alerts).filter((a) => !id || a.id === id).map((a) => ({ id: a.id }))); }
      if (req.method === 'POST') { const row = { id: 'a' + nextId++, user_id: uid, ...JSON.parse(buf) }; alerts.push(row); return send(201, [row]); }
      if (req.method === 'DELETE') { const id = eq('id'); alerts = alerts.filter((a) => !(a.user_id === uid && (id === null || a.id === id))); return send(204); }
    }
    send(404, {});
  });
});
await new Promise((r) => mock.listen(0, r));
const base = 'http://127.0.0.1:' + mock.address().port;

// a clock and a sleep that move together, and the work that was left running in the background
let clock = 1_000_000_000_000;
const slept = [];
const pending = [];
const gates = []; // a sleep lasts until the test lets time pass
const hooks = { now: () => clock, sleep: (ms) => new Promise((res) => gates.push(() => { slept.push(ms); clock += ms; res(); })), waitUntil: (p) => pending.push(p), hopMs: 100000 };
const handler = createHandler({ url: base, anonKey: 'anon', vapidPublic: VAPID_PUBLIC, vapidPrivate: jwk.d, vapidSubject: 'mailto:owner@example.com', publicUrl: 'https://fn.example/rest-push' },
  (u, i) => (String(u).startsWith('https://fn.example/rest-push') ? handler(new Request(u, i)) : fetch(u, i)), hooks);
const call = async (token, body, method = 'POST') => {
  const r = await handler(new Request('https://fn.example/rest-push', { method, headers: { ...(token ? { authorization: 'Bearer ' + token } : {}), 'content-type': 'application/json' }, body: method === 'POST' ? JSON.stringify(body) : undefined }));
  return { status: r.status, json: await r.json().catch(() => null) };
};
const tick = () => new Promise((r) => setTimeout(r, 15));
const settle = async () => { for (let i = 0; i < 50; i += 1) { await tick(); if (gates.length) { gates.shift()(); continue; } if (pending.length) { await pending.shift(); continue; } if (i > 3) break; } };
let n = 0; const ok = (c, m) => { n += 1; assert.ok(c, m); };
const reset = () => { subs.length = 0; alerts = []; pushLog.length = 0; slept.length = 0; gates.length = 0; pending.length = 0; pushStatus = 201; };

// ---- who may ask
reset();
ok((await call(null, { action: 'schedule', seconds: 60 })).status === 401, 'no token');
ok((await call('not-a-jwt', { action: 'schedule', seconds: 60 })).status === 401, 'not a jwt');
ok((await call(jwt('u-nobody'), { action: 'schedule', seconds: 60 })).status === 401, 'unknown user');
ok((await call(TOK.app, { action: 'schedule', seconds: 60 })).status === 401, 'a connected AI app is refused');
ok((await handler(new Request('https://fn.example/rest-push', { method: 'OPTIONS' }))).status === 204, 'preflight answered');
ok((await handler(new Request('https://fn.example/rest-push', { method: 'GET' }))).status === 405, 'POST only');

// ---- nothing to send to
let r = await call(TOK.anna, { action: 'schedule', seconds: 60 });
ok(r.status === 200 && r.json.scheduled === false && r.json.reason === 'no_devices' && alerts.length === 0 && pending.length === 0, 'no device: nothing is scheduled');

// ---- a rest that ends while the app is away
subs.push({ user_id: 'u-anna', endpoint: pushBase + '/phone' }, { user_id: 'u-anna', endpoint: pushBase + '/gone-laptop' }, { user_id: 'u-ben', endpoint: pushBase + '/bens' });
ok((await call(TOK.anna, { action: 'schedule', seconds: 0 })).status === 400 && (await call(TOK.anna, { action: 'schedule', seconds: 5000 })).status === 400 && (await call(TOK.anna, { action: 'schedule', seconds: 'x' })).status === 400, 'seconds are checked');
r = await call(TOK.anna, { action: 'schedule', seconds: 90 });
ok(r.status === 200 && r.json.scheduled === true && r.json.id && alerts.length === 1 && alerts[0].user_id === 'u-anna', 'scheduled: one pending alert for her');
await tick();
ok(pending.length === 1 && pushLog.length === 0 && gates.length === 1, 'the answer comes at once, the waiting goes on in the background');
await settle();
ok(slept.join() === '90000', 'it waited the 90 seconds: ' + slept);
ok(pushLog.length === 2 && pushLog.every((p) => !p.url.includes('bens')), 'her two devices were pushed, not ben\'s');
ok(alerts.length === 0, 'the alert is used up');
ok(!subs.some((s) => s.endpoint.includes('gone')), 'a device the push service says is gone is forgotten');
ok(subs.some((s) => s.endpoint.endsWith('/phone')) && subs.some((s) => s.user_id === 'u-ben'), 'the others stay');

// ---- what the push service receives
const p = pushLog[0];
const m = /^vapid t=([\w-]+)\.([\w-]+)\.([\w-]+), k=([\w-]+)$/.exec(p.headers.authorization || '');
ok(m && m[4] === VAPID_PUBLIC, 'vapid header with the public key');
const claims = JSON.parse(Buffer.from(m[2], 'base64url').toString());
ok(claims.aud === pushBase && claims.sub === 'mailto:owner@example.com' && claims.exp > clock / 1000 && claims.exp - clock / 1000 <= 24 * 3600, 'claims: audience, subject, under 24 h: ' + JSON.stringify(claims));
const pubKey = await webcrypto.subtle.importKey('raw', pubBytes, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']);
ok(await webcrypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, pubKey, Buffer.from(m[3], 'base64url'), Buffer.from(m[1] + '.' + m[2])), 'the signature verifies with the public key');
ok(p.headers.ttl === '300' && p.headers.urgency === 'high', 'ttl and urgency');

// ---- cancelled before it is due
reset(); subs.push({ user_id: 'u-anna', endpoint: pushBase + '/phone' });
r = await call(TOK.anna, { action: 'schedule', seconds: 60 });
const id = r.json.id;
ok((await call(TOK.ben, { action: 'cancel', id })).json.cancelled === true && alerts.length === 1, 'another person cannot cancel it (the row is not theirs)');
ok((await call(TOK.anna, { action: 'cancel', id })).json.cancelled === true && alerts.length === 0, 'she cancels it');
await settle();
ok(pushLog.length === 0, 'a cancelled alert sends nothing');

// ---- a new rest replaces the one before
reset(); subs.push({ user_id: 'u-anna', endpoint: pushBase + '/phone' });
const first = (await call(TOK.anna, { action: 'schedule', seconds: 60 })).json.id;
const second = (await call(TOK.anna, { action: 'schedule', seconds: 30 })).json.id;
ok(alerts.length === 1 && alerts[0].id === second && first !== second, 'one pending alert per person');
await settle();
ok(pushLog.length === 1, 'only the newer rest sends: ' + pushLog.length);

// ---- a long rest is waited out in hops
reset(); subs.push({ user_id: 'u-anna', endpoint: pushBase + '/phone' });
r = await call(TOK.anna, { action: 'schedule', seconds: 250 });
await settle();
ok(slept.join() === '100000,100000,50000' && pushLog.length === 1 && alerts.length === 0, 'three hops, one push, at the end: ' + slept + ' / ' + pushLog.length);
// cancelled between hops
reset(); subs.push({ user_id: 'u-anna', endpoint: pushBase + '/phone' });
r = await call(TOK.anna, { action: 'schedule', seconds: 250 });
await tick(); gates.shift()(); await tick(); await tick(); alerts = []; await settle();
ok(pushLog.length === 0, 'cancelling during a long rest stops the next hop');

// ---- a failing push service does not break anything
reset(); subs.push({ user_id: 'u-anna', endpoint: pushBase + '/phone' }); pushStatus = 500;
await call(TOK.anna, { action: 'schedule', seconds: 10 }); await settle();
ok(subs.length === 1 && alerts.length === 0, 'a 500 from the push service keeps the device');
ok((await call(TOK.anna, { action: 'nope' })).status === 400, 'unknown action');
ok((await handler(new Request('https://fn.example/rest-push', { method: 'POST', headers: { authorization: 'Bearer ' + TOK.anna }, body: 'not json' }))).status === 400, 'bad body');

console.log(n + ' checks passed');
mock.close(); push.close();
