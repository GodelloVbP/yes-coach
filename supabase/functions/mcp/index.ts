// Yes Coach! connector: an MCP server (Streamable HTTP, JSON replies) that lets a user's own AI read their
// training data and change their plan. One file, no dependencies. Deploy it as the Supabase Edge Function "mcp"
// with "Verify JWT" switched off (it checks the sign-in itself, see README).
//
// Sign-in: Supabase's OAuth 2.1 server. The AI client sends the user's access token; every database call carries
// that token, so row-level security (schema.sql) keeps each user inside their own rows. No admin key is used.
// Logged sets are never written. The AI can change training days, the weekly schedule, add exercises and answer notes.

declare const Deno: any;

type Env = { url: string; anonKey: string; publicUrl: string };
type Json = any;

const PROTOCOLS = ['2025-06-18', '2025-03-26', '2024-11-05'];
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const KINDS = ['Push', 'Pull', 'Legs', 'Other'];
const UNITS = ['kg', 'bw', 'stack', 'assist', 'min'];
const GROUPS = ['Chest', 'Back', 'Shoulders', 'Arms', 'Legs', 'Core', 'Other'];

const INSTRUCTIONS = [
  'Yes Coach! is a workout tracker. These tools read the signed-in person\'s own plan, log and notes, and change their plan.',
  'Logged sets can not be changed. Plan changes show up in their app at once, and the app keeps an undo for the schedule.',
  'Exercises are referenced by id. Loads are in kg.',
].join(' ');

// ---------------------------------------------------------------- small helpers
const text = (v: Json): string => JSON.stringify(v, null, 1);
const str = (v: Json, max: number, d = ''): string => (v == null ? d : String(v).trim().slice(0, max));
const int = (v: Json, lo: number, hi: number, d: number): number => { const n = Math.round(Number(v)); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : d; };
const slug = (s: string): string => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
const isDate = (v: Json): boolean => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v);
const today = (): string => new Date().toISOString().slice(0, 10);
class ToolError extends Error {}
const fail = (m: string): never => { throw new ToolError(m); };

// ---------------------------------------------------------------- the user's documents (one table, row-level security)
const database = (env: Env, token: string, userId: string, f: typeof fetch) => {
  const headers = (extra: Record<string, string> = {}) => ({ apikey: env.anonKey, authorization: 'Bearer ' + token, 'content-type': 'application/json', ...extra });
  const call = async (path: string, init: RequestInit = {}) => {
    const r = await f(env.url + '/rest/v1/' + path, { ...init, headers: headers(init.headers as Record<string, string>) });
    if (!r.ok) fail('The database said no (' + r.status + '). Try again, or sign in to the connector again.');
    const raw = await r.text();
    return raw ? JSON.parse(raw) : null;
  };
  return {
    // documents whose path starts with prefix, optionally between two path suffixes, newest or oldest first
    list: async (prefix: string, o: { limit?: number; desc?: boolean; gte?: string; lte?: string } = {}): Promise<{ path: string; data: Json }[]> => {
      const q = new URLSearchParams({ select: 'path,data', order: 'path.' + (o.desc ? 'desc' : 'asc') });
      q.append('path', 'like.' + prefix + '*');
      if (o.gte) q.append('path', 'gte.' + prefix + o.gte);
      if (o.lte) q.append('path', 'lte.' + prefix + o.lte);
      if (o.limit) q.set('limit', String(o.limit));
      return call('docs?' + q.toString());
    },
    get: async (path: string): Promise<Json | null> => {
      const rows = await call('docs?' + new URLSearchParams({ select: 'data', path: 'eq.' + path, limit: '1' }).toString());
      return rows.length ? rows[0].data : null;
    },
    put: async (path: string, data: Json): Promise<void> => {
      await call('docs?on_conflict=user_id,path', { method: 'POST', headers: { prefer: 'resolution=merge-duplicates,return=minimal' }, body: JSON.stringify({ user_id: userId, path, data, updated_at: new Date().toISOString() }) });
    },
  };
};
type Db = ReturnType<typeof database>;

