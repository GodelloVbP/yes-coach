// Tests for the calendar link function against a mock Supabase: the calendar_feed() database function answers by token only.
// Run: node --experimental-strip-types --no-warnings supabase/tests/calendar.test.mjs
import http from 'node:http';
import assert from 'node:assert/strict';
import { createHandler } from '../functions/calendar/index.ts';

const TOK = 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718';
const ICS = 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n';
const calls = [];
let status = 200;
const mock = http.createServer((req, res) => {
  let buf = '';
  req.on('data', (c) => (buf += c));
  req.on('end', () => {
    calls.push({ url: req.url, headers: req.headers, body: buf });
    if (status !== 200) { res.writeHead(status); return res.end('{}'); }
    const tok = JSON.parse(buf || '{}').tok;
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify(tok === TOK ? ICS : null));
  });
});
await new Promise((r) => mock.listen(0, r));
const handler = createHandler({ url: 'http://127.0.0.1:' + mock.address().port, anonKey: 'anon-key' });
const get = (path, method = 'GET') => handler(new Request('https://x.supabase.co' + path, { method }));
let n = 0;
const ok = (c, m) => { assert.ok(c, m); n += 1; };

let r = await get('/calendar/' + TOK + '.ics');
ok(r.status === 200 && (await r.text()) === ICS, 'the calendar text by token');
ok(r.headers.get('content-type').startsWith('text/calendar'), 'as a calendar');
ok(calls[0].url === '/rest/v1/rpc/calendar_feed' && calls[0].headers.apikey === 'anon-key' && JSON.parse(calls[0].body).tok === TOK, 'asked the database function with the public key and the token');
r = await get('/functions/v1/calendar/' + TOK);
ok(r.status === 200, 'also without .ics and under /functions/v1');
r = await get('/calendar?t=' + TOK.toUpperCase());
ok(r.status === 200, 'the token in the query, in capitals');
r = await get('/calendar/' + TOK + '.ics', 'HEAD');
ok(r.status === 200 && (await r.text()) === '', 'HEAD has no body');
const before = calls.length;
r = await get('/calendar/' + TOK.replace(/.$/, '0') + '.ics');
ok(r.status === 404, 'a wrong token finds nothing');
for (const bad of ['/calendar', '/calendar/short.ics', '/calendar/' + TOK.slice(1) + '.ics', '/calendar/' + 'g'.repeat(48) + '.ics', '/calendar/../' + TOK + 'x']) {
  const x = await get(bad);
  ok(x.status === 404, 'not a token: ' + bad);
}
ok(calls.length === before + 1, 'a token that is not 48 hex characters never reaches the database');
r = await handler(new Request('https://x.supabase.co/calendar/' + TOK, { method: 'POST' }));
ok(r.status === 405, 'GET and HEAD only');
status = 500;
r = await get('/calendar/' + TOK + '.ics');
ok(r.status === 502, 'a database error is not shown as an empty calendar');
status = 200;
const down = createHandler({ url: 'http://127.0.0.1:1', anonKey: 'k' });
r = await down(new Request('https://x.supabase.co/calendar/' + TOK + '.ics'));
ok(r.status === 502, 'database not reachable');
mock.close();
console.log(n + ' checks passed');
