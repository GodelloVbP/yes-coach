// Tests for the connector against a mock Supabase (auth + PostgREST with the same row-level rule as schema.sql).
// Run: node --experimental-strip-types --no-warnings supabase/tests/mcp.test.mjs
import http from 'node:http';
import assert from 'node:assert/strict';
import { createHandler } from '../functions/mcp/index.ts';

const USERS = { 'tok.anna.x': 'u-anna', 'tok.ben.x': 'u-ben' };
const rows = []; // {user_id, path, data, updated_at}
const seed = (u, path, data) => rows.push({ user_id: u, path, data, updated_at: 'x' });
let authCalls = 0;

const like = (path, pat) => path.startsWith(pat.replace(/\*$/, ''));
const mock = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const tok = (req.headers.authorization || '').replace('Bearer ', '');
  const uid = USERS[tok];
  const send = (code, body) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(body == null ? '' : JSON.stringify(body)); };
  let buf = '';
  req.on('data', (c) => (buf += c));
  req.on('end', () => {
    if (url.pathname === '/auth/v1/user') { authCalls += 1; return uid ? send(200, { id: uid }) : send(401, { msg: 'bad' }); }
    if (!uid) return send(401, { message: 'JWT' });
    if (url.pathname !== '/rest/v1/docs') return send(404, {});
    if (req.method === 'GET') {
      let out = rows.filter((r) => r.user_id === uid); // row-level security
      for (const [k, v] of url.searchParams.getAll('path').map((x) => ['path', x])) {
        const [op, ...rest] = v.split('.'); const val = rest.join('.');
        if (op === 'like') out = out.filter((r) => like(r.path, val));
        if (op === 'eq') out = out.filter((r) => r.path === val);
        if (op === 'gte') out = out.filter((r) => r.path >= val);
        if (op === 'lte') out = out.filter((r) => r.path <= val);
      }
      out.sort((a, b) => (a.path < b.path ? -1 : 1) * (url.searchParams.get('order') === 'path.desc' ? -1 : 1));
      if (url.searchParams.get('limit')) out = out.slice(0, +url.searchParams.get('limit'));
      return send(200, out.map((r) => ({ path: r.path, data: r.data })));
    }
    if (req.method === 'POST') {
      const b = JSON.parse(buf);
      if (b.user_id !== uid) return send(403, { message: 'rls' }); // with check (user_id = auth.uid())
      const i = rows.findIndex((r) => r.user_id === uid && r.path === b.path);
      if (i >= 0) rows[i] = b; else rows.push(b);
      return send(201, null);
    }
    send(405, {});
  });
});
await new Promise((r) => mock.listen(0, r));
const base = 'http://127.0.0.1:' + mock.address().port;
const PUB = 'https://fn.example/functions/v1/mcp';
const handler = createHandler({ url: base, anonKey: 'anon', publicUrl: PUB });

let id = 0;
const post = (tok, body) => handler(new Request(PUB, { method: 'POST', headers: { 'content-type': 'application/json', ...(tok ? { authorization: 'Bearer ' + tok } : {}) }, body: JSON.stringify(body) }));
const rpc = async (tok, method, params) => { const r = await post(tok, { jsonrpc: '2.0', id: ++id, method, params }); return { status: r.status, body: await r.json().catch(() => null) }; };
const call = async (tok, name, args = {}) => {
  const { body } = await rpc(tok, 'tools/call', { name, arguments: args });
  const t = body.result.content[0].text;
  return { err: !!body.result.isError, text: t, json: body.result.isError ? null : JSON.parse(t) };
};
let n = 0; const ok = (c, m) => { n += 1; assert.ok(c, m); };