const idOf = (path: string): string => path.slice(path.lastIndexOf('/') + 1);
const loadExercises = async (db: Db): Promise<Record<string, Json>> => Object.fromEntries((await db.list('yc/exercises/')).map((r) => [idOf(r.path), r.data]));
const loadDays = async (db: Db): Promise<Record<string, Json>> => Object.fromEntries((await db.list('yc/templates/')).map((r) => [idOf(r.path), r.data]));
const exName = (ex: Record<string, Json>, id: string): string => (ex[id] && ex[id].name) || id;
const byOrder = (days: Record<string, Json>): string[] => Object.keys(days).sort((a, b) => (days[a].order || 0) - (days[b].order || 0));

// the weekly schedule as the app stores it (root.schedule), as plain words
const readSchedule = (root: Json, days: Record<string, Json>): Json => {
  const sc = root && root.schedule;
  if (!sc || !sc.enabled) return { mode: 'none', note: 'No schedule set. Each day falls on its own weekday if it has one.' };
  const name = (id: string) => (days[id] ? days[id].name + ' (' + id + ')' : '(missing day ' + id + ')');
  if (sc.mode === 'rotation') return { mode: 'rotation', note: 'The days repeat in order on these weekdays.', weekdays: sc.days || [], rotation: (sc.rotation || []).map(name) };
  return { mode: 'fixed', week: Object.fromEntries(WEEKDAYS.map((w) => [w, sc.week && sc.week[w] ? name(sc.week[w]) : 'rest'])) };
};
const inWeek = (root: Json): Set<string> => {
  const sc = root && root.schedule;
  if (!sc || !sc.enabled) return new Set();
  return new Set(sc.mode === 'rotation' ? sc.rotation || [] : Object.values(sc.week || {}).filter(Boolean) as string[]);
};
const dayOut = (id: string, d: Json, ex: Record<string, Json>, week: Set<string>): Json => ({
  id, name: d.name, kind: d.kind || 'Other', focus: d.focus || '', in_week: week.has(id),
  exercises: (d.items || []).map((it: Json) => ({ exercise_id: it.ex, exercise: exName(ex, it.ex), sets: it.sets, reps: it.reps, target_kg: it.target || '', rest_s: it.rest_s, note: it.note || null })),
});

// ---------------------------------------------------------------- sessions
const isDone = (st: Json): boolean => !!st && st.done !== false;
const isWork = (st: Json): boolean => !!st && st.kind !== 'warmup' && st.kind !== 'test';
const sessionOut = (path: string, s: Json, ex: Record<string, Json>, days: Record<string, Json>): Json => {
  const by: Record<string, Json[]> = {};
  Object.values(s.sets || {}).filter(isDone).sort((a: Json, b: Json) => (a.order || 0) - (b.order || 0)).forEach((st: Json) => { (by[st.ex] = by[st.ex] || []).push(st); });
  return {
    date: s.date, label: s.label || '', day: s.template && days[s.template] ? days[s.template].name : null, finished: !!s.finished_at, note: s.note || null,
    exercises: Object.entries(by).map(([id, sets]) => ({
      exercise_id: id, exercise: exName(ex, id),
      sets: sets.map((st: Json) => ({ n: st.n, type: st.kind || 'work', reps: st.reps ?? null, load: st.load ?? null, minutes: st.minutes ?? null, rir: st.rir ?? null, note: st.note || null })),
    })),
    _id: idOf(path),
  };
};
// the best working set of one session for one exercise (Epley estimate for loaded lifts)
const bestSet = (sets: Json[], unit: string): Json | null => {
  const work = sets.filter((st) => isDone(st) && isWork(st) && st.reps != null);
  if (!work.length) return null;
  const score = (st: Json) => (unit === 'bw' ? st.reps : unit === 'assist' ? -(st.load || 0) : (st.load || 0) * (1 + st.reps / 30));
  const b = work.reduce((a, c) => (score(c) > score(a) ? c : a));
  return { load: b.load ?? null, reps: b.reps, estimated_1rm: unit === 'kg' || unit === 'stack' ? Math.round((b.load || 0) * (1 + b.reps / 30) * 10) / 10 : null };
};

