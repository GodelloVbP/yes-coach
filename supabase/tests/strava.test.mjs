// Tests for the strava function against a mock Supabase (auth + the links table) and a fake Strava.
// Run: node --experimental-strip-types --no-warnings supabase/tests/strava.test.mjs
import http from 'node:http';
import assert from 'node:assert/strict';
import { createHandler } from '../functions/strava/index.ts';

const b64u = (b) => Buffer.from(b).toString('base64url');
const jwt = (uid, extra = {}) => [b64u('{"alg":"ES256"}'), b64u(JSON.stringify({ sub: uid, role: 'authenticated', ...extra })), 'sig'].join('.');
const TOK = { anna: jwt('u-anna'), ben: jwt('u-ben'), app: jwt('u-anna', { client_id: 'c-claude' }) };
const USERS = { [TOK.anna]: 'u-anna', [TOK.ben]: 'u-ben', [TOK.app]: 'u-anna' };
const SERVICE = 'service-key-secret';

let rows = []; // strava_links
let dbStatus = 0; // when set, the links table answers with this
const mockLog = [];
const mock = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const tok = (req.headers.authorization || '').replace('Bearer ', '');
  const send = (code, body) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(body == null ? '' : JSON.stringify(body)); };
  let buf = '';
  req.on('data', (c) => (buf += c));
  req.on('end', () => {
    if (url.pathname === '/auth/v1/user') return USERS[tok] ? send(200, { id: USERS[tok] }) : send(401, {});
    if (url.pathname === '/rest/v1/strava_links') {
      mockLog.push({ method: req.method, tok, apikey: req.headers.apikey });
      if (dbStatus) return send(dbStatus, { message: 'no such table' });
      if (tok !== SERVICE) return send(401, { message: 'only the service key may use this table' }); // no policy, roles revoked
      const eq = (k) => { const v = url.searchParams.get(k); return v && v.startsWith('eq.') ? decodeURIComponent(v.slice(3)) : null; };
      if (req.method === 'GET') return send(200, rows.filter((r) => !eq('user_id') || r.user_id === eq('user_id')));
      if (req.method === 'POST') { const b = JSON.parse(buf); rows = rows.filter((r) => r.user_id !== b.user_id).concat(b); return send(201, null); }
      if (req.method === 'DELETE') { rows = rows.filter((r) => r.user_id !== eq('user_id')); return send(204); }
    }
    send(404, {});
  });
});
await new Promise((r) => mock.listen(0, r));
const base = 'http://127.0.0.1:' + mock.address().port;

// a fake Strava, answered inside the fetch the handler is given
const strava = { calls: [], tokenReply: null, activityStatus: 200, nextId: 9001 };
const fakeStrava = async (u, init) => {
  const url = new URL(u);
  const body = init && init.body ? Object.fromEntries(new URLSearchParams(String(init.body))) : {};
  strava.calls.push({ path: url.pathname, body, auth: (init && init.headers && init.headers.authorization) || '' });
  const json = (status, b) => new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } });
  if (url.pathname === '/oauth/token') {
    if (body.client_secret !== 'shh-secret' || body.client_id !== '4242') return json(401, { message: 'bad client' });
    if (strava.tokenReply) return strava.tokenReply(body);
    if (body.grant_type === 'authorization_code') return body.code === 'good-code' ? json(200, { access_token: 'AT1', refresh_token: 'RT1', expires_at: Math.floor(clock / 1000) + 21600, athlete: { id: 777 } }) : json(400, { message: 'bad code' });
    if (body.grant_type === 'refresh_token') return json(200, { access_token: 'AT2', refresh_token: 'RT2', expires_at: Math.floor(clock / 1000) + 21600 });
  }
  if (url.pathname === '/api/v3/activities') return strava.activityStatus === 200 ? json(201, { id: strava.nextId++ }) : json(strava.activityStatus, { message: 'no' });
  if (url.pathname === '/oauth/deauthorize') return json(200, {});
  return json(404, {});
};
let clock = 1_800_000_000_000;
const handler = createHandler({ url: base, anonKey: 'anon', serviceKey: SERVICE, clientId: '4242', clientSecret: 'shh-secret', publicUrl: 'https://fn.example/strava', appUrl: 'https://app.example/' },
  (u, i) => (String(u).startsWith('https://www.strava.com') ? fakeStrava(String(u), i) : fetch(u, i)), () => clock);
