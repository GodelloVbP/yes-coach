// Tests for the connector against a mock Supabase (auth + PostgREST with the same row-level rule as schema.sql).
// Run: node --experimental-strip-types --no-warnings supabase/tests/mcp.test.mjs
import http from 'node:http';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHandler } from '../functions/mcp/index.ts';

const USERS = { 'tok.anna.x': 'u-anna', 'tok.ben.x': 'u-ben' };
const rows = []; // {user_id, path, data, updated_at}
const seed = (u, path, data) => rows.push({ user_id: u, path, data, updated_at: 'x' });
let authCalls = 0;

const deepMerge = (a, b) => (a && b && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b) ? Object.fromEntries([...new Set([...Object.keys(a), ...Object.keys(b)])].map((k) => [k, k in a && k in b ? deepMerge(a[k], b[k]) : k in b ? b[k] : a[k]])) : b);
const like = (path, pat) => path.startsWith(pat.replace(/\*$/, ''));
const mock = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const tok = (req.headers.authorization || '').replace('Bearer ', '');
  const uid = USERS[tok];
  const send = (code, body) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(body == null ? '' : JSON.stringify(body)); };
  let buf = '';
  req.on('data', (c) => (buf += c));
  req.on('end', () => setTimeout(() => {
    if (url.pathname.startsWith('/site/')) { // the app's own site: the food tables
      try { const b = readFileSync(new URL('../../' + url.pathname.slice(6), import.meta.url)); res.writeHead(200, { 'content-type': 'application/json' }); return res.end(b); } catch (e) { return send(404, {}); }
    }
    if (url.pathname === '/auth/v1/user') { authCalls += 1; return uid ? send(200, { id: uid }) : send(401, { msg: 'bad' }); }
    if (!uid) return send(401, { message: 'JWT' });
    if (url.pathname === '/rest/v1/rpc/yc_update' && req.method === 'POST') { // the app's merge, under the same row-level rule
      const { p_path, p_patch } = JSON.parse(buf);
      const row = rows.find((r) => r.user_id === uid && r.path === p_path);
      if (!row) return send(404, { code: 'P0002', message: 'not found' });
      row.data = deepMerge(row.data, p_patch);
      return send(200, row.data);
    }
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
      if (i >= 0 && /ignore-duplicates/.test(req.headers.prefer || '')) return send(201, null); // on conflict do nothing
      if (i >= 0) rows[i] = b; else rows.push(b);
      return send(201, null);
    }
    send(405, {});
  }, (url.searchParams.get('path') || '').includes('yc/food/') ? 15 : 0));
});
await new Promise((r) => mock.listen(0, r));
const base = 'http://127.0.0.1:' + mock.address().port;
const PUB = 'https://fn.example/functions/v1/mcp';
const handler = createHandler({ url: base, anonKey: 'anon', publicUrl: PUB, siteUrl: base + '/site/' });

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
const rowA = (path) => rows.find((x) => x.user_id === A && x.path === path);
seed(A, 'yc', { app: 'yes-coach', profile: { goal: 'strength', days_per_week: 3 }, schedule: { enabled: true, mode: 'rotation', days: ['Mon', 'Wed', 'Fri'], rotation: ['day-1', 'day-2'] }, intro_seen: true, settings: { tz: 'Europe/Amsterdam' } });
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
  ok(names.length === 18 && !names.some((x) => /delete|remove|session/.test(x) && !['get_sessions', 'remove_food_entry', 'remove_saved'].includes(x)), 'tool list: ' + names);
  ok(list.body.result.tools.every((t) => t.inputSchema.type === 'object' && t.annotations && t.description && t.title && t.annotations.title === t.title && t.name.length <= 64 && (t.annotations.readOnlyHint === true || typeof t.annotations.destructiveHint === 'boolean')), 'schemas, titles, hints');
  const toolNames = list.body.result.tools.map((t) => t.name);
  ok(list.body.result.tools.every((t) => !toolNames.some((n) => n !== t.name && (t.description + JSON.stringify(t.inputSchema)).includes(n))), 'descriptions do not mention other tools');
  ok(list.body.result.tools.every((t) => !/\b(always|never|must|should|instruction|ignore|before calling|call this)/i.test(t.description)), 'descriptions are plain, no directives');
  const init = (await rpc('tok.anna.x', 'initialize', {})).body.result.instructions;
  ok(!/\b(call|first|never|must|should)\b/i.test(init), 'server instructions are descriptive: ' + init);
  ok(list.body.result.tools.filter((t) => t.annotations.destructiveHint === true).map((t) => t.name).sort().join() === 'answer_note,remove_food_entry,remove_saved,save_meal,save_training_day,set_schedule', 'overwriting tools are destructive');
  ok(list.body.result.tools.find((t) => t.name === 'log_meals').annotations.idempotentHint === false, 'logging a meal twice adds it twice, so it is not idempotent');
  ok(list.body.result.tools.filter((t) => t.annotations.readOnlyHint).length === 9, 'read-only hints');
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

  r = await call('tok.anna.x', 'save_training_day', { name: 'Arms', exercises: [{ exercise_id: 'bench', sets: 3, reps: '5', superset: 'A' }, { exercise_id: 'lateral-raise', sets: 3, reps: '12', superset: 'A' }, { exercise_id: 'bench', sets: 3, reps: '5', superset: 'B' }] });
  const ts = rows.find((x) => x.user_id === A && x.path === 'yc/templates/' + r.json.day.id).data;
  ok(!r.err && ts.items[0].group === 'A' && ts.items[1].group === 'A' && !('group' in ts.items[2]), 'superset kept on neighbours, dropped on a lone item');
  ok(r.json.day.exercises[0].superset === 'A' && r.json.day.exercises[2].superset === null, 'superset is read back');
  r = await call('tok.anna.x', 'save_training_day', { name: 'Split', exercises: [{ exercise_id: 'bench', sets: 3, reps: '5', superset: 'A' }, { exercise_id: 'lateral-raise', sets: 3, reps: '5', superset: 'A' }, { exercise_id: 'bench', sets: 3, reps: '5' }, { exercise_id: 'lateral-raise', sets: 3, reps: '5', superset: 'A' }, { exercise_id: 'bench', sets: 3, reps: '5', superset: 'A' }] });
  const t2 = rows.find((x) => x.user_id === A && x.path === 'yc/templates/' + r.json.day.id).data;
  ok(t2.items[0].group === 'A' && t2.items[3].group && t2.items[3].group !== 'A' && t2.items[3].group === t2.items[4].group, 'a label reused further down is a separate group');

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