// ---------------------------------------------------------------- tools
type Tool = { name: string; title: string; description: string; inputSchema: Json; annotations: Json; run: (db: Db, a: Json) => Promise<Json> };
const RO = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
const WR = { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false }; // overwrites plan data
const ADD = { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false }; // only adds
const obj = (properties: Json, required: string[] = []) => ({ type: 'object', properties, required, additionalProperties: false });

const TOOLS: Tool[] = [
  {
    name: 'get_overview', title: 'Get overview', annotations: RO, inputSchema: obj({}),
    description: 'Start here. The person\'s profile (goal, days per week, session length, where they train), their weekly schedule, their training days, the last 5 sessions and how many notes wait for an answer.',
    run: async (db) => {
      const [root, ex, days, recent, notes] = await Promise.all([db.get('yc'), loadExercises(db), loadDays(db), db.list('yc/sessions/', { desc: true, limit: 5 }), db.list('yc/notes/', { desc: true, limit: 100 })]);
      const week = inWeek(root);
      return {
        profile: (root && root.profile) || {}, schedule: readSchedule(root, days),
        training_days: byOrder(days).map((id) => ({ id, name: days[id].name, kind: days[id].kind || 'Other', exercises: (days[id].items || []).length, in_week: week.has(id) })),
        recent_sessions: recent.map((r) => { const s = sessionOut(r.path, r.data, ex, days); return { date: s.date, label: s.label, day: s.day, exercises: s.exercises.length, sets: s.exercises.reduce((n: number, e: Json) => n + e.sets.length, 0) }; }),
        notes_waiting: notes.filter((n) => (n.data.status || 'new') === 'new' && !n.data.reply).length,
        today: today(),
      };
    },
  },
  {
    name: 'get_plan', title: 'Get training plan', annotations: RO, inputSchema: obj({}),
    description: 'The training plan: every training day with its exercises (sets, reps, starting load in kg, rest, note), whether it is in the week, and the weekly schedule.',
    run: async (db) => {
      const [root, ex, days] = await Promise.all([db.get('yc'), loadExercises(db), loadDays(db)]);
      const week = inWeek(root);
      return { schedule: readSchedule(root, days), days: byOrder(days).map((id) => dayOut(id, days[id], ex, week)) };
    },
  },
  {
    name: 'list_exercises', title: 'List exercises', annotations: RO, inputSchema: obj({}),
    description: 'The person\'s exercises: id, name, body part and how the load is counted (kg = weight, stack = machine pin, bw = bodyweight reps, assist = assistance in kg, min = minutes).',
    run: async (db) => { const ex = await loadExercises(db); return Object.entries(ex).map(([id, e]) => ({ id, name: e.name, group: e.group || 'Other', unit: e.unit || 'kg', category: e.category || 'strength' })).sort((a, b) => (a.name < b.name ? -1 : 1)); },
  },
  {
    name: 'get_sessions', title: 'Get logged sessions', annotations: RO,
    inputSchema: obj({ from: { type: 'string', description: 'First date, YYYY-MM-DD. Optional.' }, to: { type: 'string', description: 'Last date, YYYY-MM-DD. Optional.' }, limit: { type: 'integer', description: 'How many sessions, newest first. Default 10, most 60.' } }),
    description: 'Logged sessions, newest first, with every ticked set per exercise (reps, load, set type, reps in reserve, notes).',
    run: async (db, a) => {
      if (a.from != null && !isDate(a.from)) fail('from must be YYYY-MM-DD.');
      if (a.to != null && !isDate(a.to)) fail('to must be YYYY-MM-DD.');
      const [ex, days, rows] = await Promise.all([loadExercises(db), loadDays(db), db.list('yc/sessions/', { desc: true, limit: int(a.limit, 1, 60, 10), gte: a.from, lte: a.to ? a.to + '~z' : undefined })]);
      return rows.map((r) => { const { _id, ...s } = sessionOut(r.path, r.data, ex, days); return s; });
    },
  },
  {
    name: 'get_exercise_history', title: 'Get exercise history', annotations: RO,
    inputSchema: obj({ exercise_id: { type: 'string' }, limit: { type: 'integer', description: 'Sessions to look back through, newest first. Default 20, most 60.' } }, ['exercise_id']),
    description: 'How one exercise went over time: per session the best working set (load, reps, estimated one-rep max for loaded lifts) and the number of working sets.',
    run: async (db, a) => {
      const id = str(a.exercise_id, 80);
      const ex = await loadExercises(db);
      if (!ex[id]) fail('Unknown exercise_id "' + id + '". Call list_exercises.');
      const unit = ex[id].unit || 'kg';
      const rows = await db.list('yc/sessions/', { desc: true, limit: 200 });
      const out: Json[] = [];
      for (const r of rows) {
        const sets = Object.values(r.data.sets || {}).filter((st: Json) => st.ex === id);
        const best = bestSet(sets as Json[], unit);
        if (best) out.push({ date: r.data.date, working_sets: (sets as Json[]).filter((st) => isDone(st) && isWork(st)).length, best });
        if (out.length >= int(a.limit, 1, 60, 20)) break;
      }
      return { exercise: ex[id].name, unit, sessions: out };
    },
  },
  {
    name: 'get_notes', title: 'Get notes', annotations: RO,
    inputSchema: obj({ only_waiting: { type: 'boolean', description: 'Only notes without an answer. Default true.' }, limit: { type: 'integer', description: 'Default 20, most 100.' } }),
    description: 'Notes the person wrote to their coach during sessions (about an exercise or the whole session).',
    run: async (db, a) => {
      const rows = await db.list('yc/notes/', { desc: true, limit: 100 });
      const only = a.only_waiting !== false;
      return rows.filter((r) => !only || (!r.data.reply && (r.data.status || 'new') === 'new')).slice(0, int(a.limit, 1, 100, 20))
        .map((r) => ({ note_id: idOf(r.path), date: r.data.date, about: r.data.about_label || r.data.about, text: r.data.text, status: r.data.status || 'new', reply: r.data.reply || null }));
    },
  },
  {
    name: 'create_exercise', title: 'Create exercise', annotations: ADD,
    inputSchema: obj({ name: { type: 'string' }, group: { type: 'string', enum: GROUPS }, unit: { type: 'string', enum: UNITS, description: 'kg weights, stack machine pin, bw bodyweight reps, assist assistance kg, min minutes.' } }, ['name']),
    description: 'Adds a new exercise to the exercise list. Returns its id (the existing one if the name is already there).',
    run: async (db, a) => {
      const name = str(a.name, 60);
      if (!name || !slug(name)) fail('Give the exercise a name.');
      const ex = await loadExercises(db);
      const found = Object.entries(ex).find(([, e]) => String(e.name).trim().toLowerCase() === name.toLowerCase());
      if (found) return { id: found[0], created: false };
      let id = slug(name);
      for (let n = 2; ex[id]; n += 1) id = slug(name) + '-' + n;
      const unit = UNITS.includes(a.unit) ? a.unit : 'kg';
      await db.put('yc/exercises/' + id, { name, group: GROUPS.includes(a.group) ? a.group : 'Other', category: unit === 'min' ? 'cardio' : 'strength', unit, better: unit === 'assist' ? 'lower' : 'higher', per_side: false, rest_s: unit === 'stack' ? 75 : 90, shoulder: null, library_id: null });
      return { id, created: true };
    },
  },
  {
    name: 'save_training_day', title: 'Save training day', annotations: WR,
    inputSchema: obj({
      id: { type: 'string', description: 'An existing day id to replace. Leave out to create a new day.' }, name: { type: 'string' }, kind: { type: 'string', enum: KINDS }, focus: { type: 'string', description: 'A few words, e.g. "Chest and triceps".' },
      exercises: { type: 'array', maxItems: 12, description: 'The whole list of exercises for the day, in order. It replaces the old list.', items: obj({
        exercise_id: { type: 'string' }, sets: { type: 'integer' }, reps: { type: 'string', description: 'Text, e.g. "8", "8 to 10", "10 per arm", "max", "30 s".' },
        target_kg: { type: 'string', description: 'Load in kg as a plain number in text, e.g. "60", or "". Leave it empty to let the app suggest the next weight from the last sessions; a load set here replaces that suggestion until the next session is logged.' }, rest_s: { type: 'integer' }, note: { type: 'string', description: 'One short coaching cue.' },
      }, ['exercise_id', 'sets', 'reps']) },
    }, ['name', 'exercises']),
    description: 'Create a training day or replace an existing one (name, kind, focus and the whole exercise list). The exercise list given replaces the old one. A new day is not part of the week until the schedule includes it.',
    run: async (db, a) => {
      const [ex, days] = await Promise.all([loadExercises(db), loadDays(db)]);
      const name = str(a.name, 40);
      if (!name) fail('Give the day a name.');
      if (!Array.isArray(a.exercises) || !a.exercises.length) fail('A day needs at least one exercise.');
      const items = a.exercises.slice(0, 12).map((it: Json, k: number) => {
        const exId = str(it && it.exercise_id, 80);
        if (!ex[exId]) fail('Unknown exercise_id "' + exId + '". Call list_exercises or create_exercise.');
        return { ex: exId, order: k + 1, sets: int(it.sets, 1, 8, 3), reps: str(it.reps, 20, '10'), target: str(it.target_kg, 20), target_at: today(), rest_s: int(it.rest_s, 0, 600, 90), note: it.note ? str(it.note, 140) : null };
      });
      let id = str(a.id, 40);
      if (id && !days[id]) fail('Unknown day id "' + id + '". Call get_plan, or leave id out to create a new day.');
      if (!id) { let n = 1; while (days['day-' + n]) n += 1; id = 'day-' + n; }
      const old = days[id] || { order: Object.values(days).reduce((m: number, d: Json) => Math.max(m, d.order || 0), 0) + 1 };
      const doc = { ...old, name, kind: KINDS.includes(a.kind) ? a.kind : old.kind || 'Other', focus: str(a.focus, 80, old.focus || ''), items };
      await db.put('yc/templates/' + id, doc);
      return { saved: true, day: dayOut(id, doc, ex, new Set()), created: !days[id] };
    },
  },
  {
    name: 'set_schedule', title: 'Set weekly schedule', annotations: WR,
    inputSchema: obj({
      mode: { type: 'string', enum: ['rotation', 'fixed'], description: 'rotation: the days repeat in order on the chosen weekdays. fixed: each weekday has its own day.' },
      weekdays: { type: 'array', items: { type: 'string', enum: WEEKDAYS }, description: 'rotation: the weekdays they train.' },
      day_ids: { type: 'array', items: { type: 'string' }, description: 'rotation: day ids in the order they repeat.' },
      week: { type: 'object', description: 'fixed: weekday to day id, e.g. {"Mon":"day-1","Wed":"day-2"}. Leave a weekday out for rest.', additionalProperties: { type: 'string' } },
    }, ['mode']),
    description: 'Set which training days are in the week and when. The old schedule is kept so the person can undo it in the app.',
    run: async (db, a) => {
      const [root, days] = await Promise.all([db.get('yc'), loadDays(db)]);
      const known = (id: string) => { if (!days[id]) fail('Unknown day id "' + id + '". Call get_plan.'); return id; };
      let sc: Json;
      if (a.mode === 'rotation') {
        const wd = [...new Set((Array.isArray(a.weekdays) ? a.weekdays : []).map((w: Json) => String(w).slice(0, 3)).filter((w: string) => WEEKDAYS.includes(w)))].sort((x, y) => WEEKDAYS.indexOf(x as string) - WEEKDAYS.indexOf(y as string));
        const ids = (Array.isArray(a.day_ids) ? a.day_ids : []).map((x: Json) => known(str(x, 40)));
        if (!wd.length || !ids.length) fail('rotation needs weekdays and day_ids.');
        sc = { enabled: true, mode: 'rotation', days: wd, rotation: ids };
      } else if (a.mode === 'fixed') {
        const week: Record<string, string> = {};
        WEEKDAYS.forEach((w) => { week[w] = a.week && a.week[w] ? known(str(a.week[w], 40)) : ''; });
        if (!Object.values(week).some(Boolean)) fail('fixed needs at least one weekday with a day.');
        sc = { enabled: true, mode: 'fixed', week };
      } else fail('mode must be "rotation" or "fixed".');
      const before = root && root.schedule && root.schedule.enabled ? root.schedule : null;
      await db.put('yc', { ...(root || { app: 'yes-coach', schema: 1, created_at: Date.now() }), schedule: sc, ...(before ? { schedule_before: before } : {}) });
      return { saved: true, schedule: readSchedule({ schedule: sc }, days) };
    },
  },
  {
    name: 'answer_note', title: 'Answer note', annotations: WR,
    inputSchema: obj({ note_id: { type: 'string' }, reply: { type: 'string', description: 'A short answer in plain words. The person sees it under their note.' } }, ['note_id', 'reply']),
    description: 'Answer one of the person\'s notes. The reply appears under the note in their app and the note counts as read.',
    run: async (db, a) => {
      const id = str(a.note_id, 80);
      const path = 'yc/notes/' + id;
      const note = id && (await db.get(path));
      if (!note) fail('Unknown note_id. Call get_notes.');
      const reply = str(a.reply, 1500);
      if (!reply) fail('Write a reply.');
      await db.put(path, { ...note, reply, status: 'seen' });
      return { saved: true };
    },
  },
];

