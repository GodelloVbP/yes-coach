// Tests for the calendar feed function against a mock database function (calendar_feed).
// Run: node --experimental-strip-types --no-warnings supabase/tests/cal.test.mjs
import assert from 'node:assert/strict';
import { createHandler } from '../functions/cal/index.ts';

const TOKEN = 'a'.repeat(32) + 'b'.repeat(32);
const ICS = 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n';
const calls = [];
const fakeFetch = (mode = 'ok') => async (url, init) => {
  calls.push({ url, init });
  if (mode === 'down') throw new Error('network');
  if (mode === 'error') return new Response('{}', { status: 500 });
  const { p_token } = JSON.parse(init.body);
  return new Response(JSON.stringify(p_token === TOKEN ? ICS : null), { status: 200, headers: { 'content-type': 'application/json' } });
};
const env = { url: 'https://x.supabase.co', anonKey: 'anon-key' };
const get = (h, path, method = 'GET') => h(new Request('https://x.supabase.co/functions/v1/cal' + path, { method }));

let n = 0;
const ok = async (name, fn) => { await fn(); n += 1; };

await ok('serves the stored file for a good token', async () => {
  const r = await get(createHandler(env, fakeFetch()), '/' + TOKEN + '.ics');
  assert.equal(r.status, 200);
  assert.match(r.headers.get('content-type'), /^text\/calendar/);
  assert.equal(await r.text(), ICS);
});
await ok('works without the .ics ending', async () => {
  assert.equal((await get(createHandler(env, fakeFetch()), '/' + TOKEN)).status, 200);
});
await ok('asks the database with the public key only, at the right function', async () => {
  calls.length = 0;
  await get(createHandler(env, fakeFetch()), '/' + TOKEN + '.ics');
  assert.equal(calls[0].url, 'https://x.supabase.co/rest/v1/rpc/calendar_feed');
  assert.equal(calls[0].init.headers.apikey, 'anon-key');
  assert.equal(JSON.parse(calls[0].init.body).p_token, TOKEN);
});
await ok('an unknown token is a plain 404 and not cached', async () => {
  const r = await get(createHandler(env, fakeFetch()), '/' + 'c'.repeat(64) + '.ics');
  assert.equal(r.status, 404);
  assert.equal(r.headers.get('cache-control'), 'no-store');
  assert.equal(await r.text(), 'Not found');
});
await ok('a malformed token never reaches the database', async () => {
  calls.length = 0;
  for (const p of ['/', '/short.ics', '/' + 'g'.repeat(64) + '.ics', "/" + 'a'.repeat(31), '/' + 'A'.repeat(64)]) assert.equal((await get(createHandler(env, fakeFetch()), p)).status, 404, p);
  assert.equal(calls.length, 0);
});
await ok('a database failure is a 502, not a 404 (the calendar keeps its events)', async () => {
  assert.equal((await get(createHandler(env, fakeFetch('error')), '/' + TOKEN + '.ics')).status, 502);
  assert.equal((await get(createHandler(env, fakeFetch('down')), '/' + TOKEN + '.ics')).status, 502);
});
await ok('HEAD has no body, other methods are refused', async () => {
  const h = createHandler(env, fakeFetch());
  const r = await get(h, '/' + TOKEN + '.ics', 'HEAD');
  assert.equal(r.status, 200);
  assert.equal(await r.text(), '');
  assert.equal((await get(h, '/' + TOKEN + '.ics', 'POST')).status, 405);
});
console.log('passed', n);