// ---- data
const ex = (name, group, unit = 'kg') => ({ name, group, unit, category: 'strength' });
const A = 'u-anna', B = 'u-ben';
seed(A, 'yc', { app: 'yes-coach', profile: { goal: 'strength', days_per_week: 3 }, schedule: { enabled: true, mode: 'rotation', days: ['Mon', 'Wed', 'Fri'], rotation: ['day-1', 'day-2'] }, intro_seen: true });
seed(A, 'yc/exercises/bench', ex('Bench press', 'Chest'));
seed(A, 'yc/exercises/row', ex('Row', 'Back'));
seed(A, 'yc/exercises/pullup', ex('Pull-up', 'Back', 'bw'));
seed(A, 'yc/templates/day-1', { name: 'Push', order: 1, kind: 'Push', focus: 'Chest', items: [{ ex: 'bench', order: 1, sets: 3, reps: '8', target: '60', rest_s: 120, note: 'Slow down' }] });
seed(A, 'yc/templates/day-2', { name: 'Pull', order: 2, kind: 'Pull', focus: 'Back', items: [{ ex: 'row', order: 1, sets: 3, reps: '10', target: '50', rest_s: 90, note: null }] });
const sess = (date, sets, extra = {}) => ({ date, label: 'Push', template: 'day-1', finished_at: 1, sets, ...extra });
seed(A, 'yc/sessions/2026-10-01', sess('2026-10-01', { a: { ex: 'bench', n: 1, order: 1, kind: 'work', reps: 8, load: 60, done: true }, b: { ex: 'bench', n: 2, order: 2, kind: 'work', reps: 6, load: 65, done: true }, w: { ex: 'bench', n: 0, order: 0, kind: 'warmup', reps: 10, load: 30, done: true }, z: { ex: 'bench', n: 3, order: 3, kind: 'work', reps: 5, load: 70, done: false } }));
seed(A, 'yc/sessions/2026-10-08~day-1', sess('2026-10-08', { a: { ex: 'bench', n: 1, order: 1, kind: 'work', reps: 8, load: 62.5, done: true }, p: { ex: 'pullup', n: 1, order: 2, kind: 'work', reps: 7, done: true } }));
seed(A, 'yc/sessions/2026-10-15', sess('2026-10-15', { a: { ex: 'row', n: 1, order: 1, kind: 'work', reps: 10, load: 50, done: true } }, { template: 'day-2', label: 'Pull' }));
seed(A, 'yc/notes/n1', { text: 'Shoulder pinches on bench', about: 'bench', about_label: 'Bench press', date: '2026-10-08', status: 'new' });
seed(A, 'yc/notes/n2', { text: 'Fine', date: '2026-10-01', status: 'seen', reply: 'Good' });
seed(B, 'yc', { profile: { goal: 'secret-ben' } });
seed(B, 'yc/exercises/squat', ex('Squat', 'Legs'));
seed(B, 'yc/notes/n1', { text: 'ben private', status: 'new' });
const snapshot = () => JSON.stringify(rows.filter((r) => r.user_id === A && r.path.startsWith('yc/sessions/')));