// ---- food: search, log, read, remove
{
  const T = 'tok.anna.x';
  const dayIn = (tz) => { const p = new Intl.DateTimeFormat('en-GB', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date()); const g = (t) => p.find((x) => x.type === t).value; return g('year') + '-' + g('month') + '-' + g('day'); };
  const day = dayIn('Europe/Amsterdam'); // her saved time zone
  const foodRow = (u, d) => rows.find((x) => x.user_id === u && x.path === 'yc/food/' + d);
  const search = async (q, limit) => (await call(T, 'search_foods', { query: q, limit })).json;

  // search
  let r = await search('kaas');
  ok(r.results.length === 10 && r.results.every((x) => /^(nevo|usda):/.test(x.food) && x.per_100.protein_g != null && x.portions.length && x.portions_are), 'search: ids, nutrients per 100, portions');
  ok(!('kcal' in r.results[0].per_100) && /hidden/.test(r.calories), 'calories hidden by default, and the result says so');
  ok((await search('kaas', 3)).results.length === 3, 'search limit');
  r = await search('bruin brood');
  ok(r.results.some((x) => x.name === 'Tarwebrood bruin'), 'a Dutch compound word is found by its last part: ' + r.results.map((x) => x.name));
  r = await search('Ei gekookt');
  ok(r.results.length > 0 && /ei/i.test(r.results[0].name), 'search is case and accent tolerant: ' + r.results.map((x) => x.name));
  r = (await call(T, 'search_foods', { query: 'brood', type: 'bread' })).json;
  ok(r.results.length > 0 && r.results.every((x) => x.type === 'Bread') && r.results.some((x) => /brood/i.test(x.name) && !/^Broodje/.test(x.name)), 'a group keeps the search inside it, case-insensitively: ' + r.results.map((x) => x.name));
  r = (await call(T, 'search_foods', { query: 'kaas', type: 'Cheese', limit: 15 })).json;
  ok(r.results.length === 15 && r.results.every((x) => x.type === 'Cheese') && !r.results.some((x) => /^Pindakaas/.test(x.name)), 'kaas inside Cheese leaves out peanut butter');
  r = (await call(T, 'search_foods', { query: 'kaas', type: 'Cars' })).json;
  ok(r.results.length === 0 && /in that group/.test(r.note), 'an unknown group finds nothing and says so');
  r = await search('zzzzqqqq');
  ok(r.results.length === 0 && /Nothing matched/.test(r.note), 'nothing found says so');
  ok((await call(T, 'search_foods', { query: '  ' })).err, 'empty query rejected');
  const pick = async (q) => (await search(q, 1)).results[0];
  const bread = await pick('tarwebrood bruin'), egg = await pick('ei gekookt'), cheese = await pick('kaas goudse 48+'), mustard = await pick('mosterd');
  ok([bread, egg, cheese, mustard].every(Boolean) && /snee|stuk/i.test(bread.portions[0].label), 'the everyday portion of bread comes first: ' + JSON.stringify(bread.portions[0]));

  // log one meal with several foods
  const meal = { name: '2 slices bread with egg, cheese and mustard', items: [{ food: bread.food, portion: { label: bread.portions[0].label, count: 2 } }, { food: egg.food, grams: 50, estimated: false }, { food: cheese.food, grams: 20 }, { food: mustard.food, grams: 5 }] };
  r = await call(T, 'log_meals', { meals: [meal] });
  ok(!r.err, r.text);
  const doc = foodRow(A, day).data, [[id1, e1]] = Object.entries(doc.entries);
  ok(doc.date === day && e1.name === meal.name && e1.items.length === 4 && e1.via === 'connector' && !('src' in e1), 'one entry, with its items inside');
  const bg = bread.portions[0].grams * 2;
  ok(e1.items[0].g === bg && e1.items[0].est === true && e1.items[1].g === 50 && !('est' in e1.items[1]), 'portion times count; estimated unless the weight was said');
  const expectP = Math.round((bread.per_100.protein_g * bg / 100 + egg.per_100.protein_g * 0.5 + cheese.per_100.protein_g * 0.2 + mustard.per_100.protein_g * 0.05) * 10) / 10;
  ok(Math.abs(e1.p - expectP) <= 0.3 && e1.p > 0, 'the entry protein is the sum from the tables: ' + e1.p + ' vs ' + expectP);
  ok(Math.abs(e1.items.reduce((t, i) => t + i.p, 0) - e1.p) <= 0.3, 'entry protein adds up from its items');
  ok(Math.abs(e1.kcal - e1.items.reduce((t, i) => t + i.kcal, 0)) <= 2, 'entry kcal adds up from its items');
  ok(r.json.saved.length === 1 && r.json.saved[0].id === id1 && r.json.saved[0].items.length === 4 && !('kcal' in r.json.saved[0]), 'the reply lists what was saved, without calories');
  ok(r.json.day.totals.protein_g === e1.p && r.json.day.entries.length === 1, 'the reply has the day totals');

  // a second call adds to the same day without touching the first entry
  r = await call(T, 'log_meals', { meals: [{ items: [{ food: (await pick('appel')).food, portion: { label: (await pick('appel')).portions[0].label } }] }] });
  const doc2 = foodRow(A, day).data;
  ok(!r.err && Object.keys(doc2.entries).length === 2 && JSON.stringify(doc2.entries[id1]) === JSON.stringify(e1), 'a second meal is added, the first stays as it was');
  const e2 = Object.values(doc2.entries).find((e) => e !== doc2.entries[id1]);
  ok(e2.src && e2.ref && e2.g > 0 && e2.u === 'g' && e2.at >= e1.at && !('items' in e2), 'one food becomes a normal entry the app can reopen');

  // several meals and another day in one call
  r = await call(T, 'log_meals', { date: '2026-11-01', meals: [{ name: 'Breakfast', items: [{ food: bread.food, grams: 70 }, { food: cheese.food, grams: 20 }] }, { name: 'Lunch', items: [{ food: egg.food, grams: 100 }, { food: bread.food, grams: 70 }] }] });
  const d3 = foodRow(A, '2026-11-01').data, ents = Object.values(d3.entries).sort((a, b) => a.at - b.at);
  ok(!r.err && ents.length === 2 && ents[0].name === 'Breakfast' && ents[1].name === 'Lunch' && ents[0].at < ents[1].at && !foodRow(A, day).data.entries.zzz, 'a whole day in one call, in order, on the date given');

  // refused input
  const bad = async (args, re, m) => { const x = await call(T, 'log_meals', args); ok(x.err && re.test(x.text), m + ': ' + x.text); };
  const before = JSON.stringify(rows.filter((x) => x.path.startsWith('yc/food/')));
  await bad({ meals: [{ items: [{ food: 'nevo:99999999', grams: 10 }] }] }, /Unknown food/, 'unknown food');
  await bad({ meals: [{ items: [{ food: bread.food }] }] }, /grams or a portion/, 'no amount');
  await bad({ meals: [{ items: [{ food: bread.food, portion: { label: 'bucket' } }] }] }, /not a portion of .*Its portions/, 'unknown portion lists the real ones');
  await bad({ meals: [{ items: [{ food: bread.food, grams: 0 }] }] }, /Give grams/, 'zero grams');
  await bad({ meals: [{ items: [{ food: bread.food, grams: 9000 }] }] }, /at most 5000/, 'absurd amount');
  await bad({ meals: [{ items: [] }] }, /at least one food/, 'empty meal');
  await bad({ meals: [] }, /at least one meal/, 'no meals');
  await bad({ date: '1 Nov', meals: [{ items: [{ food: bread.food, grams: 10 }] }] }, /date must be a real day/, 'bad date');
  await bad({ date: '2026-02-30', meals: [{ items: [{ food: bread.food, grams: 10 }] }] }, /date must be a real day/, 'a day that does not exist');
  await bad({ meals: [{ items: [{ food: bread.food, grams: 0.01 }] }] }, /at least 0.1/, 'an amount that rounds to nothing');
  await bad({ meals: Array.from({ length: 9 }, () => ({ items: [{ food: bread.food, grams: 10 }] })) }, /At most 8 meals.*Nothing was saved/, 'too many meals is refused, not cut short');
  await bad({ meals: [{ items: Array.from({ length: 13 }, () => ({ food: bread.food, grams: 10 })) }] }, /At most 12 foods.*Nothing was saved/, 'too many foods in a meal is refused, not cut short');
  ok(JSON.stringify(rows.filter((x) => x.path.startsWith('yc/food/'))) === before, 'a refused meal writes nothing');
  ok(!rows.some((x) => x.user_id === B && x.path.startsWith('yc/food/')), 'nothing written to ben');

  // read
  let g = (await call(T, 'get_food_day')).json;
  ok(g.date === day && g.entries.length === 2 && g.entries[0].id === id1 && g.entries[0].items.length === 4 && g.entries[0].items[0].amount.startsWith('~'), 'get_food_day lists entries in order with items and ~ for estimates');
  ok(!('kcal' in g.totals) && /hidden/.test(g.note) && g.totals.protein_g > 0, 'day totals without calories');
  { const rr = rows.find((x) => x.user_id === A && x.path === 'yc').data; rr.settings = { ...(rr.settings || {}), show_calories: true }; }
  rows.find((x) => x.user_id === A && x.path === 'yc').data.nutrition = { kcal: 2650, protein: 180 };
  g = (await call(T, 'get_food_day')).json;
  ok(g.totals.kcal > 0 && g.entries[0].kcal > 0 && g.targets.kcal === 2650 && g.targets.protein_g === 180 && !g.note, 'calories and targets appear once the person shows them');
  ok((await search('kaas', 1)).results[0].per_100.kcal > 0, 'search shows calories too then');
  ok((await call(T, 'get_food_day', { date: '2026-01-01' })).json.entries.length === 0, 'an empty day is an empty list');
  ok((await call('tok.ben.x', 'get_food_day', { date: day })).json.entries.length === 0, 'ben does not see her food');
  ok((await call(T, 'get_food_day', { date: 'x' })).err, 'bad date');

  // remove
  const sessionsBefore = snapshot();
  for (const odd of ['__proto__', 'constructor', 'hasOwnProperty', 'toString', '']) {
    const before = JSON.stringify(foodRow(A, day).data);
    ok((await call(T, 'remove_food_entry', { date: day, entry_id: odd })).err && JSON.stringify(foodRow(A, day).data) === before, 'an id that is not an entry ("' + odd + '") is refused and changes nothing');
  }
  ok((await call(T, 'remove_food_entry', { date: '2026-13-01', entry_id: id1 })).err, 'remove needs a real day');
  r = await call(T, 'remove_food_entry', { date: day, entry_id: id1 });
  ok(!r.err && r.json.removed.id === id1 && r.json.day.entries.length === 1 && !foodRow(A, day).data.entries[id1], 'an entry is removed and the rest stays');
  ok((await call(T, 'remove_food_entry', { date: day, entry_id: id1 })).err, 'removing it twice fails');
  ok((await call(T, 'remove_food_entry', { date: '2026-01-01', entry_id: 'x' })).err, 'nothing to remove on an empty day');
  ok((await call('tok.ben.x', 'remove_food_entry', { date: day, entry_id: Object.entries(foodRow(A, day).data.entries).find(([, e]) => e)[0] })).err, 'ben can not remove her entry');
  ok(Object.values(foodRow(A, day).data.entries).filter(Boolean).length === 1 && snapshot() === sessionsBefore, 'her other entry and her logged sessions are untouched');

  // the food tables not loading is a tool error that recovers
  let down = true;
  const h3 = createHandler({ url: base, anonKey: 'anon', publicUrl: PUB, siteUrl: base + '/site/' }, async (u, i) => (down && String(u).includes('/site/') ? new Response('', { status: 503 }) : fetch(u, i)));
  const ask = async () => (await (await h3(new Request(PUB, { method: 'POST', headers: { authorization: 'Bearer ' + T }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'search_foods', arguments: { query: 'kaas' } } }) }))).json()).result;
  const out = await ask();
  ok(out.isError && /could not be loaded/.test(out.content[0].text), 'tables down -> tool error');
  down = false;
  ok(!(await ask()).isError, 'and it works again once they load, without a restart');
}