const post = async (token, body) => {
  const r = await handler(new Request('https://fn.example/strava', { method: 'POST', headers: { ...(token ? { authorization: 'Bearer ' + token } : {}), 'content-type': 'application/json' }, body: JSON.stringify(body) }));
  const text = await r.text();
  return { status: r.status, text, json: text ? JSON.parse(text) : null };
};
const cb = (params) => handler(new Request('https://fn.example/strava/callback?' + new URLSearchParams(params).toString()));
let n = 0; const ok = (c, m) => { n += 1; assert.ok(c, m); };
const stateOf = async () => new URL((await post(TOK.anna, { action: 'start' })).json.url).searchParams.get('state');
const GOOD = { name: 'Legs', start: '2026-11-09T08:30:00', seconds: 3300, description: 'Leg extension: 25 kg × 10\nSquat: 65 kg × 8' };

// ---- who may ask
ok((await post(null, { action: 'status' })).status === 401, 'no token');
ok((await post('nope', { action: 'status' })).status === 401, 'not a jwt');
ok((await post(TOK.app, { action: 'status' })).status === 401, 'a connected AI app is refused');
ok((await handler(new Request('https://fn.example/strava', { method: 'GET' }))).status === 405, 'GET elsewhere is refused');
ok((await handler(new Request('https://fn.example/strava', { method: 'OPTIONS' }))).status === 204, 'preflight');
ok((await post(TOK.anna, { action: 'nope' })).status === 400, 'unknown action');

// ---- connecting
ok((await post(TOK.anna, { action: 'status' })).json.connected === false, 'not connected at first');
const start = (await post(TOK.anna, { action: 'start' })).json.url;
const su = new URL(start);
ok(su.origin + su.pathname === 'https://www.strava.com/oauth/authorize' && su.searchParams.get('client_id') === '4242' && su.searchParams.get('scope') === 'activity:write' && su.searchParams.get('response_type') === 'code' && su.searchParams.get('redirect_uri') === 'https://fn.example/strava/callback', 'the authorize address asks only for activity:write: ' + start);
ok(!start.includes('shh-secret') && !start.includes(SERVICE), 'no secret in the address');

let r = await cb({ code: 'good-code', state: su.searchParams.get('state'), scope: 'read,activity:write' });
ok(r.status === 302 && r.headers.get('location') === 'https://app.example/?strava=ok#settings', 'back to the app, connected: ' + r.headers.get('location'));
ok(rows.length === 1 && rows[0].user_id === 'u-anna' && rows[0].access_token === 'AT1' && rows[0].athlete_id === 777, 'tokens kept for her');
ok(mockLog.every((m) => m.tok === SERVICE), 'only the service key touched the table');
ok(strava.calls[0].body.code === 'good-code' && strava.calls[0].body.grant_type === 'authorization_code', 'the code was swapped with the secret');
ok((await post(TOK.anna, { action: 'status' })).json.connected === true && (await post(TOK.ben, { action: 'status' })).json.connected === false, 'status is hers only');
const everything = JSON.stringify([(await post(TOK.anna, { action: 'status' })).text, start]);
ok(!/AT1|RT1|shh-secret|service-key/.test(everything), 'no token or secret in anything the browser sees');

// ---- a bad way back
const rowsBefore = JSON.stringify(rows);
const tamper = su.searchParams.get('state').replace(/^./, (c) => (c === 'a' ? 'b' : 'a'));
ok((await cb({ code: 'good-code', state: tamper, scope: 'activity:write' })).headers.get('location').includes('strava=error'), 'a made-up state is refused');
ok((await cb({ code: 'good-code', scope: 'activity:write' })).headers.get('location').includes('strava=error'), 'no state is refused');
ok((await cb({ error: 'access_denied', state: su.searchParams.get('state') })).headers.get('location').includes('strava=denied'), 'the person said no');
const st2 = await stateOf();
ok((await cb({ code: 'good-code', state: st2, scope: 'read' })).headers.get('location').includes('strava=scope'), 'activity:write not granted');
clock += 11 * 60 * 1000;
ok((await cb({ code: 'good-code', state: st2, scope: 'activity:write' })).headers.get('location').includes('strava=error'), 'an old state is refused');
ok(JSON.stringify(rows) === rowsBefore, 'none of that changed what is kept');
clock -= 11 * 60 * 1000;
ok((await cb({ code: 'bad-code', state: await stateOf(), scope: 'activity:write' })).headers.get('location').includes('strava=error'), 'Strava refusing the code is an error');

