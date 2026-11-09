// The service worker (sw.js) run against stand-ins for its environment: it keeps the words it is sent, shows them on a push,
// and opens or focuses the app on a click. Run: node tests/sw.test.mjs
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const handlers = {};
const store = new Map();
const shown = [];
const focused = [];
let clients = [];
const opened = [];
const self = {
  addEventListener: (type, fn) => { handlers[type] = fn; },
  skipWaiting: () => {},
  clients: { claim: async () => {}, matchAll: async () => clients, openWindow: async (u) => { opened.push(u); } },
  registration: { showNotification: async (title, opts) => { shown.push({ title, opts }); } },
};
const caches = { open: async () => ({ put: async (req, res) => { store.set(req.url, await res.text()); }, match: async (req) => (store.has(req.url) ? new Response(store.get(req.url)) : undefined) }) };
class Req { constructor(u) { this.url = u; } } // a browser resolves a relative address against the worker's own; here it is only a key
vm.runInNewContext(readFileSync(new URL('../sw.js', import.meta.url), 'utf8'), { self, caches, Request: Req, Response, JSON });

let n = 0; const ok = (c, m) => { n += 1; assert.ok(c, m); };
const run = async (type, ev) => { let p; handlers[type]({ ...ev, waitUntil: (x) => { p = x; } }); await p; };

ok(['install', 'activate', 'message', 'push', 'notificationclick'].every((t) => typeof handlers[t] === 'function'), 'handles install, activate, message, push, click');
await run('push', {});
ok(shown.length === 1 && shown[0].title === 'Rest is over' && shown[0].opts.body === 'Time for the next set.', 'a push before any words were sent still says something: ' + JSON.stringify(shown[0]));
await run('message', { data: { type: 'text', title: 'Die Pause ist vorbei', body: 'Zeit für den nächsten Satz.' } });
await run('push', {});
ok(shown[1].title === 'Die Pause ist vorbei' && shown[1].opts.body === 'Zeit für den nächsten Satz.', 'the words the app sent are used');
ok(shown[1].opts.tag === 'yc-rest' && shown[1].opts.renotify === true, 'one notification at a time, it rings again');
await run('message', { data: { type: 'other', title: 'x', body: 'y' } });
await run('message', { data: { type: 'text', title: 5, body: 'y' } });
await run('push', {});
ok(shown[2].title === 'Die Pause ist vorbei', 'a wrong message changes nothing');
await run('message', { data: { type: 'text', title: 'x'.repeat(500), body: 'y'.repeat(500) } });
await run('push', {});
ok(shown[3].title.length === 80 && shown[3].opts.body.length === 160, 'long words are cut');
let closed = 0;
clients = [];
await run('notificationclick', { notification: { close: () => { closed += 1; } } });
ok(closed === 1 && opened.join() === './', 'a click with no window open starts the app');
clients = [{ focus: async () => { focused.push(1); } }];
await run('notificationclick', { notification: { close: () => { closed += 1; } } });
ok(focused.length === 1 && opened.length === 1, 'a click with the app open focuses it');
console.log(n + ' service worker checks passed');