// ---- food: things that went wrong in review, each one checked
{
  const T = 'tok.anna.x';
  const foodRow = (d) => rows.find((x) => x.user_id === A && x.path === 'yc/food/' + d);
  const one = async (q) => (await call(T, 'search_foods', { query: q, limit: 1 })).json.results[0].food;
  const bread = await one('tarwebrood bruin'), egg = await one('ei gekookt');
  const meal = (name, food) => ({ name, items: [{ food, grams: 50 }, { food: bread, grams: 35 }] });

  // two calls at the same moment on an empty day: both meals stay
  let rs = await Promise.all([call(T, 'log_meals', { date: '2026-10-20', meals: [meal('Breakfast', egg)] }), call(T, 'log_meals', { date: '2026-10-20', meals: [meal('Lunch', egg)] })]);
  ok(rs.every((x) => !x.err), rs.map((x) => x.text).join(' | '));
  ok(Object.values(foodRow('2026-10-20').data.entries).map((e) => e.name).sort().join() === 'Breakfast,Lunch', 'parallel meals on a new day are both kept: ' + Object.values(foodRow('2026-10-20').data.entries).map((e) => e.name));
  ok(foodRow('2026-10-20').data.date === '2026-10-20', 'the new day has its date');

  // removing while another meal is logged: the removal and the new meal both land
  const keepId = Object.entries(foodRow('2026-10-20').data.entries).find(([, e]) => e.name === 'Breakfast')[0];
  rs = await Promise.all([call(T, 'remove_food_entry', { date: '2026-10-20', entry_id: keepId }), call(T, 'log_meals', { date: '2026-10-20', meals: [meal('Dinner', egg)] })]);
  const names = Object.values(foodRow('2026-10-20').data.entries).filter(Boolean).map((e) => e.name).sort().join();
  ok(rs.every((x) => !x.err) && names === 'Dinner,Lunch', 'a removal and a new meal at the same moment both land: ' + names);
  ok(foodRow('2026-10-20').data.entries[keepId] === null, 'a removed entry is emptied in place, in one step');
  ok((await call(T, 'get_food_day', { date: '2026-10-20' })).json.entries.length === 2, 'and the day no longer lists it');
  ok((await call(T, 'remove_food_entry', { date: '2026-10-20', entry_id: keepId })).err, 'an emptied entry can not be removed twice');

  // the app adds an entry right after a removal has read the day: the app's entry must survive the removal
  await call(T, 'log_meals', { date: '2026-10-21', meals: [meal('Gone soon', egg)] });
  const goneId = Object.keys(foodRow('2026-10-21').data.entries)[0];
  let inject = true;
  const h4 = createHandler({ url: base, anonKey: 'anon', publicUrl: PUB, siteUrl: base + '/site/' }, async (u, i) => {
    const res = await fetch(u, i);
    if (inject && (!i || !i.method || i.method === 'GET') && decodeURIComponent(String(u)).includes('yc/food/2026-10-21')) { inject = false; foodRow('2026-10-21').data.entries.app1 = { name: 'Added in the app', p: 1, at: 9 }; }
    return res;
  });
  const rm = await (await h4(new Request(PUB, { method: 'POST', headers: { authorization: 'Bearer ' + T }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'remove_food_entry', arguments: { date: '2026-10-21', entry_id: goneId } } }) }))).json();
  const left = foodRow('2026-10-21').data.entries;
  ok(!rm.result.isError && !inject && left.app1 && left.app1.name === 'Added in the app' && left[goneId] === null, 'an entry the app adds while a removal runs is kept: ' + JSON.stringify(left).slice(0, 120));

  // today is the person's own day
  const rootRow = rows.find((x) => x.user_id === A && x.path === 'yc').data;
  const utc = new Date().toISOString().slice(0, 10);
  const far = new Date().getUTCHours() >= 10 ? 'Pacific/Kiritimati' : 'Etc/GMT+12'; // UTC+14 or UTC-12: a different date from UTC right now
  const local = new Intl.DateTimeFormat('en-GB', { timeZone: far, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const localDay = ['year', 'month', 'day'].map((t) => local.find((x) => x.type === t).value).join('-');
  rootRow.settings = { ...(rootRow.settings || {}), tz: far };
  let r = await call(T, 'log_meals', { meals: [meal('Late snack', egg)] });
  ok(!r.err && localDay !== utc && r.json.day.date === localDay && foodRow(localDay) && Object.values(foodRow(localDay).data.entries).some((e) => e && e.name === 'Late snack'), 'without a date the meal lands on the person\'s own today (' + localDay + '), not UTC\'s (' + utc + ')');
  ok((await call(T, 'get_food_day')).json.date === localDay, 'reading the day uses the same today');
  // no saved time zone (a person who connected before opening the app, or a broken value): no guess at their day, the date is asked for
  const before = JSON.stringify(rows.filter((x) => x.path.startsWith('yc/food/')));
  for (const bad of [undefined, 'Not/AZone', '']) {
    if (bad === undefined) delete rootRow.settings.tz; else rootRow.settings.tz = bad;
    r = await call(T, 'get_food_day'); const r2 = await call(T, 'log_meals', { meals: [meal('No day', egg)] });
    ok(r.err && r2.err && /time zone is not saved/.test(r.text) && /YYYY-MM-DD/.test(r2.text), 'time zone "' + bad + '": the date is asked for, not guessed: ' + r.text.slice(0, 60));
  }
  ok(JSON.stringify(rows.filter((x) => x.path.startsWith('yc/food/'))) === before, 'and nothing was written to a guessed day');
  ok(!(await call(T, 'get_food_day', { date: '2026-10-20' })).err && !(await call(T, 'log_meals', { date: '2026-10-22', meals: [meal('With a date', egg)] })).err, 'with the date given it works without a saved time zone');
  rootRow.settings.tz = 'Europe/Amsterdam';

  // several searches in one call
  r = await call(T, 'search_foods', { queries: [{ query: 'tarwebrood bruin' }, { query: 'goudse', type: 'Cheese' }, { query: 'ei gekookt' }, { query: 'zzzqqq' }] });
  const ss = r.json && r.json.searches;
  ok(!r.err && ss.length === 4 && ss[0].results.length <= 6 && ss[0].results.length > 0 && ss[1].results.every((x) => x.type === 'Cheese') && /Goudse/.test(ss[1].results[0].name), 'four foods in one search call, groups per search: ' + r.text.slice(0, 200));
  ok(ss[3].results.length === 0 && /Nothing matched/.test(ss[3].note) && ss[0].query === 'tarwebrood bruin', 'each search says what it was and whether it found anything');
  ok((await call(T, 'search_foods', { queries: Array.from({ length: 9 }, () => ({ query: 'kaas' })) })).err, 'at most 8 searches at once');
  ok((await call(T, 'search_foods', { queries: [{ query: 'kaas' }, { query: ' ' }] })).err, 'an empty search in the list is refused');
  ok((await call(T, 'search_foods', {})).err, 'no query at all is refused');

  // whatever is stored, reading a day does not break
  seed(A, 'yc/food/2026-09-01', { date: '2026-09-01', entries: { a: null, b: 'x', c: { name: 42, p: 5 }, d: { name: 'Odd meal', p: '5', kcal: 'lots', items: [null, 'x', { name: 'Ok', g: 10, p: 1 }] }, e: { name: 'Fine', p: 2, at: 2 } } });
  r = await call(T, 'get_food_day', { date: '2026-09-01' });
  ok(!r.err && r.json.entries.map((e) => e.name).sort().join() === 'Fine,Odd meal' && r.json.totals.protein_g === 2 && r.json.entries.find((e) => e.name === 'Odd meal').items.length === 1, 'malformed entries are skipped and text is never added up as a number: ' + r.text.slice(0, 160));
}

// ---- the person's own foods, portion sizes and saved meals
{
  const T = 'tok.anna.x', TB = 'tok.ben.x';
  rowA('yc').data.settings = { ...(rowA('yc').data.settings || {}), show_calories: false }; // earlier checks switched calories on
  const mineRows = (u = A) => rows.filter((x) => x.user_id === u && x.path.startsWith('yc/myfoods/') && x.data && !x.data.gone);
  const first = async (q, tok = T) => (await call(tok, 'search_foods', { query: q, limit: 1 })).json.results[0];
  const pb = await first('pindakaas'), bread = await first('tarwebrood bruin'), egg = await first('ei gekookt');
  ok(pb && !pb.yours, 'peanut butter has not been logged yet, so it is not "yours": ' + JSON.stringify(pb && pb.name));

  // a food is remembered when it is logged, with the word the person used
  let r = await call(T, 'log_meals', { meals: [{ items: [{ food: pb.food, grams: 15, said: 'Pindakaas ' }] }] });
  ok(!r.err, r.text);
  let doc = mineRows().find((x) => x.data.food === pb.food);
  ok(doc && doc.data.n === 1 && doc.data.aka.pindakaas === 1 && doc.data.name === pb.name && doc.data.last > 0, 'logging remembers the food, how often and the word: ' + JSON.stringify(doc && doc.data));
  r = await call(T, 'log_meals', { meals: [{ items: [{ food: pb.food, grams: 20, said: 'PB' }] }] });
  doc = mineRows().find((x) => x.data.food === pb.food);
  ok(doc.data.n === 2 && doc.data.aka.pb === 1 && doc.data.aka.pindakaas === 1, 'again: counted twice, both words kept: ' + JSON.stringify(doc.data));
  let s1 = (await call(T, 'search_foods', { query: 'pb' })).json.results;
  ok(s1[0].food === pb.food && s1[0].yours === true && s1[0].times_logged === 2 && s1[0].said.includes('pb'), 'a search for her word puts her food first: ' + JSON.stringify(s1[0]));
  s1 = (await call(T, 'search_foods', { query: 'pindakaas', limit: 10 })).json.results;
  ok(s1.filter((x) => x.food === pb.food).length === 1 && s1[0].yours, 'her food is listed once, at the top, not again from the tables');
  ok((await call(TB, 'search_foods', { query: 'pb' })).json.results.every((x) => !x.yours), 'another person does not get her foods');
  s1 = (await call(T, 'search_foods', { query: 'pb', type: 'Cheese' })).json.results;
  ok(s1.every((x) => !x.yours), 'a group filter keeps her foods in their own group');

  // her own portion sizes
  r = await call(T, 'save_my_food', { food: pb.food, said: ['peanut butter'], portions: [{ label: 'Spoon', grams: 12 }] });
  ok(!r.err && r.json.saved.portions.Spoon === 12 && r.json.saved.said.includes('peanut butter') && r.json.saved.said.includes('pb'), 'portion sizes and words are saved, the old words stay: ' + r.text);
  s1 = (await call(T, 'search_foods', { query: 'peanut butter' })).json.results[0];
  ok(s1.food === pb.food && s1.portions[0].label === 'Spoon' && s1.portions[0].grams === 12 && s1.portions[0].yours === true && /own portion sizes first/.test(s1.portions_are), 'her portion sizes come first in the result');
  r = await call(T, 'log_meals', { meals: [{ items: [{ food: pb.food, portion: { label: 'spoon', count: 2 } }] }] });
  const lastE = Object.values(r.json ? rowA('yc/food/' + r.json.day.date).data.entries : {}).filter(Boolean).sort((a, b) => b.at - a.at)[0];
  ok(!r.err && lastE.g === 24 && lastE.est === true, 'her portion times the count gives the grams, case-insensitively: ' + r.text.slice(0, 120));
  r = await call(T, 'log_meals', { meals: [{ items: [{ food: pb.food, portion: { label: 'bucket' } }] }] });
  ok(r.err && /Spoon \(12 g\)/.test(r.text), 'an unknown portion lists her own first: ' + r.text);
  r = await call(T, 'save_my_food', { food: pb.food, portions: [{ label: 'spoon', grams: 10 }] });
  ok(!r.err && Object.keys(rowA('yc/myfoods/' + doc.path.split('/').pop()).data.portions).length === 2, 'a portion with the same name in another case is a new key, not a crash');
  ok((await call(T, 'save_my_food', { food: 'nevo:99999999' })).err, 'unknown food refused');
  ok((await call(T, 'save_my_food', { food: pb.food, portions: [{ label: 'x', grams: 0 }] })).err, 'a portion without grams refused');
  ok((await call(T, 'save_my_food', { food: pb.food, portions: [{ label: 'x', grams: 99999 }] })).err, 'an absurd portion refused');
  for (let i = 0; i < 6; i += 1) await call(T, 'save_my_food', { food: pb.food, portions: [{ label: 'p' + i, grams: 5 + i }] });
  ok((await call(T, 'save_my_food', { food: pb.food, portions: [{ label: 'one too many', grams: 5 }] })).err, 'at most 8 portion sizes per food');
  ok(!(await call(T, 'save_my_food', { food: pb.food, portions: [{ label: 'p0', grams: 7 }] })).err, 'but an existing one can be changed');

  // words: at most 12 per food
  for (let i = 0; i < 14; i += 1) await call(T, 'log_meals', { meals: [{ items: [{ food: egg.food, grams: 50, said: 'ei' + i }] }] });
  const eggDoc = mineRows().find((x) => x.data.food === egg.food);
  ok(Object.keys(eggDoc.data.aka).length === 12 && eggDoc.data.n >= 14, 'a food keeps at most 12 words but still counts every use: ' + Object.keys(eggDoc.data.aka).length);

  // saved meals
  const items = [{ food: bread.food, portion: { label: bread.portions[0].label, count: 2 } }, { food: egg.food, grams: 50, estimated: false }, { food: pb.food, grams: 15 }];
  r = await call(T, 'save_meal', { name: 'My usual breakfast', items });
  ok(!r.err && r.json.saved.id === 'my-usual-breakfast' && r.json.saved.items.length === 3 && r.json.saved.protein_g > 0 && r.json.replaced === false && !('kcal' in r.json.saved), 'a meal is saved with its foods and totals: ' + r.text.slice(0, 160));
  const mealDoc = rowA('yc/meals/my-usual-breakfast').data;
  ok(mealDoc.name === 'My usual breakfast' && mealDoc.items.length === 3 && mealDoc.items[0].g === bread.portions[0].grams * 2 && mealDoc.items[0].est === true && !('est' in mealDoc.items[1]) && mealDoc.n === 0, 'stored like the items of an entry');
  r = await call(T, 'save_meal', { name: ' my USUAL breakfast', items: items.slice(0, 2) });
  ok(!r.err && r.json.replaced === true && r.json.saved.id === 'my-usual-breakfast' && rowA('yc/meals/my-usual-breakfast').data.items.length === 2, 'the same name replaces it');
  r = await call(T, 'save_meal', { name: 'My usual breakfast!', items: items.slice(0, 1) });
  ok(!r.err && r.json.saved.id === 'my-usual-breakfast-2', 'a different name with the same slug gets its own id: ' + r.text.slice(0, 100));
  ok((await call(T, 'save_meal', { name: '', items })).err && (await call(T, 'save_meal', { name: 'x' })).err && (await call(T, 'save_meal', { name: 'x', items: [] })).err, 'a name and foods are needed');
  ok((await call(T, 'save_meal', { name: 'x', items: Array.from({ length: 13 }, () => items[1]) })).err, 'at most 12 foods in a saved meal');

  // from an entry already in the log
  const day = (await call(T, 'log_meals', { meals: [{ name: 'Lunch', items: items.slice(0, 2) }, { items: [{ food: egg.food, grams: 60 }] }] })).json.day;
  const [lunch, single] = day.entries.slice(-2);
  r = await call(T, 'save_meal', { name: 'Usual lunch', from_entry: { date: day.date, entry_id: lunch.id } });
  ok(!r.err && r.json.saved.items.length === 2 && r.json.saved.id === 'usual-lunch', 'a logged meal is saved as it was: ' + r.text.slice(0, 120));
  r = await call(T, 'save_meal', { name: 'Just an egg', from_entry: { date: day.date, entry_id: single.id } });
  ok(!r.err && r.json.saved.items.length === 1 && rowA('yc/meals/just-an-egg').data.items[0].g === 60, 'a single food entry is saved as one food');
  seed(A, 'yc/food/2026-08-01', { date: '2026-08-01', entries: { hand: { name: 'Typed by hand', kcal: 100, p: 3, at: 1 } } });
  ok((await call(T, 'save_meal', { name: 'Hand', from_entry: { date: '2026-08-01', entry_id: 'hand' } })).err, 'an entry typed by hand has no foods to save');
  ok((await call(T, 'save_meal', { name: 'Hand', from_entry: { date: '2026-08-01', entry_id: 'constructor' } })).err, 'only real entries');
  ok((await call(T, 'save_meal', { name: 'Hand', from_entry: { date: '2026-13-01', entry_id: 'x' } })).err, 'a real date');

  // reading them back
  const mine = (await call(T, 'get_my_foods')).json;
  ok(mine.foods[0].times_logged >= mine.foods[mine.foods.length - 1].times_logged && mine.foods.some((f) => f.food === pb.food && f.portions.Spoon === 12), 'foods most used first, with portions');
  ok(mine.meals.map((m) => m.id).sort().join() === 'just-an-egg,my-usual-breakfast,my-usual-breakfast-2,usual-lunch' && !('kcal' in mine.meals[0]) && /hidden/.test(mine.calories), 'meals listed, no calories while hidden');

  // logging a saved meal
  r = await call(T, 'log_meals', { date: '2026-10-25', meals: [{ saved: 'usual-lunch' }, { saved: 'usual-lunch', name: 'Lunch at work' }, { saved: 'just-an-egg' }] });
  const ents = Object.values(rowA('yc/food/2026-10-25').data.entries).sort((a, b) => a.at - b.at);
  ok(!r.err && ents.length === 3 && ents[0].name === 'Usual lunch' && ents[1].name === 'Lunch at work' && ents[0].items.length === 2 && JSON.stringify(ents[0].items) === JSON.stringify(rowA('yc/meals/usual-lunch').data.items) && ents[2].src && ents[2].g === 60, 'a saved meal is logged with its foods; one food becomes a normal entry: ' + r.text.slice(0, 120));
  ok(rowA('yc/meals/usual-lunch').data.n === 2 && rowA('yc/meals/just-an-egg').data.n === 1, 'and counted');
  ok((await call(T, 'log_meals', { meals: [{ saved: 'nope' }] })).err && (await call(TB, 'log_meals', { meals: [{ saved: 'usual-lunch' }] })).err, 'an unknown id, or someone else\'s saved meal, is refused');
  ok((await call(T, 'log_meals', { meals: [{}] })).err, 'a meal needs foods or a saved meal');
  ok((await call(TB, 'get_my_foods')).json.meals.length === 0 && mineRows(B).length === 0 && !rows.some((x) => x.user_id === B && x.path.startsWith('yc/meals/')), 'another person has none of it');

  // removing: forgotten foods and removed meals go away, and a forgotten food can come back
  ok((await call(T, 'remove_saved', {})).err && (await call(T, 'remove_saved', { food: pb.food, meal: 'usual-lunch' })).err, 'exactly one of food or meal');
  ok((await call(T, 'remove_saved', { food: 'nevo:123456' })).err && (await call(T, 'remove_saved', { meal: 'nope' })).err && (await call(T, 'remove_saved', { meal: 'constructor' })).err, 'unknown ones are refused');
  r = await call(T, 'remove_saved', { food: pb.food });
  ok(!r.err && r.json.removed.food === pb.food && (await first('pb')).yours !== true, 'a forgotten food is no longer "yours"');
  ok(!(await call(T, 'get_my_foods')).json.foods.some((f) => f.food === pb.food), 'nor listed');
  await call(T, 'log_meals', { meals: [{ items: [{ food: pb.food, grams: 10, said: 'pb' }] }] });
  const back = (await call(T, 'search_foods', { query: 'pb' })).json.results[0];
  ok(back.yours === true && back.times_logged === 1 && !back.portions.some((x) => x.yours), 'logging it again brings it back, starting from one, without the old portions');
  r = await call(T, 'remove_saved', { meal: 'usual-lunch' });
  ok(!r.err && !(await call(T, 'get_my_foods')).json.meals.some((m) => m.id === 'usual-lunch') && (await call(T, 'log_meals', { meals: [{ saved: 'usual-lunch' }] })).err, 'a removed meal is gone and can not be logged');
  ok(!(await call(T, 'save_meal', { name: 'Usual lunch', items: items.slice(0, 1) })).err && (await call(T, 'get_my_foods')).json.meals.some((m) => m.id === 'usual-lunch'), 'and can be saved again');
  ok((await call(T, 'get_food_day', { date: '2026-10-25' })).json.entries.length === 3, 'entries already logged stay when a saved meal is removed');

  // whatever is stored
  seed(A, 'yc/myfoods/zzz', { food: 5 }); seed(A, 'yc/myfoods/yyy', { food: 'nevo:99999999', name: 'Ghost', n: 9 }); seed(A, 'yc/myfoods/xxx', 'text'); seed(A, 'yc/myfoods/www', { food: egg.food, name: 'Egg', n: 'lots', aka: { a: 'x', b: -1 }, portions: { big: 'huge', ok: 50 } });
  seed(A, 'yc/meals/bad', { name: 'Bad meal', items: [null, 'a', { name: 'x' }] }); seed(A, 'yc/meals/bad2', { name: 5, items: [] }); seed(A, 'yc/meals/bad3', 7);
  r = await call(T, 'get_my_foods');
  ok(!r.err && !r.json.meals.some((m) => /bad/i.test(m.id)) && r.json.foods.every((f) => typeof f.times_logged === 'number' && Object.values(f.portions).every((g) => typeof g === 'number')), 'malformed saved data is skipped, not shown or added up: ' + r.text.slice(0, 120));
  r = await call(T, 'search_foods', { query: 'ghost' });
  ok(!r.err && !r.json.results.some((x) => x.name === 'Ghost'), 'a remembered food that is no longer in the tables is not offered');

  // remembering is best effort: with the list unreadable the meal is still logged
  const flaky = createHandler({ url: base, anonKey: 'anon', publicUrl: PUB, siteUrl: base + '/site/' }, async (u, i) => (decodeURIComponent(String(u)).includes('yc/myfoods') || String((i && i.body) || '').includes('yc/myfoods') ? new Response('{}', { status: 500 }) : fetch(u, i)));
  const askF = async (name, args) => (await (await flaky(new Request(PUB, { method: 'POST', headers: { authorization: 'Bearer ' + T }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args } }) }))).json()).result;
  const before = Object.keys(rowA('yc/food/2026-10-26') ? rowA('yc/food/2026-10-26').data.entries : {}).length;
  const lf = await askF('log_meals', { date: '2026-10-26', meals: [{ name: 'While the list is down', items: [{ food: egg.food, grams: 50, said: 'ei' }] }] });
  ok(!lf.isError && Object.keys(rowA('yc/food/2026-10-26').data.entries).length === before + 1, 'the meal is logged although the remembered foods can neither be read nor written: ' + JSON.stringify(lf).slice(0, 120));
  ok(!(await askF('search_foods', { query: 'kaas' })).isError, 'and search still works');

  // at most 500 remembered foods
  for (let i = 0; i < 500; i += 1) seed(B, 'yc/myfoods/f' + i, { food: 'nevo:' + (1000 + i), name: 'F' + i, n: 1, last: 1 });
  const cheese2 = (await call(TB, 'search_foods', { query: 'kaas goudse 48+', limit: 1 })).json.results[0];
  r = await call(TB, 'log_meals', { date: '2026-10-28', meals: [{ items: [{ food: cheese2.food, grams: 20 }] }] });
  ok(!r.err && mineRows(B).length === 500, 'a full list stays at 500 and the meal is still logged: ' + mineRows(B).length);

  // two meals at once that remember the same new food
  const ham = await first('rookvlees');
  const rs = await Promise.all([call(T, 'log_meals', { date: '2026-10-27', meals: [{ items: [{ food: ham.food, grams: 30, said: 'ham' }] }] }), call(T, 'log_meals', { date: '2026-10-27', meals: [{ items: [{ food: ham.food, grams: 40, said: 'ham' }] }] })]);
  ok(rs.every((x) => !x.err) && mineRows().filter((x) => x.data.food === ham.food).length === 1 && Object.keys(rowA('yc/food/2026-10-27').data.entries).length === 2, 'two calls at once remember the food once and keep both meals');

  // the database rule lets a connected app write these places
  const sql = readFileSync(new URL('../../connector.sql', import.meta.url), 'utf8');
  ok((sql.match(/yc\/myfoods\/%/g) || []).length === 3 && (sql.match(/yc\/meals\/%/g) || []).length === 3 && !/for delete[\s\S]{0,80}yc\/(food|meals|myfoods)/.test(sql), 'connector.sql allows insert and update on both, and still no deletes');
}