// ---------------------------------------------------------------- MCP over HTTP
const CORS = { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'authorization, content-type, mcp-protocol-version, mcp-session-id, accept', 'access-control-allow-methods': 'POST, GET, OPTIONS', 'access-control-expose-headers': 'www-authenticate' };
const reply = (body: Json, status = 200, extra: Record<string, string> = {}) => new Response(body == null ? null : JSON.stringify(body), { status, headers: { ...CORS, ...(body == null ? {} : { 'content-type': 'application/json' }), ...extra } });
const rpcOk = (id: Json, result: Json) => ({ jsonrpc: '2.0', id, result });
const rpcErr = (id: Json, code: number, message: string) => ({ jsonrpc: '2.0', id: id ?? null, error: { code, message } });

export const createHandler = (env: Env, f: typeof fetch = fetch) => {
  const seen = new Map<string, { id: string; until: number }>(); // token -> user, so a busy chat does not ask Supabase every time
  const who = async (token: string): Promise<string | null> => {
    if (token.length > 4096 || token.split('.').length !== 3) return null; // not a JWT: no need to ask Supabase
    const hit = seen.get(token);
    if (hit && hit.until > Date.now()) return hit.id;
    const r = await f(env.url + '/auth/v1/user', { headers: { apikey: env.anonKey, authorization: 'Bearer ' + token } }).catch(() => null);
    if (!r || !r.ok) return null;
    const u = await r.json().catch(() => null);
    if (!u || !u.id) return null;
    seen.set(token, { id: u.id, until: Date.now() + 60000 });
    if (seen.size > 500) seen.clear();
    return u.id;
  };
  const rpc = async (db: Db, m: Json): Promise<Json | null> => {
    const id = m && m.id;
    if (!m || m.jsonrpc !== '2.0' || typeof m.method !== 'string') return rpcErr(id, -32600, 'Invalid request');
    if (id === undefined) return null; // a notification
    if (m.method === 'initialize') {
      const asked = m.params && m.params.protocolVersion;
      return rpcOk(id, { protocolVersion: PROTOCOLS.includes(asked) ? asked : PROTOCOLS[0], capabilities: { tools: { listChanged: false } }, serverInfo: { name: 'yes-coach', title: 'Yes Coach!', version: '0.1.0' }, instructions: INSTRUCTIONS });
    }
    if (m.method === 'ping') return rpcOk(id, {});
    if (m.method === 'tools/list') return rpcOk(id, { tools: TOOLS.map(({ name, title, description, inputSchema, annotations }) => ({ name, title, description, inputSchema, annotations: { title, ...annotations } })) });
    if (m.method === 'tools/call') {
      const tool = TOOLS.find((t) => t.name === (m.params && m.params.name));
      if (!tool) return rpcErr(id, -32602, 'Unknown tool');
      try {
        const out = await tool.run(db, (m.params && m.params.arguments) || {});
        return rpcOk(id, { content: [{ type: 'text', text: text(out) }] });
      } catch (e) {
        return rpcOk(id, { content: [{ type: 'text', text: e instanceof ToolError ? e.message : 'Something went wrong. Try again.' }], isError: true });
      }
    }
    return rpcErr(id, -32601, 'Method not found');
  };
  return async (req: Request): Promise<Response> => {
    const { pathname } = new URL(req.url);
    if (req.method === 'OPTIONS') return reply(null, 204);
    // how an AI client finds out where to sign in (RFC 9728)
    if (pathname.endsWith('/.well-known/oauth-protected-resource')) return reply({ resource: env.publicUrl, authorization_servers: [env.url + '/auth/v1'], bearer_methods_supported: ['header'], resource_name: 'Yes Coach!' });
    if (req.method !== 'POST') return reply(rpcErr(null, -32000, 'Use POST'), 405, { allow: 'POST' });
    const token = (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '');
    const userId = token ? await who(token) : null;
    if (!userId) return reply(rpcErr(null, -32001, 'Sign in required'), 401, { 'www-authenticate': 'Bearer resource_metadata="' + env.publicUrl + '/.well-known/oauth-protected-resource"' });
    if (Number(req.headers.get('content-length') || 0) > 200000) return reply(rpcErr(null, -32600, 'Request too large'), 413);
    let body: Json;
    try { const raw = await req.text(); if (raw.length > 200000) return reply(rpcErr(null, -32600, 'Request too large'), 413); body = JSON.parse(raw); } catch (e) { return reply(rpcErr(null, -32700, 'Parse error'), 400); }
    const db = database(env, token, userId, f);
    if (Array.isArray(body) && body.length > 20) return reply(rpcErr(null, -32600, 'Too many requests in one batch'), 400);
    if (Array.isArray(body)) {
      const out = (await Promise.all(body.map((m) => rpc(db, m)))).filter((x) => x !== null);
      return out.length ? reply(out) : reply(null, 202);
    }
    const out = await rpc(db, body);
    return out ? reply(out) : reply(null, 202);
  };
};

if (typeof Deno !== 'undefined' && Deno.serve) {
  const url = Deno.env.get('SUPABASE_URL') as string;
  Deno.serve(createHandler({ url, anonKey: (Deno.env.get('YC_ANON_KEY') || Deno.env.get('SUPABASE_ANON_KEY')) as string, publicUrl: Deno.env.get('MCP_PUBLIC_URL') || url + '/functions/v1/mcp' }));
}