// ---- protocol + auth
{
  let r = await rpc(null, 'initialize', {});
  ok(r.status === 401, 'no token -> 401');
  const resp = await post(null, { jsonrpc: '2.0', id: 1, method: 'ping' });
  ok(resp.headers.get('www-authenticate') === `Bearer resource_metadata="${PUB}/.well-known/oauth-protected-resource"`, 'www-authenticate header');
  ok(resp.headers.get('access-control-expose-headers').includes('www-authenticate'), 'cors exposes header');
  ok((await rpc('bad.tok.x', 'ping')).status === 401, 'bad token -> 401');
  const calls0 = authCalls; ok((await rpc('notajwt', 'ping')).status === 401 && authCalls === calls0, 'a token that is not shaped like a JWT is refused without asking Supabase');
  const meta = await handler(new Request(PUB + '/.well-known/oauth-protected-resource'));
  const mj = await meta.json();
  ok(meta.status === 200 && mj.resource === PUB && mj.authorization_servers[0] === base + '/auth/v1', 'resource metadata');
  ok((await handler(new Request(PUB, { method: 'OPTIONS' }))).status === 204, 'options');
  ok((await handler(new Request(PUB, { method: 'GET' }))).status === 405, 'GET 405');
  r = await rpc('tok.anna.x', 'initialize', { protocolVersion: '2025-06-18' });
  ok(r.body.result.protocolVersion === '2025-06-18' && r.body.result.serverInfo.name === 'yes-coach' && r.body.result.capabilities.tools, 'initialize');
  ok((await rpc('tok.anna.x', 'initialize', { protocolVersion: '1999-01-01' })).body.result.protocolVersion === '2025-06-18', 'unknown version falls back');
  const note = await post('tok.anna.x', { jsonrpc: '2.0', method: 'notifications/initialized' });
  ok(note.status === 202, 'notification 202');
  ok((await rpc('tok.anna.x', 'nope')).body.error.code === -32601, 'unknown method');
  const bad = await handler(new Request(PUB, { method: 'POST', headers: { authorization: 'Bearer tok.anna.x' }, body: '{' }));
  ok(bad.status === 400, 'parse error');
  const batch = await post('tok.anna.x', [{ jsonrpc: '2.0', id: 1, method: 'ping' }, { jsonrpc: '2.0', method: 'notifications/initialized' }]);
  ok((await batch.json()).length === 1, 'batch drops notifications');
  const big = await handler(new Request(PUB, { method: 'POST', headers: { authorization: 'Bearer tok.anna.x' }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'ping', pad: 'x'.repeat(250000) }) }));
  ok(big.status === 413, 'oversized request refused');
  ok((await post('tok.anna.x', Array.from({ length: 21 }, (_, i) => ({ jsonrpc: '2.0', id: i, method: 'ping' })))).status === 400, 'huge batch refused');
  const before = authCalls; await rpc('tok.anna.x', 'ping'); await rpc('tok.anna.x', 'ping');
  ok(authCalls === before, 'token check is cached');
  const list = await rpc('tok.anna.x', 'tools/list');
  const names = list.body.result.tools.map((t) => t.name);
  ok(names.length === 10 && !names.some((x) => /delete|remove|session/.test(x) && x !== 'get_sessions'), 'tool list: ' + names);
  ok(list.body.result.tools.every((t) => t.inputSchema.type === 'object' && t.annotations && t.description && t.title && t.annotations.title === t.title && t.name.length <= 64 && (t.annotations.readOnlyHint === true || typeof t.annotations.destructiveHint === 'boolean')), 'schemas, titles, hints');
  const toolNames = list.body.result.tools.map((t) => t.name);
  ok(list.body.result.tools.every((t) => !toolNames.some((n) => n !== t.name && (t.description + JSON.stringify(t.inputSchema)).includes(n))), 'descriptions do not mention other tools');
  ok(list.body.result.tools.every((t) => !/\b(always|never|must|should|instruction|ignore|before calling|call this)/i.test(t.description)), 'descriptions are plain, no directives');
  const init = (await rpc('tok.anna.x', 'initialize', {})).body.result.instructions;
  ok(!/\b(call|first|never|must|should)\b/i.test(init), 'server instructions are descriptive: ' + init);
  ok(list.body.result.tools.filter((t) => t.annotations.destructiveHint === true).map((t) => t.name).sort().join() === 'answer_note,save_training_day,set_schedule', 'overwriting tools are destructive');
  ok(list.body.result.tools.filter((t) => t.annotations.readOnlyHint).length === 6, 'read-only hints');
  ok((await rpc('tok.anna.x', 'tools/call', { name: 'zzz' })).body.error.code === -32602, 'unknown tool');
}