// ---- "I ate something": an entry with no details is shown as a placeholder and counts for nothing
{
  const T = 'tok.anna.x';
  const at0 = Date.parse('2026-09-15T12:32:00Z');
  seed(A, 'yc/food/2026-09-15', { date: '2026-09-15', entries: { q1: { name: 'Ate something', quick: true, at: at0, p: null, c: null, f: null }, r1: { name: 'Apple', p: 0.3, c: 14, f: 0.2, kcal: 62, at: at0 + 1 }, q2: { name: 'Ate something', quick: true, at: 'soon' } } });
  let r = await call(T, 'get_food_day', { date: '2026-09-15' });
  const q1 = r.json.entries.find((e) => e.id === 'q1');
  ok(!r.err && r.json.entries.length === 3 && q1.placeholder === true && q1.logged_at === '2026-09-15T12:32:00.000Z', 'a placeholder is listed, flagged and timed: ' + JSON.stringify(q1));
  ok(r.json.entries.find((e) => e.id === 'q2').logged_at === null && !r.json.entries.find((e) => e.id === 'r1').placeholder, 'a bad time is null, a normal entry is not flagged');
  ok(r.json.totals.protein_g === 0.3 && r.json.totals.carbs_g === 14, 'the totals leave placeholders out');
  r = await call(T, 'remove_food_entry', { date: '2026-09-15', entry_id: 'q1' });
  ok(!r.err && r.json.removed.placeholder === true && !(await call(T, 'get_food_day', { date: '2026-09-15' })).json.entries.some((e) => e.id === 'q1'), 'once the person says what it was, the placeholder can be removed');
  const bread = (await call(T, 'search_foods', { query: 'tarwebrood bruin', limit: 1 })).json.results[0].food;
  r = await call(T, 'log_meals', { date: '2026-09-15', meals: [{ name: 'Sandwich', items: [{ food: bread, grams: 70 }] }] });
  ok(!r.err && r.json.day.totals.protein_g > 0.3 && r.json.day.entries.some((e) => e.id === 'q2' && e.placeholder), 'logging a meal on a day with placeholders adds to the totals and leaves them listed');
}