// ---- an error says why, in a few safe words
const whyOf = (r) => new URL(r.headers.get('location')).searchParams.get('why');
ok(whyOf(await cb({ code: 'bad-code', state: await stateOf(), scope: 'activity:write' })) === 'Strava 400', 'Strava refusing the code: ' + whyOf(await cb({ code: 'bad-code', state: await stateOf(), scope: 'activity:write' })));
strava.tokenReply = () => new Response(JSON.stringify({ message: 'Bad Request', errors: [{ resource: 'Application', field: 'client_secret', code: 'invalid' }] }), { status: 400, headers: { 'content-type': 'application/json' } });
r = await cb({ code: 'good-code', state: await stateOf(), scope: 'activity:write' });
ok(whyOf(r) === 'Strava 400 client_secret invalid' && !r.headers.get('location').includes('shh-secret'), 'a wrong secret says which field: ' + whyOf(r));
strava.tokenReply = null;
dbStatus = 404;
r = await cb({ code: 'good-code', state: await stateOf(), scope: 'activity:write' });
ok(r.headers.get('location').includes('strava=error') && whyOf(r) === 'database 404', 'a missing table says database: ' + whyOf(r));
dbStatus = 0;
ok(whyOf(await cb({ code: 'good-code', scope: 'activity:write' })) === 'state expired or invalid', 'no state says so');

// ---- posting
r = await post(TOK.anna, { action: 'post', ...GOOD, name: '' }); ok(r.status === 400, 'needs a name');
r = await post(TOK.anna, { action: 'post', ...GOOD, seconds: 5 }); ok(r.status === 400, 'too short');
r = await post(TOK.anna, { action: 'post', ...GOOD, seconds: 999999 }); ok(r.status === 400, 'too long');
r = await post(TOK.anna, { action: 'post', ...GOOD, start: 'yesterday' }); ok(r.status === 400, 'start has a format');
strava.calls.length = 0;
r = await post(TOK.anna, { action: 'post', ...GOOD });
const act = strava.calls.find((c) => c.path === '/api/v3/activities');
ok(r.status === 200 && r.json.posted === true && r.json.id === 9001 && r.json.url === 'https://www.strava.com/activities/9001', 'posted: ' + r.text);
ok(act.body.name === 'Legs' && act.body.sport_type === 'WeightTraining' && act.body.start_date_local === '2026-11-09T08:30:00Z' && act.body.elapsed_time === '3300' && act.body.description === GOOD.description && act.auth === 'Bearer AT1', 'the activity: ' + JSON.stringify(act));
ok(!strava.calls.some((c) => c.path === '/oauth/token'), 'a token that is still good is not refreshed');
r = await post(TOK.ben, { action: 'post', ...GOOD });
ok(r.status === 409 && r.json.error === 'reconnect', 'someone who did not connect has to connect first');

// ---- an old token is refreshed, and the new one kept
rows[0].expires_at = new Date(clock - 1000).toISOString(); strava.calls.length = 0;
r = await post(TOK.anna, { action: 'post', ...GOOD });
ok(r.status === 200 && strava.calls[0].body.grant_type === 'refresh_token' && strava.calls[0].body.refresh_token === 'RT1' && strava.calls.find((c) => c.path === '/api/v3/activities').auth === 'Bearer AT2', 'refreshed, then posted with the new token');
ok(rows[0].access_token === 'AT2' && rows[0].refresh_token === 'RT2' && rows[0].athlete_id === 777 && new Date(rows[0].expires_at).getTime() > clock, 'the new tokens are kept');

// ---- when Strava says no
rows[0].expires_at = new Date(clock - 1000).toISOString(); strava.tokenReply = () => new Response('{}', { status: 400 });
r = await post(TOK.anna, { action: 'post', ...GOOD });
ok(r.status === 409 && r.json.error === 'reconnect' && rows.length === 0, 'a refresh Strava refuses drops the link and asks to reconnect');
strava.tokenReply = null;
await cb({ code: 'good-code', state: await stateOf(), scope: 'activity:write' });
strava.activityStatus = 401;
r = await post(TOK.anna, { action: 'post', ...GOOD });
ok(r.status === 409 && rows.length === 0, 'a 401 from Strava drops the link');
await cb({ code: 'good-code', state: await stateOf(), scope: 'activity:write' });
strava.activityStatus = 429;
r = await post(TOK.anna, { action: 'post', ...GOOD });
ok(r.status === 429 && r.json.error === 'busy' && rows.length === 1, 'busy keeps the link');
strava.activityStatus = 500;
r = await post(TOK.anna, { action: 'post', ...GOOD });
ok(r.status === 502 && rows.length === 1, 'a Strava error keeps the link');
strava.activityStatus = 200;

// ---- disconnecting
strava.calls.length = 0;
r = await post(TOK.anna, { action: 'disconnect' });
ok(r.json.connected === false && rows.length === 0 && strava.calls.some((c) => c.path === '/oauth/deauthorize' && c.body.access_token === 'AT1'), 'Strava is told, the tokens are gone');
ok((await post(TOK.anna, { action: 'status' })).json.connected === false, 'and she is disconnected');
ok((await post(TOK.anna, { action: 'disconnect' })).json.connected === false, 'disconnecting twice is fine');

console.log(n + ' checks passed');
mock.close();