// ---- reads
{
  const o = (await call('tok.anna.x', 'get_overview')).json;
  ok(o.profile.goal === 'strength' && o.training_days.length === 2 && o.training_days[0].in_week, 'overview');
  ok(o.recent_sessions.length === 3 && o.recent_sessions[0].date === '2026-10-15', 'recent newest first');
  ok(o.notes_waiting === 1, 'one note waiting');
  ok(!JSON.stringify(o).includes('secret-ben') && !JSON.stringify(o).includes('ben private'), 'no leak of other user');
  const p = (await call('tok.anna.x', 'get_plan')).json;
  ok(p.schedule.mode === 'rotation' && p.schedule.rotation[0] === 'Push (day-1)', 'schedule words');
  ok(p.days[0].exercises[0].exercise === 'Bench press' && p.days[0].exercises[0].target_kg === '60', 'plan day');
  const e = (await call('tok.anna.x', 'list_exercises')).json;
  ok(e.length === 3 && e[0].name === 'Bench press' && !e.some((x) => x.name === 'Squat'), 'exercises scoped to user');
  const s = (await call('tok.anna.x', 'get_sessions', { limit: 10 })).json;
  ok(s.length === 3 && s[0].date === '2026-10-15', 'sessions newest first');
  const s1 = s.find((x) => x.date === '2026-10-01');
  ok(s1.exercises[0].sets.length === 3 && !s1.exercises[0].sets.some((t) => t.load === 70), 'unticked set left out');
  ok(s1.exercises[0].sets[0].type === 'warmup', 'warmup typed');
  ok((await call('tok.anna.x', 'get_sessions', { from: '2026-10-08', to: '2026-10-08' })).json.length === 1, 'date filter incl. suffixed path');
  ok((await call('tok.anna.x', 'get_sessions', { from: 'nope' })).err, 'bad date rejected');
  ok((await call('tok.anna.x', 'get_sessions', { limit: 1 })).json.length === 1, 'limit');
  const h = (await call('tok.anna.x', 'get_exercise_history', { exercise_id: 'bench' })).json;
  ok(h.sessions.length === 2 && h.sessions[0].date === '2026-10-08' && h.sessions[1].best.load === 65 && h.sessions[1].working_sets === 2, 'history ignores warmup + unticked');
  ok(h.sessions[1].best.estimated_1rm === 78, 'epley ' + h.sessions[1].best.estimated_1rm);
  const hb = (await call('tok.anna.x', 'get_exercise_history', { exercise_id: 'pullup' })).json;
  ok(hb.sessions[0].best.reps === 7 && hb.sessions[0].best.estimated_1rm === null, 'bodyweight history');
  ok((await call('tok.anna.x', 'get_exercise_history', { exercise_id: 'squat' })).err, 'other user exercise unknown');
  const nt = (await call('tok.anna.x', 'get_notes')).json;
  ok(nt.length === 1 && nt[0].note_id === 'n1', 'waiting notes');
  ok((await call('tok.anna.x', 'get_notes', { only_waiting: false })).json.length === 2, 'all notes');
  ok((await call('tok.ben.x', 'get_notes')).json[0].text === 'ben private', 'ben sees his own');
}