// ---- things found in review, each checked
{
  const T = 'tok.anna.x';
  const settings = rowA('yc').data.settings;
  const first = async (q) => (await call(T, 'search_foods', { query: q, limit: 1 })).json.results[0];
  const egg = (await first('ei gekookt')).food;

  // a rough entry has no calories: they are unknown, not zero, and it says it is rough
  settings.show_calories = true;
  seed(A, 'yc/food/2026-07-01', { date: '2026-07-01', entries: { rough: { name: 'Big lunch', p: 25, c: null, f: null, kcal: null, rough: true, at: 1 }, full: { name: 'Apple', p: 0.3, c: 14, f: 0.2, kcal: 62, at: 2 } } });
  let r = await call(T, 'get_food_day', { date: '2026-07-01' });
  const rough = r.json.entries.find((e) => e.id === 'rough');
  ok(rough.kcal === null && rough.rough === true && rough.protein_g === 25 && r.json.entries.find((e) => e.id === 'full').kcal === 62, 'a missing calorie figure is null, not 0, and a rough entry is flagged: ' + JSON.stringify(rough));
  ok(/1 entry has no calories/.test(r.json.calories_note) && r.json.totals.kcal === 62 && r.json.totals.protein_g === 25.3, 'the day says its calorie total is a minimum: ' + JSON.stringify(r.json.calories_note));
  settings.show_calories = false;
  r = await call(T, 'get_food_day', { date: '2026-07-01' });
  ok(!('kcal' in r.json.entries[0]) && !('calories_note' in r.json) && r.json.entries.find((e) => e.id === 'rough').rough === true, 'with calories hidden there is nothing about calories, the flag stays');

  // search: a synonym ranks below real names and drops out when three real ones exist (the app's rule); it still finds its food alone
  const names = (await call(T, 'search_foods', { query: 'mosterd', limit: 15 })).json.results.map((x) => x.name);
  ok(names.includes('Mosterd') && !names.some((n) => /^Amsoi|^Soep gebonden/.test(n)), 'mustard: real matches only, no vegetable or soup: ' + names);
  const nevo = JSON.parse(readFileSync(new URL('../../foods-nevo.json', import.meta.url), 'utf8')).foods;
  const usda = JSON.parse(readFileSync(new URL('../../foods-usda.json', import.meta.url), 'utf8')).foods;
  const fold = (x) => String(x).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const words = (x) => fold(x).split(/[^a-z0-9]+/).filter(Boolean);
  const seen = new Set(); nevo.forEach((rw) => { words(rw[1]).forEach((w) => seen.add(w)); words(rw[2] || '').forEach((w) => seen.add(w)); }); usda.forEach((rw) => words(rw[1]).forEach((w) => seen.add(w)));
  let synRow = null, synWord = null;
  for (const rw of nevo) { const own = new Set([...words(rw[1]), ...words(rw[2] || '')]); const w = words(rw[3] || '').find((x) => x.length >= 7 && !own.has(x) && ![...seen].some((s) => s.startsWith(x))); if (w) { synRow = rw; synWord = w; break; } }
  ok(synRow && (await call(T, 'search_foods', { query: synWord })).json.results.some((x) => x.name === synRow[1]), 'a word that only a synonym has still finds its food (' + synWord + ')');

  // remembering is skipped, not reset, when the remembered foods can not be read
  const mine = () => rows.filter((x) => x.user_id === A && x.path.startsWith('yc/myfoods/') && x.data && x.data.food === egg)[0];
  for (let i = 0; i < 3; i += 1) await call(T, 'log_meals', { date: '2026-07-02', meals: [{ items: [{ food: egg, grams: 50 }] }] });
  const nBefore = mine().data.n;
  const readsFail = createHandler({ url: base, anonKey: 'anon', publicUrl: PUB, siteUrl: base + '/site/' }, async (u, i) => (decodeURIComponent(String(u)).includes('yc/myfoods') && (!i || !i.method || i.method === 'GET') ? new Response('{}', { status: 500 }) : fetch(u, i)));
  const lg = (await (await readsFail(new Request(PUB, { method: 'POST', headers: { authorization: 'Bearer ' + T }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'log_meals', arguments: { date: '2026-07-02', meals: [{ items: [{ food: egg, grams: 50 }] }] } } }) }))).json()).result;
  ok(!lg.isError && nBefore >= 3 && mine().data.n === nBefore, 'a meal logged while the list is unreadable does not reset how often the food was used: ' + nBefore + ' -> ' + mine().data.n);

  // a saved meal item with no real food is not remembered
  const mineBefore = rows.filter((x) => x.user_id === A && x.path.startsWith('yc/myfoods/')).map((x) => x.path).sort().join();
  seed(A, 'yc/meals/junk', { name: 'Junk meal', items: [{ name: 'Mystery', g: 50, kcal: 10, p: 1 }, { name: 'Ghost', src: 'nevo', ref: '99999999', g: 10, kcal: 1 }] });
  r = await call(T, 'log_meals', { date: '2026-07-03', meals: [{ saved: 'junk' }] });
  ok(!r.err && r.json.saved[0].items.length === 2 && rows.filter((x) => x.user_id === A && x.path.startsWith('yc/myfoods/')).map((x) => x.path).sort().join() === mineBefore, 'a saved meal item the tables do not know is logged but not remembered: ' + r.text.slice(0, 120));

  // a null food is a clear error, not a crash
  for (const [tool, args] of [['log_meals', { date: '2026-07-04', meals: [{ items: [null] }] }], ['save_meal', { name: 'Null', items: [null] }]]) {
    r = await call(T, tool, args);
    ok(r.err && /Each food needs/.test(r.text), tool + ' with a null food says what is wrong: ' + r.text);
  }

  // forgotten and removed items stay behind as { gone: true }: they must not push live ones out of the list
  const sizeBefore = rows.length;
  for (let i = 0; i < 650; i += 1) { if (i < 450) seed(A, 'yc/meals/aaa' + String(i).padStart(4, '0'), { gone: true }); seed(A, 'yc/myfoods/aaa' + String(i).padStart(4, '0'), { gone: true }); } // more than the old read limits (200 meals, 600 foods)
  seed(A, 'yc/meals/zzz-live', { name: 'Last in the list', items: [{ name: 'Bread', src: 'nevo', ref: '1', g: 35, kcal: 80, p: 3 }], n: 1, last: 1 });
  seed(A, 'yc/myfoods/zzz-live', { food: 'nevo:' + egg.split(':')[1], name: 'Live food', n: 1, last: 1 });
  r = await call(T, 'get_my_foods');
  ok(r.json.meals.some((m) => m.id === 'zzz-live') && r.json.foods.some((f) => f.name === 'Live food' || f.food === egg), 'live meals and foods are listed past 450 removed meals and 650 forgotten foods');
  ok((await call(T, 'save_meal', { name: 'Last in the list', items: [{ food: egg, grams: 50 }] })).json.replaced === true, 'and saving under the same name replaces the live meal instead of overwriting it as a new one');
  for (let k = rows.length - 1; k >= sizeBefore; k -= 1) if (/yc\/(meals|myfoods)\/(aaa|zzz-live)/.test(rows[k].path)) rows.splice(k, 1);
  settings.show_calories = false;
}

// ---- database errors surface as tool errors, not crashes
{
  const h2 = createHandler({ url: base, anonKey: 'anon', publicUrl: PUB, siteUrl: base + '/site/' }, async (u, i) => (String(u).includes('/rest/') ? new Response('{}', { status: 500 }) : fetch(u, i)));
  const r = await h2(new Request(PUB, { method: 'POST', headers: { authorization: 'Bearer tok.anna.x' }, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'get_plan', arguments: {} } }) }));
  const j = await r.json();
  ok(r.status === 200 && j.result.isError && /database said no/.test(j.result.content[0].text), 'db failure -> tool error');
}

console.log(n + ' checks passed');
mock.close();