// ---- writes
{
  const sessionsBefore = snapshot();
  let r = await call('tok.anna.x', 'create_exercise', { name: 'Lateral raise', group: 'Shoulders' });
  ok(r.json.id === 'lateral-raise' && r.json.created, 'create exercise');
  ok((await call('tok.anna.x', 'create_exercise', { name: ' lateral RAISE ' })).json.created === false, 'dedupe by name');
  ok((await call('tok.anna.x', 'create_exercise', { name: '' })).err, 'empty name rejected');
  ok((await call('tok.ben.x', 'list_exercises')).json.length === 1, 'ben unaffected');
  r = await call('tok.anna.x', 'save_training_day', { name: 'Shoulders', kind: 'Push', focus: 'Delts', exercises: [{ exercise_id: 'lateral-raise', sets: 99, reps: '12', target_kg: '8', rest_s: 5000, note: 'x'.repeat(300) }, { exercise_id: 'bench', sets: 3, reps: '5' }] });
  ok(!r.err && r.json.day.id === 'day-3' && r.json.created && !r.json.day.in_week, r.text);
  const t = rows.find((x) => x.user_id === A && x.path === 'yc/templates/day-3').data;
  ok(t.items[0].sets === 8 && t.items[0].rest_s === 600 && t.items[0].note.length === 140 && t.order === 3 && t.items[1].order === 2, 'clamped like the app');
  ok((await call('tok.anna.x', 'save_training_day', { name: 'X', exercises: [{ exercise_id: 'ghost', sets: 3, reps: '5' }] })).err, 'unknown exercise rejected');
  ok((await call('tok.anna.x', 'save_training_day', { name: 'X', exercises: [] })).err, 'empty day rejected');
  ok((await call('tok.anna.x', 'save_training_day', { id: 'day-9', name: 'X', exercises: [{ exercise_id: 'bench', sets: 3, reps: '5' }] })).err, 'unknown day id rejected');
  ok((await call('tok.anna.x', 'save_training_day', { name: 'X', exercises: [{ exercise_id: 'squat', sets: 3, reps: '5' }] })).err, 'other user exercise rejected');
  r = await call('tok.anna.x', 'save_training_day', { id: 'day-1', name: 'Push A', exercises: [{ exercise_id: 'bench', sets: 4, reps: '6', target_kg: '62.5' }] });
  const t1 = rows.find((x) => x.user_id === A && x.path === 'yc/templates/day-1').data;
  ok(!r.err && !r.json.created && t1.name === 'Push A' && t1.order === 1 && t1.kind === 'Push' && t1.items.length === 1 && t1.focus === 'Chest', 'replace keeps order/kind/focus');
  ok(!rows.some((x) => x.user_id === B && x.path.startsWith('yc/templates/')), 'nothing written to ben');

  const rootBefore = JSON.parse(JSON.stringify(rows.find((x) => x.user_id === A && x.path === 'yc').data));
  r = await call('tok.anna.x', 'set_schedule', { mode: 'fixed', week: { Mon: 'day-1', Thu: 'day-2', Sat: 'day-3' } });
  const root = rows.find((x) => x.user_id === A && x.path === 'yc').data;
  ok(!r.err && root.schedule.mode === 'fixed' && root.schedule.week.Thu === 'day-2' && root.schedule.week.Tue === '', 'fixed schedule');
  ok(JSON.stringify(root.schedule_before) === JSON.stringify(rootBefore.schedule) && root.profile.goal === 'strength' && root.intro_seen, 'undo copy kept, rest of root kept');
  ok(r.json.schedule.week.Tue === 'rest' && r.json.schedule.week.Mon === 'Push A (day-1)', 'schedule echo');
  r = await call('tok.anna.x', 'set_schedule', { mode: 'rotation', weekdays: ['Fri', 'Mon', 'Mon', 'Wed'], day_ids: ['day-1', 'day-2', 'day-3'] });
  ok(!r.err && JSON.stringify(rows.find((x) => x.user_id === A && x.path === 'yc').data.schedule.days) === '["Mon","Wed","Fri"]', 'rotation sorted, deduped');
  ok((await call('tok.anna.x', 'set_schedule', { mode: 'rotation', weekdays: ['Mon'], day_ids: ['nope'] })).err, 'unknown day in schedule');
  ok((await call('tok.anna.x', 'set_schedule', { mode: 'rotation', weekdays: [], day_ids: ['day-1'] })).err, 'rotation needs weekdays');
  ok((await call('tok.anna.x', 'set_schedule', { mode: 'fixed', week: {} })).err, 'fixed needs a day');
  ok((await call('tok.anna.x', 'set_schedule', { mode: 'weird' })).err, 'bad mode');

  r = await call('tok.anna.x', 'answer_note', { note_id: 'n1', reply: 'Try a narrower grip.' });
  const nn = rows.find((x) => x.user_id === A && x.path === 'yc/notes/n1').data;
  ok(!r.err && nn.reply === 'Try a narrower grip.' && nn.status === 'seen' && nn.text === 'Shoulder pinches on bench', 'note answered');
  ok((await call('tok.anna.x', 'get_overview')).json.notes_waiting === 0, 'no notes waiting');
  ok((await call('tok.anna.x', 'answer_note', { note_id: 'zzz', reply: 'x' })).err, 'unknown note');
  ok((await call('tok.anna.x', 'answer_note', { note_id: 'n1', reply: '  ' })).err, 'empty reply');
  r = await call('tok.anna.x', 'answer_note', { note_id: 'n1', reply: 'x' }); // ben has a note n1 too
  ok(rows.find((x) => x.user_id === B && x.path === 'yc/notes/n1').data.text === 'ben private' && !rows.find((x) => x.user_id === B && x.path === 'yc/notes/n1').data.reply, 'ben note untouched');
  ok(snapshot() === sessionsBefore, 'logged sessions never changed');
}

// ---- database errors surface as tool errors, not crashes
{
  const h2 = createHandler({ url: base, anonKey: 'anon', publicUrl: PUB }, async (u, i) => (String(u).includes('/rest/') ? new Response('{}', { status: 500 }) : fetch(u, i)));
  const r = await h2(new Request(PUB, { method: 'POST', headers: { authorization: 'Bearer tok.anna.x' }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'get_plan', arguments: {} } }) }));
  const j = await r.json();
  ok(r.status === 200 && j.result.isError && /database said no/.test(j.result.content[0].text), 'db failure -> tool error');
}

console.log(n + ' checks passed');
mock.close();
