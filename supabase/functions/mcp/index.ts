// Yes Coach! connector: an MCP server (Streamable HTTP, JSON replies) that lets a user's own AI read their
// training data and change their plan. One file, no dependencies. Deploy it as the Supabase Edge Function "mcp"
// with "Verify JWT" switched off (it checks the sign-in itself, see README).
//
// Sign-in: Supabase's OAuth 2.1 server. The AI client sends the user's access token; every database call carries
// that token, so row-level security (schema.sql) keeps each user inside their own rows. No admin key is used.
// The AI can change training days, the weekly schedule, add exercises and answer notes, and it can add sets to the log and remove them (never edit one,
// never delete a session document). A removed set is flagged the way the app flags one, so it leaves the history and progress.
// It can also log meals, remove food entries, remember the person's own foods and portion sizes, and keep saved meals. Nutrients are never typed by the AI: they are read from the same NEVO and
// USDA tables the app searches (foods-nevo.json, foods-usda.json, portions-nevo.json, fetched from the app's own site).

declare const Deno: any;

type Env = { url: string; anonKey: string; publicUrl: string; siteUrl: string };
type Json = any;

const PROTOCOLS = ['2025-06-18', '2025-03-26', '2024-11-05'];
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const KINDS = ['Push', 'Pull', 'Legs', 'Other'];
const UNITS = ['kg', 'bw', 'stack', 'assist', 'min'];
const SET_KINDS = ['work', 'warmup', 'drop', 'test'];
const PROGRESS = ['auto', 'up', 'hold', 'down'];
const GROUPS = ['Chest', 'Back', 'Shoulders', 'Arms', 'Legs', 'Core', 'Other'];

const INSTRUCTIONS = [
  'Yes Coach! is a workout tracker. These tools read the signed-in person\'s own plan, log and notes, and change their plan.',
  'Sets can be added to the log and removed from it, but not edited: to fix a set, remove it and add the right one. A removed set leaves the history and Progress. Plan changes show up in their app at once, and the app keeps an undo for the schedule.',
  'Exercises are referenced by id. Loads are in kg.',
  'Weights go up in steps, and every exercise comes with its weight_step and where that step comes from: set (the person chose it), log (the smallest jump between weights they have lifted) or usual (the smallest usual jump for the equipment). The app suggests the last working weight plus one step once every set reached its reps, so 80 kg with a step of 2.3 becomes 82.3 kg.',
  'A plan change can say up, hold or down for an exercise, and the weight is worked out from the log, so the person does not have to be asked which weights their gym has.',
  'Food: search_foods finds foods in the Dutch (NEVO) and international (USDA) tables the app uses; save_custom_food saves a product that is in neither, from the numbers on its label or product page; log_meals saves meals as food ids with grams or a portion; get_food_day and remove_food_entry read and remove entries.',
  'The app reads every nutrient from those tables, so the AI supplies foods and amounts, not nutrient numbers. A search lists the portions a food comes in (a slice, a piece) with grams for one; amounts that are guesses are marked estimated.',
  'A search lists the foods the person logged before at the top, marked yours, with the words they use for them and their own portion sizes; save_my_food and save_meal keep a food, a word, a portion size or a usual meal, and log_meals can log a saved meal.',
  'People who switched calories off in the app get results without calories, with a note saying so.',
].join(' ');

// ---------------------------------------------------------------- small helpers
const text = (v: Json): string => JSON.stringify(v, null, 1);
const str = (v: Json, max: number, d = ''): string => (v == null ? d : String(v).trim().slice(0, max));
const int = (v: Json, lo: number, hi: number, d: number): number => { const n = Math.round(Number(v)); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : d; };
const slug = (s: string): string => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
const isDate = (v: Json): boolean => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v);
const today = (): string => new Date().toISOString().slice(0, 10);
class ToolError extends Error {}
const fail: (m: string) => never = (m) => { throw new ToolError(m); };

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
    // merge a patch into an existing document in one step (the app's yc_update), so a write from the app or a parallel call
    // at the same moment is not lost; returns the document as it is after the merge
    patch: async (path: string, patch: Json): Promise<Json> => call('rpc/yc_update', { method: 'POST', body: JSON.stringify({ p_path: path, p_patch: patch }) }),
    // create a document only if it is not there yet; an existing one is left exactly as it is
    ensure: async (path: string, data: Json): Promise<void> => {
      await call('docs?on_conflict=user_id,path', { method: 'POST', headers: { prefer: 'resolution=ignore-duplicates,return=minimal' }, body: JSON.stringify({ user_id: userId, path, data, updated_at: new Date().toISOString() }) });
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
// adhoc days are the hidden days behind custom workouts: they name a logged session but are not part of the plan
const byOrder = (days: Record<string, Json>): string[] => Object.keys(days).filter((id) => !days[id].adhoc).sort((a, b) => (days[a].order || 0) - (days[b].order || 0));

// the weekly schedule as the app stores it (root.schedule), as plain words
const readSchedule = (root: Json, days: Record<string, Json>): Json => {
  const sc = root && root.schedule;
  if (!sc || !sc.enabled) return { mode: 'none', note: 'No schedule set. Each day falls on its own weekday if it has one.' };
  const name = (id: string) => (days[id] ? days[id].name + ' (' + id + ')' : '(missing day ' + id + ')');
  if (sc.mode === 'rotation') return { mode: 'rotation', note: sc.per_week && sc.per_week < (sc.days || []).length ? 'The weekdays are the days the person can train. They train ' + sc.per_week + ' times a week, spread over those days, and the days repeat in order.' : 'The days repeat in order on these weekdays.', weekdays: sc.days || [], ...(sc.per_week ? { sessions_per_week: sc.per_week } : {}), rotation: (sc.rotation || []).map(name) };
  return { mode: 'fixed', week: Object.fromEntries(WEEKDAYS.map((w) => [w, sc.week && sc.week[w] ? name(sc.week[w]) : 'rest'])) };
};
const inWeek = (root: Json): Set<string> => {
  const sc = root && root.schedule;
  if (!sc || !sc.enabled) return new Set();
  return new Set(sc.mode === 'rotation' ? sc.rotation || [] : Object.values(sc.week || {}).filter(Boolean) as string[]);
};
const dayOut = (id: string, d: Json, ex: Record<string, Json>, week: Set<string>, w: Weights): Json => ({
  id, name: d.name, kind: d.kind || 'Other', focus: d.focus || '', in_week: week.has(id),
  exercises: (d.items || []).map((it: Json) => ({ exercise_id: it.ex, exercise: exName(ex, it.ex), ...stepOut(w, it.ex), last_load: w.last(it.ex), sets: it.sets, reps: it.reps, target_kg: it.target || '', rest_s: it.rest_s, note: it.note || null, superset: it.group || null })),
});

// ---------------------------------------------------------------- sessions
const isDone = (st: Json): boolean => !!st && st.done !== false && !st.removed;
const isWork = (st: Json): boolean => !!st && st.kind !== 'warmup' && st.kind !== 'test';

// ---------------------------------------------------------------- weight steps
// The app's own rule (progression.js: defaultInc, learnInc, resolveInc), copied because an Edge Function cannot import from the page.
// tests/parity.test.mjs keeps the equipment lists below the same as the app's exercise library.
const LIB_DUMBBELL = new Set('l02 l03 l16 l20 l22 l24 l26 l27 l30 l31 l32 l39 l40 l46 l47 l48 l49 l50 l069 l070 l071 l087 l090 l091 l095 l096 l100 l101 l102 l127 l130 l131 l133 l139 l141 l143 l144 l150 l151 l152 l153 l158 l159 l163 l173 l176 l178 l179 l180 l194 l195 l196 l198 l199 l211 l212 l215 l221 l238 l240 l259 l275 l276 l277 l278 l279 l280 l281 l282 l283'.split(' '));
const LIB_CABLE = new Set('l06 l07 l10 l14 l18 l23 l25 l28 l29 l34 l36 l37 l38 l54 l60 l61 l072 l073 l074 l104 l105 l106 l107 l134 l135 l136 l140 l154 l155 l160 l161 l170 l171 l172 l174 l224 l231 l232 l256'.split(' '));
const LIB_BARBELL = new Set('l04 l27 l29 l33 l40 l42 l50 l53 l067 l068 l088 l092 l093 l094 l096 l098 l099 l120 l121 l124 l125 l128 l129 l131 l148 l149 l153 l157 l162 l164 l175 l177 l179 l180 l181 l185 l186 l187 l188 l193 l195 l197 l211 l213 l214 l216 l217 l221 l257 l271 l272 l273 l274 l276 l277'.split(' '));
const STEP_SESSIONS = 60; // how far back the log is read for the step and the last weight
const round2 = (x: number): number => Math.round(x * 100) / 100;
const usualStep = (e: Json, minPlate: number): number => {
  const unit = e.unit || 'kg';
  if (unit === 'stack') return 1;
  if (unit === 'assist') return 5;
  if (unit === 'kg' && e.load_basis === 'per_side') return minPlate;
  const id = e.library_id || '', name = String(e.name || '');
  if (LIB_DUMBBELL.has(id) || (!id && /dumbbell|kettlebell/i.test(name))) return 2;
  if (LIB_CABLE.has(id) || (!id && /cable/i.test(name))) return 2.5;
  if (LIB_BARBELL.has(id) || (!id && /barbell|ez-bar|trap bar|safety squat/i.test(name))) return round2(minPlate * 2);
  return 2.5;
};
// the smallest gap between two neighbouring weights that were each used for two sets or more; a gap over twice the usual jump is a jump over weights
const learnStep = (loads: number[], usual: number): number | null => {
  const count: Record<string, number> = {};
  loads.forEach((x) => { const v = Number(x); if (x != null && isFinite(v) && v >= 0) count[round2(v)] = (count[round2(v)] || 0) + 1; });
  const seen = Object.keys(count).filter((k) => count[k] >= 2).map(Number).sort((a, b) => a - b);
  let best: number | null = null;
  for (let i = 1; i < seen.length; i += 1) { const g = round2(seen[i] - seen[i - 1]); if (g >= 0.25 && (best == null || g < best)) best = g; }
  return best == null || best > 2 * usual ? null : best;
};
type Weights = { step: (id: string) => { inc: number; from: string } | null; last: (id: string) => number | null };
// what the log says about every exercise: its step, and the weight most working sets were done at in its last session
const weightsOf = (root: Json | null, ex: Record<string, Json>, sessions: { path: string; data: Json }[]): Weights => {
  const plates = root && root.settings && Array.isArray(root.settings.plates) ? root.settings.plates.map(Number).filter((x: number) => x > 0) : [];
  const minPlate = plates.length ? Math.min(...plates) : 1.25;
  const loads: Record<string, number[]> = {}, last: Record<string, number> = {};
  sessions.slice().sort((a, b) => (String(a.data.date) < String(b.data.date) ? 1 : -1)).forEach((r) => {
    const by: Record<string, number[]> = {};
    Object.values(r.data.sets || {}).forEach((st: Json) => { if (isDone(st) && (st.kind == null || st.kind === 'work') && st.ex && typeof st.load === 'number') (by[st.ex] = by[st.ex] || []).push(st.load); });
    Object.entries(by).forEach(([id, ls]) => {
      (loads[id] = loads[id] || []).push(...ls);
      if (last[id] !== undefined) return;
      // the load most sets were done at; ties go to the harder one (less help on an assisted machine)
      const assist = ex[id] && ex[id].unit === 'assist';
      const n: Record<string, number> = {};
      ls.forEach((l) => { n[l] = (n[l] || 0) + 1; });
      last[id] = Object.keys(n).map(Number).reduce((a, c) => (n[c] > n[a] || (n[c] === n[a] && (assist ? c < a : c > a)) ? c : a));
    });
  });
  return {
    step: (id) => {
      const e = ex[id];
      const unit = e ? e.unit || 'kg' : '';
      if (!e || (unit !== 'kg' && unit !== 'stack' && unit !== 'assist')) return null;
      if (Number(e.inc) > 0) return { inc: Number(e.inc), from: 'set' };
      const usual = usualStep(e, minPlate);
      const learned = learnStep(loads[id] || [], usual);
      return learned != null ? { inc: learned, from: 'log' } : { inc: usual, from: 'usual' };
    },
    last: (id) => (last[id] === undefined ? null : last[id]),
  };
};
const stepOut = (w: Weights, id: string): Json => { const s = w.step(id); return { weight_step: s ? s.inc : null, weight_step_from: s ? s.from : null }; };
const loadWeights = async (db: Db, root: Json | null, ex: Record<string, Json>): Promise<Weights> => weightsOf(root, ex, await db.list('yc/sessions/', { desc: true, limit: STEP_SESSIONS }));
// a run set also carries distance (km), climb (m) and where it happened; the pace follows from time and distance
const runOut = (st: Json): Json => {
  if (st.km == null && st.elev == null && !st.where) return {};
  const pace = st.km > 0 && st.minutes > 0 ? Math.round((st.minutes / st.km) * 60) : null;
  return { distance_km: st.km ?? null, altitude_gain_m: st.elev ?? null, where: st.where === 'treadmill' ? 'treadmill' : st.where ? 'outdoors' : null, pace_min_per_km: pace == null ? null : Math.floor(pace / 60) + ':' + String(pace % 60).padStart(2, '0'), speed_kmh: st.km > 0 && st.minutes > 0 ? Math.round((st.km / (st.minutes / 60)) * 10) / 10 : null };
};
const sessionOut = (path: string, s: Json, ex: Record<string, Json>, days: Record<string, Json>): Json => {
  const by: Record<string, Json[]> = {};
  Object.entries(s.sets || {}).filter(([, st]) => isDone(st as Json) && !(st as Json).removed).sort((a: Json, b: Json) => (a[1].order || 0) - (b[1].order || 0)).forEach(([key, st]: [string, Json]) => { (by[st.ex] = by[st.ex] || []).push({ ...st, _key: key }); });
  return {
    session_id: idOf(path), date: s.date, label: s.label || '', day: s.template && days[s.template] ? days[s.template].name : null, finished: !!s.finished_at, note: s.note || null,
    exercises: Object.entries(by).map(([id, sets]) => ({
      exercise_id: id, exercise: exName(ex, id),
      sets: sets.map((st: Json) => ({ set_id: st._key, n: st.n, type: st.kind || 'work', reps: st.reps ?? null, load: st.load ?? null, minutes: st.minutes ?? null, ...runOut(st), rir: st.rir ?? null, note: st.note || null })),
    })),
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

// ---------------------------------------------------------------- food: the same tables the app searches
type Food = { src: 'nevo' | 'usda' | 'own'; ref: string; name: string; alt: string; type: string; tf: string; wsyn: string[]; kcal: number; p: number; c: number; f: number; unit: 'g' | 'ml'; w: string[]; w2: string[] };
type FoodDb = { items: Food[]; byKey: Map<string, Food>; portie: Record<string, Json[]> };
const fold = (t: Json): string => String(t).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const wordsOf = (t: Json): string[] => fold(t).split(/[^a-z0-9]+/).filter(Boolean).map((w) => (w.length > 3 && w.endsWith('s') ? w.slice(0, -1) : w));
const foodKey = (src: string, ref: Json): string => src + ':' + ref;
const realDate = (v: Json): boolean => isDate(v) && !Number.isNaN(Date.parse(v + 'T00:00:00Z')) && new Date(v + 'T00:00:00Z').toISOString().slice(0, 10) === v;
// today in the person's own time zone, which the app saves in root.settings.tz when it is opened. Until then it is not known,
// and a guess would put a meal on the wrong day for anyone outside it: the caller asks for the date instead.
const localToday = (root: Json): string | null => {
  const tz = root && root.settings && typeof root.settings.tz === 'string' ? root.settings.tz : '';
  if (!tz) return null;
  try {
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
    const get = (t: string) => (parts.find((x) => x.type === t) || { value: '' }).value;
    const d = get('year') + '-' + get('month') + '-' + get('day');
    return realDate(d) ? d : null;
  } catch (e) { return null; } // not a time zone this runtime knows
};
const NO_TZ = 'The person\'s time zone is not saved yet (it is saved when they open Yes Coach! on their phone). Give the date as YYYY-MM-DD.';
const badDate = (v: Json): boolean => v != null && v !== '' && !realDate(v);
const DATE_ERR = 'date must be a real day, like 2026-11-06.';
const n0 = (v: Json): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
const round1 = (n: number): number => Math.round(n * 10) / 10;
const FOOD_FILES = ['foods-nevo.json', 'foods-usda.json', 'portions-nevo.json'];

const loadFoods = async (env: Env, f: typeof fetch): Promise<FoodDb> => {
  const base = env.siteUrl.replace(/\/?$/, '/');
  const docs: Json[] = await Promise.all(FOOD_FILES.map(async (name) => {
    const r = await f(base + name).catch(() => null);
    if (!r || !r.ok) fail('The food tables could not be loaded. Try again in a minute.');
    return r.json();
  }));
  const items: Food[] = [];
  let portie: Record<string, Json[]> = {};
  for (const d of docs) {
    if (d.src === 'portie') portie = d.p || {};
    else if (d.src === 'nevo') for (const [ref, nl, en, syn, g, kcal, p, c, fat, unit] of d.foods) items.push({ src: 'nevo', ref: String(ref), name: nl, alt: en || '', type: d.groups[g], kcal: kcal || 0, p: p || 0, c: c || 0, f: fat || 0, unit: unit === 'ml' ? 'ml' : 'g', w: wordsOf(nl), wsyn: wordsOf(syn || ''), tf: fold(d.groups[g]), w2: wordsOf(en || '') });
    else if (d.src === 'usda') for (const [ref, name, g, kcal, p, c, fat] of d.foods) items.push({ src: 'usda', ref: String(ref), name, alt: '', type: d.groups[g], kcal: kcal || 0, p: p || 0, c: c || 0, f: fat || 0, unit: 'g', w: wordsOf(name), wsyn: [], tf: fold(d.groups[g]), w2: [] });
  }
  if (!items.length) fail('The food tables could not be loaded. Try again in a minute.');
  return { items, byKey: new Map(items.map((it) => [foodKey(it.src, it.ref), it])), portie };
};

// the search the app uses (every typed word starts a word of the name; short, plain, Dutch foods first), plus a second pass for
// Dutch compound words ("brood" finds "tarwebrood") when the first pass fills fewer than the limit
const PROCESSED = ['breaded', 'fried', 'battered', 'canned', 'frozen', 'sweetened', 'flavored', 'tender', 'nugget', 'patty', 'microwaved', 'fast', 'restaurant', 'sliced', 'deli', 'roll', 'prepackaged', 'powder', 'luncheon', 'dried', 'gedroogd', 'sauce', 'pie', 'taart', 'strudel', 'turnover', 'flap'];
const searchFoods = (db: FoodDb, q: string, limit: number, type = ''): Food[] => {
  const toks = wordsOf(q);
  if (!toks.length) return [];
  const starts = (ws: string[], t: string) => ws.some((w) => w.startsWith(t));
  const inside = (ws: string[], t: string) => ws.some((w) => w.includes(t));
  const tk = fold(type);
  const hits: [number, Food, boolean][] = [];
  for (const it of db.items) {
    if (tk && it.tf !== tk) continue;
    let ws: string[] | null = null;
    let penalty = 0;
    let viaSyn = false;
    if (toks.every((t) => starts(it.w, t))) ws = it.w;
    else if (it.w2.length && toks.every((t) => starts(it.w2, t))) ws = it.w2;
    else if (toks.every((t) => inside(it.w, t))) { ws = it.w; penalty = 15; }
    else if (it.w2.length && toks.every((t) => inside(it.w2, t))) { ws = it.w2; penalty = 15; }
    // a synonym ("mosterdkool" for amsoi) only counts when the name does not match, and ranks below real name matches
    else if (it.wsyn.length && toks.every((t) => starts(it.w, t) || starts(it.wsyn, t))) { ws = it.w.concat(it.wsyn); penalty = 25; viaSyn = true; }
    if (!ws) continue;
    let sc = (ws[0] && ws[0].startsWith(toks[0]) ? 20 : 0) + (ws[0] === toks[0] ? 5 : 0) - Math.min(12, ws.length) + (it.src === 'nevo' ? 3 : 0) - penalty;
    for (const t of toks) if (ws.includes(t)) sc += 3;
    for (const w of PROCESSED) if (ws.includes(w) && !toks.includes(w)) sc -= 3;
    if (it.src === 'usda' && /\b[A-Z]{3,}\b/.test(it.name)) sc -= 4;
    if (ws.includes('whole') && !toks.includes('whole')) sc += 2;
    hits.push([sc, it, viaSyn]);
  }
  // with three or more real name matches the synonym ones are only noise
  const real = hits.filter((h) => !h[2]);
  return (real.length >= 3 ? real : hits).sort((a, b) => b[0] - a[0]).slice(0, limit).map((h) => h[1]);
};

// rough small, medium and large portions by kind of food, in grams (the same table the app falls back on)
const SIZES: Record<string, number[]> = {
  Meals: [200, 350, 500], Restaurant: [200, 350, 500], 'Fast food': [150, 250, 400], Soups: [200, 250, 350],
  Meat: [75, 100, 150], Fish: [75, 125, 175], 'Plant-based': [60, 90, 150], 'Cold cuts': [15, 30, 60],
  Vegetables: [110, 165, 220], Potatoes: [140, 210, 280], Legumes: [180, 240, 300], Fruit: [75, 125, 200],
  Bread: [35, 70, 105], Bakery: [20, 40, 80], Pastry: [20, 40, 80], Cereals: [30, 40, 60],
  Dairy: [100, 150, 250], Cheese: [20, 40, 60], Eggs: [50, 100, 150], 'Nuts and seeds': [15, 25, 50],
  Snacks: [25, 40, 100], Sweets: [15, 30, 60], 'Fats and oils': [5, 10, 20], Spreads: [10, 20, 40], Sauces: [15, 25, 50], Supplements: [15, 30, 60],
};
// which of RIVM's household measures is the everyday one: a normal slice or piece first, spoons and sips last (the app's ranking)
const measureScore = (m: string, type: string, g: number): number => {
  const t = m.toLowerCase();
  if (/afval/.test(t) || (/^stuks/.test(t) && g < 20 && ['Vegetables', 'Potatoes'].includes(type))) return 2;
  if (/^(hoeveelheid|voor 1 toastje|voor 1 beschuit|scheutje|snufje|mespunt)/.test(t)) return 0;
  if (/^slok/.test(t)) return 1;
  if (/^(theelepel|dessert\/paplepel|dessertlepel)/.test(t)) return 2;
  if (/^(eetlepel|sauslepel)/.test(t)) return 3;
  if (/^(opscheplepel|groentelepel|aardappellepel)/.test(t)) return ['Vegetables', 'Potatoes', 'Legumes'].includes(type) ? 7 : 4;
  if (/^voor 1 snee\b/.test(t) && ['Spreads', 'Cheese', 'Cold cuts', 'Sweets', 'Fats and oils'].includes(type)) return 9;
  if (/^voor/.test(t)) return 3;
  if (/^stuks? (gemiddeld|middel|medium|\(m\)|gem)/.test(t) || /^stuks (medium|m) /.test(t)) return 12;
  if (/^stuks$/.test(t) || /^stuks (enkel|kippen)/.test(t)) return 11;
  if (/^glas$/.test(t)) return 10;
  if (/^snee$/.test(t)) return 11;
  if (/^(glas|beker\/mok|kopje|portie|schaaltje|soepbord|plakje)$/.test(t) || /^(glas|portie|plakje) /.test(t)) return 9;
  if (/^(broodje\/bolletje)$/.test(t)) return 10;
  if (/^stuks/.test(t)) return /klein|small|\(s\)|mini|kriel/.test(t) ? 6 : /groot|large|\(l\)|xl/.test(t) ? 5 : 8;
  if (/^snee/.test(t)) return /zonder korst|dun/.test(t) ? 6 : 7;
  return 5;
};
// the amounts a food can be given in, best first: RIVM's household measures (grams per one), else rough sizes by kind of food
const portionsOf = (db: FoodDb, it: Food): { source: string; list: { label: string; grams: number }[] } => {
  const rp = it.src === 'nevo' ? db.portie[it.ref] : null;
  if (rp && rp.length) {
    const ranked = rp.map((m: Json, i: number) => [measureScore(String(m[0]), it.type, Number(m[1])), i, m] as [number, number, Json]).sort((a, b) => b[0] - a[0] || a[1] - b[1]);
    return { source: 'RIVM household measures, grams for one', list: ranked.map(([, , m]) => ({ label: String(m[0]), grams: Number(m[1]) })).filter((x) => x.grams > 0) };
  }
  const s = SIZES[it.type] || [50, 100, 200];
  return { source: 'rough sizes for this kind of food', list: ['small', 'medium', 'large'].map((label, i) => ({ label, grams: s[i] })) };
};
const per = (it: Food, g: number) => { const k = g / 100; return { kcal: Math.round(it.kcal * k), p: round1(it.p * k), c: round1(it.c * k), f: round1(it.f * k) }; };
const caloriesShown = (root: Json): boolean => {
  const v = root && root.settings && root.settings.show_calories;
  if (typeof v === 'boolean') return v;
  return !!(root && root.nutrition && (root.nutrition.kcal || root.nutrition.protein));
};
const foodEntries = (doc: Json): [string, Json][] => Object.entries((doc && doc.entries) || {}).filter(([, e]) => e && typeof e === 'object' && typeof (e as Json).name === 'string' && (e as Json).name).sort((a, b) => ((a[1] as Json).at || 0) - ((b[1] as Json).at || 0)) as [string, Json][];
// an entry the person noted with one tap and no details ("I ate something") holds no numbers and is left out of the totals
const totalsOf = (entries: [string, Json][]) => entries.filter(([, e]) => !e.quick).reduce((t, [, e]) => ({ kcal: t.kcal + n0(e.kcal), p: round1(t.p + n0(e.p)), c: round1(t.c + n0(e.c)), f: round1(t.f + n0(e.f)) }), { kcal: 0, p: 0, c: 0, f: 0 });
const macros = (n: { kcal: number | null; p: number; c: number; f: number }, cal: boolean) => ({ ...(cal ? { kcal: n.kcal } : {}), protein_g: n.p, carbs_g: n.c, fat_g: n.f });
const isoOf = (at: Json): string | null => { const d = new Date(n0(at)); return n0(at) > 0 && Number.isFinite(d.getTime()) ? d.toISOString() : null; };
const kcalOf = (e: Json): number | null => (typeof e.kcal === 'number' && Number.isFinite(e.kcal) ? e.kcal : null); // missing is unknown, not 0
const amountOf = (g: number, u: string | undefined, est: Json): string => (est ? '~' : '') + g + ' ' + (u || 'g');
// one entry of a day by its id; only the day's own entries count, so an id such as "constructor" finds nothing
const entryAt = (doc: Json, id: string): Json => {
  const entries = doc && doc.entries && typeof doc.entries === 'object' ? doc.entries : {};
  const e = id && Object.prototype.hasOwnProperty.call(entries, id) ? entries[id] : null;
  return e && typeof e === 'object' && e.name ? e : fail('No entry with that id on that day. Read the day to see its entries.');
};
const entryOut = (id: string, e: Json, cal: boolean) => ({
  id, name: e.name, ...(e.quick ? { placeholder: true, logged_at: isoOf(e.at) } : {}), ...(e.rough ? { rough: true } : {}), ...macros({ kcal: kcalOf(e), p: n0(e.p), c: n0(e.c), f: n0(e.f) }, cal), ...(n0(e.g) ? { amount: amountOf(e.g, e.u, e.est) } : {}),
  ...(Array.isArray(e.items) ? { items: e.items.filter((i: Json) => i && typeof i === 'object').map((i: Json) => ({ name: String(i.name || ''), amount: amountOf(n0(i.g), i.u, i.est), ...macros({ kcal: kcalOf(i), p: n0(i.p), c: n0(i.c), f: n0(i.f) }, cal) })) } : {}),
});
const foodDayOut = (date: string, doc: Json, root: Json) => {
  const entries = foodEntries(doc);
  const cal = caloriesShown(root);
  const tg = (root && root.nutrition) || {};
  const noKcal = entries.filter(([, e]) => !e.quick && kcalOf(e) === null).length;
  return {
    date, entries: entries.map(([id, e]) => entryOut(id, e, cal)), totals: macros(totalsOf(entries), cal),
    ...(cal && noKcal ? { calories_note: noKcal + (noKcal === 1 ? ' entry has' : ' entries have') + ' no calories (kcal is null), so the calorie total is a minimum.' } : {}),
    targets: { ...(cal && tg.kcal ? { kcal: tg.kcal } : {}), ...(tg.protein ? { protein_g: tg.protein } : {}) },
    ...(cal ? {} : { note: 'Calories are hidden for this person: leave them out of your answer.' }),
  };
};

// ---------------------------------------------------------------- one food in an entry, and the person's own foods and meals
// An item is what an entry and a saved meal keep for one food. The nutrients are worked out once, from the tables.
type Item = { src: string; ref: string; name: string; g: number; u: string; kcal: number; p: number; c: number; f: number; est?: true };
const itemOf = (food: Food, g: number, est: boolean): Item => ({ src: food.src, ref: food.ref, name: food.name, g, u: food.unit, ...per(food, g), ...(est ? { est: true as const } : {}) });
// what is stored could have been written by any connected app: keep only what is a real food with real numbers
const cleanItem = (x: Json): Item | null => {
  if (!x || typeof x !== 'object' || typeof x.name !== 'string' || !x.name || !(n0(x.g) > 0)) return null;
  return { src: x.src === 'usda' ? 'usda' : x.src === 'own' ? 'own' : 'nevo', ref: str(x.ref, 40), name: str(x.name, 120), g: n0(x.g), u: x.u === 'ml' ? 'ml' : 'g', kcal: n0(x.kcal), p: n0(x.p), c: n0(x.c), f: n0(x.f), ...(x.est ? { est: true as const } : {}) };
};
// the foods of a meal added up, rounded the way an entry keeps them
const sumItems = (items: Item[]) => { const t = items.reduce((a, x) => ({ kcal: a.kcal + x.kcal, p: a.p + x.p, c: a.c + x.c, f: a.f + x.f }), { kcal: 0, p: 0, c: 0, f: 0 }); return { kcal: Math.round(t.kcal), p: round1(t.p), c: round1(t.c), f: round1(t.f) }; };
// one food becomes a normal entry the app can reopen; several become one entry with the foods inside
const entryOf = (name: string, items: Item[], at: number): Json => {
  if (items.length === 1) { const x = items[0]; return { name: name || x.name, kcal: x.kcal, p: x.p, c: x.c, f: x.f, at, src: x.src, ref: x.ref, g: x.g, u: x.u, ...(x.est ? { est: true } : {}), via: 'connector' }; }
  return { name: name || items.map((x) => x.name).join(', ').slice(0, 80), ...sumItems(items), at, via: 'connector', items };
};
const itemOut = (i: Item) => ({ name: i.name, amount: amountOf(i.g, i.u, i.est) });

// yc/myfoods/<id>: a food the person logged before { food: "nevo:123", name, aka: { word: 1 }, n, last, portions: { label: grams } }
// own: a food the person made themselves (id "own:<name>"), with its numbers per 100 g or 100 ml
type Own = { kcal: number; p: number; c: number; f: number; u: 'g' | 'ml' };
type Mine = { id: string; food: string; name: string; aka: Record<string, number>; ws: string[]; n: number; last: number; portions: Record<string, number>; own?: Own };
const MINE_MAX = 500, AKA_MAX = 12, PORTIONS_MAX = 8;
// where a custom food's numbers come from: a product page (kept only when it is a real http or https address) or a short note
const sourceOf = (v: Json): string => {
  const s = str(v, 300);
  if (!/^https?:\/\//i.test(s)) return s.slice(0, 120);
  try { const u = new URL(s); return u.protocol === 'http:' || u.protocol === 'https:' ? u.href.slice(0, 300) : ''; } catch { return ''; }
};
const MINE_READ = 2000; // forgotten foods stay as { gone: true } documents: read well past the live cap
const myId = (key: string): string => fold(key).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);
const sayOf = (v: Json): string => fold(str(v, 40)).replace(/\s+/g, ' ').trim();
const numMap = (v: Json, max: number, keyMax: number): Record<string, number> => {
  const out: Record<string, number> = {};
  if (v && typeof v === 'object' && !Array.isArray(v)) for (const [k, x] of Object.entries(v)) { const key = str(k, keyMax); if (key && Object.keys(out).length < max && typeof x === 'number' && Number.isFinite(x) && x > 0 && x <= 100000) out[key] = x; }
  return out;
};
const toMine = (id: string, d: Json): Mine | null => {
  if (!d || typeof d !== 'object' || d.gone || typeof d.food !== 'string' || !d.food) return null;
  const name = str(d.name, 120);
  const aka = numMap(d.aka, AKA_MAX, 40);
  const o = d.own;
  const own: Own | undefined = o && typeof o === 'object' && str(d.food, 40).startsWith('own:') ? { kcal: n0(o.kcal), p: n0(o.p), c: n0(o.c), f: n0(o.f), u: o.u === 'ml' ? 'ml' : 'g' } : undefined;
  return { id, food: str(d.food, 40), name, aka, ws: wordsOf(name + ' ' + Object.keys(aka).join(' ')), n: n0(d.n), last: n0(d.last), portions: numMap(d.portions, PORTIONS_MAX, 30), ...(own ? { own } : {}) };
};
// the person's own foods, shaped like table foods so search, portions and logging treat them the same
const ownFood = (m: Mine): Food => ({ src: 'own', ref: m.food.slice(4), name: m.name, alt: '', type: 'Your own', tf: fold('Your own'), wsyn: [], kcal: m.own!.kcal, p: m.own!.p, c: m.own!.c, f: m.own!.f, unit: m.own!.u, w: wordsOf(m.name), w2: [] });
// the tables plus the person's own foods, for one call (the tables themselves are shared and never changed)
const withOwn = (fdb: FoodDb, mine: Mine[]): FoodDb => {
  const own = mine.filter((m) => m.own).map(ownFood);
  if (!own.length) return fdb;
  const byKey = new Map(fdb.byKey);
  own.forEach((f) => byKey.set(foodKey(f.src, f.ref), f));
  return { ...fdb, byKey };
};
const loadMine = async (db: Db): Promise<Mine[]> => (await db.list('yc/myfoods/', { limit: MINE_READ })).map((r) => toMine(idOf(r.path), r.data)).filter(Boolean) as Mine[];
const mineMatches = (m: Mine, toks: string[]): boolean => toks.every((t) => m.ws.some((w) => w.startsWith(t)));
// the words to add to what a food already has: new ones only, up to the cap
const newWords = (old: Mine | undefined, words: Iterable<string>): Record<string, number> => {
  const out: Record<string, number> = {};
  let n = old ? Object.keys(old.aka).length : 0;
  for (const w of words) if (w && !(old && w in old.aka) && !(w in out) && n < AKA_MAX) { out[w] = 1; n += 1; }
  return out;
};
// merge what changed into a remembered food, creating its document first when it is new (a forgotten food comes back as new)
const upsertMine = (db: Db, id: string, food: string, name: string, patch: Json, old?: Mine): Promise<Json> =>
  (old ? Promise.resolve() : db.ensure('yc/myfoods/' + id, { food, name, aka: {}, n: 0, last: 0, portions: {} }))
    .then(() => db.patch('yc/myfoods/' + id, { food, name, ...patch, ...(old ? {} : { gone: null }) }));
// a food gets remembered when it is logged: how often, the words the person used for it, and (below) their portion sizes
const learn = async (db: Db, mine: Mine[], uses: Map<string, { name: string; said: Set<string>; times: number }>): Promise<void> => {
  const have = new Map(mine.map((m) => [m.food, m]));
  let room = MINE_MAX - mine.length;
  await Promise.all([...uses].map(async ([food, u]) => {
    const old = have.get(food);
    if (!old) { if (room <= 0) return; room -= 1; }
    await upsertMine(db, old ? old.id : myId(food), food, u.name, { aka: newWords(old, u.said), n: (old ? old.n : 0) + u.times, last: Date.now() }, old);
  }));
};

// yc/meals/<id>: a saved meal { name, items: [Item], n, last }; { gone: true } once removed
type Saved = { id: string; name: string; items: Item[]; n: number; last: number };
const SAVED_MAX = 200;
const SAVED_READ = 600; // removed meals stay as { gone: true } documents too
const toSaved = (id: string, d: Json): Saved | null => {
  if (!d || typeof d !== 'object' || d.gone || typeof d.name !== 'string' || !d.name || !Array.isArray(d.items)) return null;
  const items = d.items.slice(0, 12).map(cleanItem).filter(Boolean) as Item[];
  return items.length ? { id, name: str(d.name, 60), items, n: n0(d.n), last: n0(d.last) } : null;
};
const loadMeals = async (db: Db): Promise<Saved[]> => (await db.list('yc/meals/', { limit: SAVED_READ })).map((r) => toSaved(idOf(r.path), r.data)).filter(Boolean) as Saved[];
const savedOut = (m: Saved, cal: boolean) => ({ id: m.id, name: m.name, times_logged: m.n, items: m.items.map(itemOut), ...macros(sumItems(m.items), cal) });

// one food of a meal as the AI gave it (a food id, and grams or a portion), checked against the tables and the person's own portion sizes
const resolveItem = (fdb: FoodDb, mineBy: Map<string, Mine>, it: Json): { item: Item; said: string } => {
  if (!it || typeof it !== 'object') fail('Each food needs a "food" id and grams or a portion.');
  const key = str(it.food, 40);
  const food = fdb.byKey.get(key);
  if (!food) fail('Unknown food "' + key + '". Use the "food" value of a search result, like "nevo:123".');
  const fd = food;
  const own = mineBy.get(key);
  let g: number;
  if (Number(it.grams) > 0) g = Number(it.grams);
  else if (it.portion && it.portion.label) {
    const want = fold(it.portion.label);
    const mineHit = own ? Object.entries(own.portions).find(([l]) => fold(l) === want) : undefined;
    const list = portionsOf(fdb, fd).list;
    const hit = mineHit ? { grams: mineHit[1] } : list.find((x) => fold(x.label) === want);
    if (!hit) fail('"' + it.portion.label + '" is not a portion of ' + fd.name + '. Its portions: ' + [...(own ? Object.entries(own.portions).map(([l, gr]) => ({ label: l, grams: gr })) : []), ...list].slice(0, 8).map((x) => x.label + ' (' + x.grams + ' g)').join(', ') + '. Or give grams.');
    const count = Number(it.portion.count);
    g = hit.grams * (count > 0 ? count : 1);
  } else fail('Give grams or a portion for ' + fd.name + '.');
  g = Math.round(g * 10) / 10;
  if (!(g > 0) || g > 5000) fail('The amount of ' + fd.name + ' has to be at least 0.1 and at most 5000.');
  return { item: itemOf(fd, g, it.estimated !== false), said: sayOf(it.said) };
};

// ---------------------------------------------------------------- tools
type Ctx = { foods: () => Promise<FoodDb> };
type Tool = { name: string; title: string; description: string; inputSchema: Json; annotations: Json; run: (db: Db, a: Json, ctx: Ctx) => Promise<Json> };
const RO = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
const WR = { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false }; // overwrites plan data
const ADD = { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false }; // only adds
const LOG = { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false }; // only adds, and every call adds again
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
    description: 'The training plan: every training day with its exercises (sets, reps, starting load in kg, rest, note, the weight step with where it comes from, and last_load, the weight of the last session\'s working sets), whether it is in the week, and the weekly schedule.',
    run: async (db) => {
      const [root, ex, days] = await Promise.all([db.get('yc'), loadExercises(db), loadDays(db)]);
      const week = inWeek(root);
      const w = await loadWeights(db, root, ex);
      return { schedule: readSchedule(root, days), days: byOrder(days).map((id) => dayOut(id, days[id], ex, week, w)) };
    },
  },
  {
    name: 'list_exercises', title: 'List exercises', annotations: RO, inputSchema: obj({}),
    description: 'The person\'s exercises: id, name, body part, how the load is counted (kg = weight, stack = machine pin, bw = bodyweight reps, assist = assistance in kg, min = minutes), the weight step with where it comes from (set by the person, log: the smallest jump between weights they lifted, or usual for the equipment; empty for bodyweight and minutes) and their own note for the exercise.',
    run: async (db) => {
      const [root, ex] = await Promise.all([db.get('yc'), loadExercises(db)]);
      const w = await loadWeights(db, root, ex);
      return Object.entries(ex).map(([id, e]) => ({ id, name: e.name, group: e.group || 'Other', unit: e.unit || 'kg', category: e.category || 'strength', ...stepOut(w, id), note: e.my_note || null })).sort((a, b) => (a.name < b.name ? -1 : 1));
    },
  },
  {
    name: 'get_sessions', title: 'Get logged sessions', annotations: RO,
    inputSchema: obj({ from: { type: 'string', description: 'First date, YYYY-MM-DD. Optional.' }, to: { type: 'string', description: 'Last date, YYYY-MM-DD. Optional.' }, limit: { type: 'integer', description: 'How many sessions, newest first. Default 10, most 60.' } }),
    description: 'Logged sessions, newest first, with every ticked set per exercise (reps, load, set type, reps in reserve, notes; for runs also distance, altitude gain, treadmill or outdoors, pace and speed).',
    run: async (db, a) => {
      if (a.from != null && !isDate(a.from)) fail('from must be YYYY-MM-DD.');
      if (a.to != null && !isDate(a.to)) fail('to must be YYYY-MM-DD.');
      const [ex, days, rows] = await Promise.all([loadExercises(db), loadDays(db), db.list('yc/sessions/', { desc: true, limit: int(a.limit, 1, 60, 10), gte: a.from, lte: a.to ? a.to + '~z' : undefined })]);
      return rows.map((r) => sessionOut(r.path, r.data, ex, days));
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
    inputSchema: obj({ name: { type: 'string' }, group: { type: 'string', enum: GROUPS }, unit: { type: 'string', enum: UNITS, description: 'kg weights, stack machine pin, bw bodyweight reps, assist assistance kg, min minutes.' }, weight_step: { type: 'number', description: 'The smallest jump in weight at their gym, e.g. 2.3. Leave out for the usual jump.' } }, ['name']),
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
      await db.put('yc/exercises/' + id, { name, group: GROUPS.includes(a.group) ? a.group : 'Other', category: unit === 'min' ? 'cardio' : 'strength', unit, better: unit === 'assist' ? 'lower' : 'higher', per_side: false, rest_s: unit === 'stack' ? 75 : 90, shoulder: null, library_id: null, ...(Number(a.weight_step) > 0 && Number(a.weight_step) <= 100 ? { inc: Math.round(Number(a.weight_step) * 100) / 100 } : {}) });
      return { id, created: true };
    },
  },
  {
    name: 'save_training_day', title: 'Save training day', annotations: WR,
    inputSchema: obj({
      id: { type: 'string', description: 'An existing day id to replace. Leave out to create a new day.' }, name: { type: 'string' }, kind: { type: 'string', enum: KINDS }, focus: { type: 'string', description: 'A few words, e.g. "Chest and triceps".' },
      exercises: { type: 'array', maxItems: 12, description: 'The whole list of exercises for the day, in order. It replaces the old list.', items: obj({
        exercise_id: { type: 'string' }, sets: { type: 'integer' }, reps: { type: 'string', description: 'Text, e.g. "8", "8 to 10", "10 per arm", "max", "30 s".' },
        progress: { type: 'string', enum: PROGRESS, description: 'How the weight moves from the last working weight, worked out here from the log: auto (the app picks the next weight from the last sessions, the same as an empty target_kg), up (one weight step heavier), hold (the same weight) or down (one step lighter). With up, hold or down no target_kg is needed and the result says which weight was saved.' },
        target_kg: { type: 'string', description: 'Load in kg as a plain number in text, e.g. "60", or "". Empty lets the app suggest the next weight from the last sessions. A number is moved to the nearest weight the person can load (their last working weight plus or minus whole steps) when the step is known from their setting or their log; the result says what was saved. A load set here replaces the app\'s suggestion until the next session is logged.' }, rest_s: { type: 'integer' }, note: { type: 'string', description: 'One short coaching cue.' },
        superset: { type: 'string', description: 'A short label such as "A". Exercises next to each other with the same label are done as a superset: one set of each in turn, rest after the round. Leave it out for a normal exercise.' },
      }, ['exercise_id', 'sets', 'reps']) },
    }, ['name', 'exercises']),
    description: 'Create a training day or replace an existing one (name, kind, focus and the whole exercise list). The exercise list given replaces the old one. A new day is not part of the week until the schedule includes it.',
    run: async (db, a) => {
      const [root, ex, days] = await Promise.all([db.get('yc'), loadExercises(db), loadDays(db)]);
      const name = str(a.name, 40);
      if (!name) fail('Give the day a name.');
      if (!Array.isArray(a.exercises) || !a.exercises.length) fail('A day needs at least one exercise.');
      const w = await loadWeights(db, root, ex);
      const weights: Json[] = []; // what was done with each weight that was asked for, so the AI can tell the person
      const items = a.exercises.slice(0, 12).map((it: Json, k: number) => {
        const exId = str(it && it.exercise_id, 80);
        if (!ex[exId]) fail('Unknown exercise_id "' + exId + '". Call list_exercises or create_exercise.');
        let target = str(it.target_kg, 20);
        const move = PROGRESS.includes(it.progress) ? it.progress : '';
        const step = w.step(exId), last = w.last(exId);
        const assist = ex[exId].unit === 'assist'; // heavier there means less help
        if (move === 'auto') target = '';
        else if (move && (!step || last == null)) {
          weights.push({ exercise_id: exId, progress: move, target_kg: target, note: 'No working weight in the last ' + STEP_SESSIONS + ' sessions to move from, so ' + (target ? 'target_kg was kept.' : 'the app suggests the weight.') });
        } else if (move && step) {
          const to = move === 'hold' ? last! : (move === 'up') !== assist ? last! + step.inc : Math.max(0, last! - step.inc);
          target = String(round2(to));
          weights.push({ exercise_id: exId, progress: move, last_load: last, weight_step: step.inc, weight_step_from: step.from, target_kg: target });
        } else if (target && /^\d+([.,]\d+)?$/.test(target.trim()) && step && step.from !== 'usual' && last != null) {
          const asked = Number(target.trim().replace(',', '.'));
          const to = round2(Math.max(0, last + Math.round((asked - last) / step.inc) * step.inc));
          if (to !== asked) { weights.push({ exercise_id: exId, asked_kg: asked, target_kg: String(to), last_load: last, weight_step: step.inc, weight_step_from: step.from, note: 'Moved to the nearest weight the person can load.' }); target = String(to); }
        }
        return { ex: exId, order: k + 1, sets: int(it.sets, 1, 8, 3), reps: str(it.reps, 20, '10'), target, target_at: today(), rest_s: int(it.rest_s, 0, 600, 90), note: it.note ? str(it.note, 140) : null, group: it.superset ? str(it.superset, 8) : '' } as Json;
      });
      // a superset is two or more exercises next to each other; a lone label is dropped, and a label reused further down becomes its own group
      const used = new Set<string>();
      for (let i = 0; i < items.length;) {
        const g = items[i].group;
        let j = i + 1;
        while (g && j < items.length && items[j].group === g) j += 1;
        if (g && j - i >= 2) {
          let n = g;
          for (let c = 2; used.has(n); c += 1) n = g.slice(0, 6) + c;
          used.add(n);
          for (let k = i; k < j; k += 1) items[k].group = n;
        } else for (let k = i; k < j; k += 1) delete items[k].group;
        i = j;
      }
      let id = str(a.id, 40);
      if (id && !days[id]) fail('Unknown day id "' + id + '". Call get_plan, or leave id out to create a new day.');
      if (!id) { let n = 1; while (days['day-' + n]) n += 1; id = 'day-' + n; }
      const old = days[id] || { order: Object.values(days).reduce((m: number, d: Json) => (d.adhoc ? m : Math.max(m, d.order || 0)), 0) + 1 };
      const doc = { ...old, name, kind: KINDS.includes(a.kind) ? a.kind : old.kind || 'Other', focus: str(a.focus, 80, old.focus || ''), items };
      await db.put('yc/templates/' + id, doc);
      return { saved: true, day: dayOut(id, doc, ex, new Set(), w), created: !days[id], ...(weights.length ? { weights } : {}) };
    },
  },
  {
    name: 'set_schedule', title: 'Set weekly schedule', annotations: WR,
    inputSchema: obj({
      mode: { type: 'string', enum: ['rotation', 'fixed'], description: 'rotation: the days repeat in order on the chosen weekdays. fixed: each weekday has its own day.' },
      weekdays: { type: 'array', items: { type: 'string', enum: WEEKDAYS }, description: 'rotation: the weekdays they can train.' },
      day_ids: { type: 'array', items: { type: 'string' }, description: 'rotation: day ids in the order they repeat.' },
      sessions_per_week: { type: 'integer', description: 'rotation: how many sessions a week, 1 to 7. With fewer than the weekdays given, the sessions are spread over those weekdays. Leave out to train on every weekday given.' },
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
        const per = int(a.sessions_per_week, 1, 7, 0);
        sc = { enabled: true, mode: 'rotation', days: wd, rotation: ids, ...(per ? { per_week: per } : {}) };
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
  {
    name: 'add_sets', title: 'Add sets to the log', annotations: LOG,
    inputSchema: obj({
      date: { type: 'string', description: 'YYYY-MM-DD, today or earlier.' },
      exercise_id: { type: 'string' },
      sets: { type: 'array', maxItems: 20, description: 'The sets, in the order they were done. Each is a done set, as if the person had ticked it.', items: obj({
        reps: { type: 'integer', description: 'Needed unless the exercise is counted in minutes.' }, load: { type: 'number', description: 'kg, machine pin, or assistance kg, as the exercise is counted. Leave out for bodyweight.' },
        minutes: { type: 'number', description: 'Needed when the exercise is counted in minutes.' }, type: { type: 'string', enum: SET_KINDS, description: 'work (default), warmup, drop or test (not counted in Progress).' },
        rir: { type: 'integer', description: 'Reps in reserve, 0 to 10.' }, note: { type: 'string' },
        distance_km: { type: 'number' }, altitude_gain_m: { type: 'number' }, where: { type: 'string', enum: ['outdoor', 'treadmill'] },
      }) },
      session_id: { type: 'string', description: 'Only when the person did two sessions on one date: the session_id of the one to add to, e.g. 2026-10-08~day-1. Leave out to use the date\'s own session.' },
      day_id: { type: 'string', description: 'Only when no session exists on that date yet: the training day it belongs to. Leave out for a session without a plan day.' },
    }, ['date', 'exercise_id', 'sets']),
    description: 'Add done sets of one exercise to the log, to a session that is there or to a new one for that date. Each set gets a set_id. A set cannot be edited afterwards: to correct one, remove it and add the right one.',
    run: async (db, a) => {
      if (!realDate(a.date)) fail(DATE_ERR);
      if (a.date > new Date(Date.now() + 864e5).toISOString().slice(0, 10)) fail('Sets can only be added for today or earlier.');
      const [ex, days] = await Promise.all([loadExercises(db), loadDays(db)]);
      const exId = str(a.exercise_id, 80);
      const e = ex[exId];
      if (!e) fail('Unknown exercise_id "' + exId + '". Call list_exercises or create_exercise.');
      if (!Array.isArray(a.sets) || !a.sets.length) fail('Give at least one set.');
      if (a.sets.length > 20) fail('At most 20 sets in one call.');
      const unit = e.unit || 'kg';
      const sid = a.session_id ? str(a.session_id, 80) : a.date;
      if (sid.slice(0, 10) !== a.date || (sid.length > 10 && sid[10] !== '~')) fail('session_id has to start with the date, like ' + a.date + ' or ' + a.date + '~day-1.');
      const dayId = a.day_id ? str(a.day_id, 40) : '';
      if (dayId && !days[dayId]) fail('Unknown day id "' + dayId + '". Call get_plan.');
      const path = 'yc/sessions/' + sid;
      const num = (v: Json, what: string, lo: number, hi: number, whole = false): number | null => {
        if (v == null || v === '') return null;
        const n = Number(v);
        if (!Number.isFinite(n) || n < lo || n > hi || (whole && !Number.isInteger(n))) fail(what + ' has to be ' + (whole ? 'a whole number' : 'a number') + ' from ' + lo + ' to ' + hi + '.');
        return Math.round(n * 100) / 100;
      };
      const made = a.sets.map((raw: Json, i: number) => {
        const st = raw || {};
        const at = 'Set ' + (i + 1) + ': ';
        const reps = num(st.reps, at + 'reps', 1, 1000, true);
        const minutes = num(st.minutes, at + 'minutes', 0.1, 1000);
        if (unit === 'min' ? minutes == null : reps == null) fail(at + (unit === 'min' ? 'minutes are needed, because this exercise is counted in minutes.' : 'reps are needed.'));
        const out: Json = { kind: SET_KINDS.includes(st.type) ? st.type : 'work', reps, load: num(st.load, at + 'load', 0, 1000), minutes, rir: num(st.rir, at + 'rir', 0, 10, true), note: st.note ? str(st.note, 140) : null };
        const km = num(st.distance_km, at + 'distance_km', 0, 1000);
        const elev = num(st.altitude_gain_m, at + 'altitude_gain_m', 0, 20000);
        if (km != null) out.km = km;
        if (elev != null) out.elev = elev;
        if (st.where === 'outdoor' || st.where === 'treadmill') out.where = st.where;
        return out;
      });
      // a new session starts like one the app starts; a past date is complete, today may still be going
      if (!(await db.get(path))) {
        const t = dayId ? days[dayId] : null;
        const now = Date.now();
        await db.ensure(path, { date: a.date, source: 'connector', template: dayId || null, split: t ? ({ Pull: 'Back', Push: 'Chest', Legs: 'Legs' } as Json)[t.kind] || t.name : 'Other', label: t ? t.name : 'workout', note: null, started_at: now, updated_at: now, ...(a.date < today() ? { finished_at: now } : {}), sets: {} });
      }
      const doc = (await db.get(path)) || {};
      const sets: Json = doc.sets || {};
      // the next free row for this exercise counts removed rows too, so a new set never lands on an old key
      let n = Object.entries(sets).reduce((m, [k, st]: [string, Json]) => (st && st.ex === exId ? Math.max(m, Number(k.slice(exId.length + 1)) || 0, st.n || 0) : m), 0);
      let order = Object.values(sets).reduce((m: number, st: Json) => (st && st.ex === exId ? Math.max(m, st.order || 0) : m), 0) || Math.max(9999, ...Object.values(sets).map((st: Json) => (st && st.order) || 0)) + 100;
      const now = Date.now();
      const patch: Json = {};
      const added = made.map((m: Json) => {
        n += 1; order += 1;
        const key = exId + '_' + n;
        patch[key] = { ex: exId, n, order, ...m, done: true, at: now, ticked_at: now, unit: unit === 'kg' ? 'kg:' + (e.load_basis === 'per_side' ? 'per_side' : 'total') : unit, via: 'connector' };
        return key;
      });
      const after = await db.patch(path, { updated_at: now, sets: patch });
      const out = sessionOut(path, after, ex, days);
      return { added: added.length, set_ids: added, session: { ...out, exercises: out.exercises.filter((x: Json) => x.exercise_id === exId) } };
    },
  },
  {
    name: 'remove_sets', title: 'Remove sets from the log', annotations: WR,
    inputSchema: obj({
      session_id: { type: 'string', description: 'The session, as listed with the logged sessions: a date like 2026-10-08, or 2026-10-08~day-1 when there were two on one date.' },
      set_ids: { type: 'array', maxItems: 50, items: { type: 'string' }, description: 'The set_id of each set to remove.' },
      exercise_id: { type: 'string', description: 'Instead of set_ids: remove every set of this exercise from the session.' },
    }, ['session_id']),
    description: 'Remove logged sets from one session, either the sets named by set_ids or all sets of one exercise. A removed set leaves the history and Progress at once. The result lists what was removed, with its numbers, so it can be added back.',
    run: async (db, a) => {
      const sid = str(a.session_id, 80);
      if (!realDate(sid.slice(0, 10)) || (sid.length > 10 && sid[10] !== '~')) fail('session_id looks like 2026-10-08, or 2026-10-08~day-1 when there were two sessions on one date.');
      const ids: string[] = Array.isArray(a.set_ids) ? a.set_ids.map((x: Json) => str(x, 90)).filter(Boolean) : [];
      const exId = str(a.exercise_id, 80);
      if (!ids.length && !exId) fail('Give set_ids, or an exercise_id to remove all its sets from the session.');
      if (ids.length && exId) fail('Give set_ids or exercise_id, not both.');
      const path = 'yc/sessions/' + sid;
      const [doc, ex, days] = await Promise.all([db.get(path), loadExercises(db), loadDays(db)]);
      if (!doc) fail('No session ' + sid + '. Call get_sessions for the session_id.');
      const live = (k: string): Json | null => { const st = (doc.sets || {})[k]; return st && st.ex && !st.removed ? st : null; };
      let keys: string[];
      if (ids.length) {
        const unknown = ids.filter((k) => !live(k));
        if (unknown.length) fail('No such set in this session: ' + unknown.join(', ') + '. Nothing was removed.');
        keys = [...new Set(ids)];
      } else {
        keys = Object.keys(doc.sets || {}).filter((k) => live(k) && live(k)!.ex === exId);
        if (!keys.length) fail('No sets of ' + (ex[exId] ? ex[exId].name : exId) + ' in this session.');
      }
      const now = Date.now();
      // the app's own way of taking a set away: unticked and flagged, in one merge step so a set added meanwhile stays
      await db.patch(path, { updated_at: now, sets: Object.fromEntries(keys.map((k) => [k, { done: false, removed: true, at: now }])) });
      const removed = keys.map((k) => { const st = (doc.sets || {})[k]; return { set_id: k, exercise_id: st.ex, exercise: exName(ex, st.ex), type: st.kind || 'work', reps: st.reps ?? null, load: st.load ?? null, minutes: st.minutes ?? null, ...runOut(st), rir: st.rir ?? null, note: st.note || null, was_done: isDone(st) }; });
      return { removed: removed.length, sets: removed, date: doc.date, session_id: sid };
    },
  },
  {
    name: 'search_foods', title: 'Search foods', annotations: RO,
    inputSchema: obj({
      query: { type: 'string', description: 'One or two plain words, Dutch or English, e.g. "gouda", "brown bread", "ei gekookt". Dutch compound words work: "brood" also finds "tarwebrood".' },
      type: { type: 'string', description: 'Optional food group to stay inside, as shown in results: Bread, Cheese, Eggs, Dairy, Meat, Fish, Vegetables, Fruit, Potatoes, Grains, Legumes, Spreads, Sauces, Spices, Fats and oils, Nuts and seeds, Sweets, Snacks, Drinks, Meals and more.' },
      queries: { type: 'array', maxItems: 8, description: 'Several foods in one go, instead of query: one search each, e.g. [{"query":"tarwebrood bruin"},{"query":"goudse","type":"Cheese"}].', items: obj({ query: { type: 'string' }, type: { type: 'string' } }, ['query']) },
      limit: { type: 'integer', description: 'Results per search, 1 to 15. Default 10 for one search, 6 each for several.' },
    }),
    description: 'Search the NEVO (Dutch) and USDA food tables the app uses. Each result has a "food" id, its nutrients per 100 g, and the portions it can be given in (RIVM household measures such as a slice or a piece, with grams for one). Foods the person logged before come first, marked yours, with the words they use for them and their own portion sizes. Plain, common foods rank next. An empty result means nothing matched; one plain word in Dutch or English usually finds it.',
    run: async (db, a, ctx) => {
      const many = Array.isArray(a.queries) && a.queries.length > 0;
      if (many && a.queries.length > 8) fail('At most 8 searches at once.');
      const asked = (many ? a.queries : [{ query: a.query, type: a.type }]).map((x: Json) => ({ query: str(x && x.query, 80), type: str(x && x.type, 40) }));
      if (asked.some((x: Json) => !x.query)) fail('Give a word to search for.');
      const [tables, root, mine] = await Promise.all([ctx.foods(), db.get('yc'), loadMine(db).catch(() => [] as Mine[])]);
      const fdb = withOwn(tables, mine);
      const cal = caloriesShown(root);
      const limit = int(a.limit, 1, 15, many ? 6 : 10);
      const out = (it: Food, m?: Mine) => {
        const pt = portionsOf(fdb, it);
        const own = m ? Object.entries(m.portions).map(([label, grams]) => ({ label, grams, yours: true })) : [];
        return { food: foodKey(it.src, it.ref), name: it.name, ...(it.alt ? { english: it.alt } : {}), type: it.type, unit: it.unit, per_100: macros(per(it, 100), cal), portions: [...own, ...pt.list].slice(0, 6), portions_are: own.length ? 'the person\'s own portion sizes first, then ' + pt.source : pt.source, ...(m ? { yours: true, times_logged: m.n, said: Object.keys(m.aka) } : {}) };
      };
      const one = (x: { query: string; type: string }) => {
        const toks = wordsOf(x.query);
        const yours = mine.filter((m) => mineMatches(m, toks)).map((m) => [m, fdb.byKey.get(m.food)] as [Mine, Food | undefined])
          .filter((p): p is [Mine, Food] => !!p[1] && (!x.type || fold(p[1].type) === fold(x.type)))
          .sort((p, q) => q[0].n - p[0].n || q[0].last - p[0].last).slice(0, Math.min(5, limit));
        const taken = new Set(yours.map(([m]) => m.food));
        const hits = searchFoods(tables, x.query, limit + taken.size, x.type).filter((it) => !taken.has(foodKey(it.src, it.ref))).slice(0, limit - yours.length);
        if (!yours.length && !hits.length) return { results: [], note: 'Nothing matched' + (x.type ? ' in that group' : '') + '. One plain word in Dutch or English usually works.' };
        return { results: [...yours.map(([m, it]) => out(it, m)), ...hits.map((it) => out(it))] };
      };
      const hidden = cal ? {} : { calories: 'Calories are hidden for this person: leave them out of your answer.' };
      if (many) return { searches: asked.map((x: Json) => ({ query: x.query, ...(x.type ? { type: x.type } : {}), ...one(x) })), ...hidden };
      return { ...one(asked[0]), ...hidden };
    },
  },
  {
    name: 'get_food_day', title: 'Get food day', annotations: RO,
    inputSchema: obj({ date: { type: 'string', description: 'YYYY-MM-DD. Leave out for today in the person\'s own time zone.' } }),
    description: 'What the person ate on one day: every entry with its id, name, nutrients and items, the day totals, and their daily targets. An entry marked placeholder is a meal the person noted with one tap and no details; it has the time it was noted and counts for nothing in the totals.',
    run: async (db, a) => {
      if (badDate(a.date)) fail(DATE_ERR);
      const [root, early] = await Promise.all([db.get('yc'), a.date ? db.get('yc/food/' + a.date) : Promise.resolve(null)]);
      const date = a.date || localToday(root) || fail(NO_TZ);
      return foodDayOut(date, a.date ? early : await db.get('yc/food/' + date), root);
    },
  },
  {
    name: 'log_meals', title: 'Log meals', annotations: LOG,
    inputSchema: obj({
      date: { type: 'string', description: 'YYYY-MM-DD, the day it was eaten. Leave out for today in the person\'s own time zone.' },
      meals: { type: 'array', minItems: 1, maxItems: 8, description: 'One entry per meal, in the order eaten. A whole day can go in one call.', items: obj({
        name: { type: 'string', description: 'The person\'s own words, short, e.g. "2 slices bread with egg, cheese and mustard". Optional for a single food.' },
        saved: { type: 'string', description: 'The id of one of the person\'s saved meals: logs it as it was saved. Use it instead of items.' },
        items: { type: 'array', minItems: 1, maxItems: 12, items: obj({
          food: { type: 'string', description: 'The "food" value of a search result, e.g. "nevo:123".' },
          grams: { type: 'number', description: 'Amount in grams (millilitres for drinks). Use it when the person said a weight.' },
          portion: obj({ label: { type: 'string', description: 'A label from that food\'s "portions" in a search result, including the person\'s own.' }, count: { type: 'number', description: 'How many of that portion. Default 1.' } }, ['label']),
          estimated: { type: 'boolean', description: 'false only when the person said the exact weight. Default true: a guess or a typical portion.' },
          said: { type: 'string', description: 'The word the person used for this food, e.g. "kaas". It is remembered, so the next search for that word finds this food first.' },
        }, ['food']) },
      }) },
    }, ['meals']),
    description: 'Save one or more meals to the person\'s food log. Each food is a "food" id from a search plus grams or a portion; the app reads the nutrients from its tables, so there are no nutrient fields. A meal with several foods becomes one entry with its items inside; a meal with one food is a normal entry. A saved meal can be logged by its id. Foods are remembered for next time. Returns what was saved and the day totals.',
    run: async (db, a, ctx) => {
      if (badDate(a.date)) fail(DATE_ERR);
      if (!Array.isArray(a.meals) || !a.meals.length) fail('Give at least one meal.');
      if (a.meals.length > 8) fail('At most 8 meals in one go. Nothing was saved; send the rest in a second call.');
      const wantsSaved = a.meals.some((m: Json) => m && m.saved);
      // the remembered foods only improve things: when they can not be read, the meal is still logged
      let mineRead = true;
      const [tables, root, mine, savedAll, early] = await Promise.all([ctx.foods(), db.get('yc'), loadMine(db).catch(() => { mineRead = false; return [] as Mine[]; }), wantsSaved ? loadMeals(db) : Promise.resolve([] as Saved[]), a.date ? db.get('yc/food/' + a.date) : Promise.resolve(null)]);
      const fdb = withOwn(tables, mine);
      const date = a.date || localToday(root) || fail(NO_TZ);
      const mineBy = new Map(mine.map((m) => [m.food, m]));
      const uses = new Map<string, { name: string; said: Set<string>; times: number }>();
      const usedSaved = new Map<string, { sm: Saved; times: number }>();
      const note = (i: Item, said: string) => { const k = foodKey(i.src, i.ref); if (!fdb.byKey.has(k)) return; // only foods the tables know are remembered
         const u = uses.get(k) || { name: i.name, said: new Set<string>(), times: 0 }; u.times += 1; if (said) u.said.add(said); uses.set(k, u); };
      const meals = a.meals.map((m: Json) => {
        if (m && m.saved) {
          const sm = savedAll.find((x) => x.id === str(m.saved, 60));
          if (!sm) fail('Unknown saved meal "' + str(m.saved, 60) + '". Read the person\'s saved meals to see their ids.');
          sm.items.forEach((i) => note(i, ''));
          usedSaved.set(sm.id, { sm: sm, times: (usedSaved.get(sm.id)?.times || 0) + 1 });
          return { name: str(m.name, 80) || sm.name, items: sm.items };
        }
        const raw = Array.isArray(m && m.items) ? m.items : [];
        if (raw.length > 12) fail('At most 12 foods in one meal. Nothing was saved; split it into two meals.');
        const items = raw.map((it: Json) => { const r = resolveItem(fdb, mineBy, it); note(r.item, r.said); return r.item; });
        if (!items.length) fail('Each meal needs at least one food or a saved meal.');
        return { name: str(m && m.name, 80), items };
      });
      const path = 'yc/food/' + date;
      const old = a.date ? early : await db.get(path);
      if (foodEntries(old).length + meals.length > 100) fail('That day already has a lot of entries. Read the day first.');
      const add: Record<string, Json> = {};
      let at = Date.now();
      meals.forEach((m: { name: string; items: Item[] }) => {
        add['e' + at.toString(36) + Math.random().toString(36).slice(2, 5)] = entryOf(m.name, m.items, at);
        at += 1;
      });
      // the day is created only if it is missing, then the meals are merged in: two calls at once both keep their meals
      if (!old) await db.ensure(path, { date, entries: {} });
      const after = await db.patch(path, { entries: add });
      // remembering foods is best effort: the meal is already saved, so a hiccup here does not fail the call
      try {
        await Promise.all([mineRead ? learn(db, mine, uses) : Promise.resolve(), ...[...usedSaved.values()].map((u) => db.patch('yc/meals/' + u.sm.id, { n: u.sm.n + u.times, last: Date.now() }))]);
      } catch (e) { /* ignored */ }
      const day = foodDayOut(date, after, root);
      const cal = caloriesShown(root);
      return { saved: Object.entries(add).map(([id, e]) => entryOut(id, e, cal)), day };
    },
  },
  {
    name: 'get_my_foods', title: 'Get my foods', annotations: RO, inputSchema: obj({}),
    description: 'The foods this person logged before, most used first, with the words they use for them and their own portion sizes, and the meals they saved with their foods and totals.',
    run: async (db) => {
      const [mine, meals, root] = await Promise.all([loadMine(db), loadMeals(db), db.get('yc')]);
      const cal = caloriesShown(root);
      return {
        foods: mine.sort((x, y) => y.n - x.n || y.last - x.last).slice(0, 40).map((m) => ({ food: m.food, name: m.name, said: Object.keys(m.aka), times_logged: m.n, portions: m.portions })),
        meals: meals.sort((x, y) => y.n - x.n || y.last - x.last).map((m) => savedOut(m, cal)),
        ...(cal ? {} : { calories: 'Calories are hidden for this person: leave them out of your answer.' }),
      };
    },
  },
  {
    name: 'save_my_food', title: 'Save my food', annotations: ADD,
    inputSchema: obj({
      food: { type: 'string', description: 'The "food" value of a search result, e.g. "nevo:723".' },
      said: { type: 'array', maxItems: 6, items: { type: 'string' }, description: 'Words the person uses for it, e.g. ["kaas","cheese"]. A search for these finds it first.' },
      portions: { type: 'array', maxItems: 6, description: 'The person\'s own portion sizes: a name and the grams of one, e.g. [{"label":"slice","grams":40}].', items: obj({ label: { type: 'string' }, grams: { type: 'number' } }, ['label', 'grams']) },
    }, ['food']),
    description: 'Remember which food the person means by a word, and their own portion sizes for it. A portion saved here is used when a meal is logged with that portion name. Saving again adds to what is there; a portion with the same name is replaced.',
    run: async (db, a, ctx) => {
      const fdb = await ctx.foods();
      const key = str(a.food, 40);
      const id = myId(key);
      const old = toMine(id, await db.get('yc/myfoods/' + id)) || undefined;
      const food = key.startsWith('own:') ? (old && old.own && old.food === key ? ownFood(old) : undefined) : fdb.byKey.get(key);
      if (!food) fail('Unknown food "' + key + '". Use the "food" value of a search result, like "nevo:123".');
      if (!old && (await loadMine(db)).length >= MINE_MAX) fail('The list of remembered foods is full.');
      const aka = newWords(old, (Array.isArray(a.said) ? a.said.slice(0, 6) : []).map(sayOf));
      const portions: Record<string, number> = {};
      const have = old ? Object.keys(old.portions).length : 0;
      for (const x of Array.isArray(a.portions) ? a.portions.slice(0, 6) : []) {
        const label = str(x && x.label, 30);
        const grams = round1(Number(x && x.grams));
        if (!label || !(grams > 0) || grams > 5000) fail('A portion needs a name and grams between 0.1 and 5000.');
        if (!(old && label in old.portions) && !(label in portions) && have + Object.keys(portions).length >= PORTIONS_MAX) fail('A food can have at most ' + PORTIONS_MAX + ' portion sizes.');
        portions[label] = grams;
      }
      const after = await upsertMine(db, id, key, food.name, { aka, portions }, old);
      return { saved: { food: key, name: food.name, said: Object.keys(numMap(after && after.aka, AKA_MAX, 40)), portions: numMap(after && after.portions, PORTIONS_MAX, 30) } };
    },
  },
  {
    name: 'save_custom_food', title: 'Save custom food', annotations: ADD,
    inputSchema: obj({
      name: { type: 'string', description: 'What the person calls it, e.g. "Mama\'s lasagne" or "Protein shake (Jumbo)".' },
      unit: { type: 'string', enum: ['g', 'ml'], description: 'g for foods, ml for drinks. All numbers below are per 100 of this unit. Default g.' },
      kcal_per_100: { type: 'number', description: 'Calories per 100 g or 100 ml, 0 to 900.' },
      protein_per_100: { type: 'number', description: 'Protein in grams per 100 g or 100 ml, 0 to 100.' },
      carbs_per_100: { type: 'number', description: 'Carbohydrates in grams per 100 g or 100 ml, 0 to 100.' },
      fat_per_100: { type: 'number', description: 'Fat in grams per 100 g or 100 ml, 0 to 100.' },
      source: { type: 'string', description: 'Where the numbers come from: the web address of the product page, or a short note such as "package label". Shown next to the food in the app.' },
      said: { type: 'array', maxItems: 6, items: { type: 'string' }, description: 'Other words the person uses for it. A search for these finds it first.' },
      portions: { type: 'array', maxItems: 6, description: 'The person\'s own portion sizes: a name and the grams (or ml) of one, e.g. [{"label":"scoop","grams":30}].', items: obj({ label: { type: 'string' }, grams: { type: 'number' } }, ['label', 'grams']) },
    }, ['name', 'kcal_per_100', 'protein_per_100', 'carbs_per_100', 'fat_per_100']),
    description: 'Save a food that is not in the NEVO or USDA tables, such as something home-made or a branded product, with its numbers per 100 g or 100 ml: calories, protein, carbs and fat, and whether it is a food or a drink. The numbers are the ones printed on the package or shown on the maker\'s or a shop\'s product page, given by the person or read from that page when the person asks for a product to be looked up on the internet. This does not search the internet and does not estimate; the numbers are saved as given, with where they come from. Saving the same name again replaces the numbers. The food then comes first in food searches, marked yours, with a "food" id like "own:lasagne", and is logged by grams or portion like any other food.',
    run: async (db, a) => {
      const name = str(a.name, 60);
      const slug = myId(name);
      if (!name || !slug) fail('Give the food a name with letters or numbers.');
      const u = a.unit === 'ml' ? 'ml' : 'g';
      const num = (v: Json, label: string, max: number): number => {
        const x = Number(v);
        if (v == null || v === '' || !Number.isFinite(x) || x < 0 || x > max) fail(label + ' per 100 ' + u + ' has to be a number from 0 to ' + max + '. Use the number on the label or product page, per 100 ' + u + '; a guess is not saved.');
        return round1(x);
      };
      const own: Own = { kcal: Math.round(num(a.kcal_per_100, 'Calories', 900)), p: num(a.protein_per_100, 'Protein', 100), c: num(a.carbs_per_100, 'Carbs', 100), f: num(a.fat_per_100, 'Fat', 100), u };
      if (own.p + own.c + own.f > 105) fail('Protein, carbs and fat together can not be more than 100 g in 100 ' + u + '. Check the numbers with the person.');
      const food = 'own:' + slug;
      const id = myId(food);
      const old = toMine(id, await db.get('yc/myfoods/' + id)) || undefined;
      if (!old && (await loadMine(db)).length >= MINE_MAX) fail('The list of the person\'s foods is full.');
      const aka = newWords(old, (Array.isArray(a.said) ? a.said.slice(0, 6) : []).map(sayOf));
      const portions: Record<string, number> = {};
      const have = old ? Object.keys(old.portions).length : 0;
      for (const x of Array.isArray(a.portions) ? a.portions.slice(0, 6) : []) {
        const label = str(x && x.label, 30);
        const grams = round1(Number(x && x.grams));
        if (!label || !(grams > 0) || grams > 5000) fail('A portion needs a name and an amount between 0.1 and 5000.');
        if (!(old && label in old.portions) && !(label in portions) && have + Object.keys(portions).length >= PORTIONS_MAX) fail('A food can have at most ' + PORTIONS_MAX + ' portion sizes.');
        portions[label] = grams;
      }
      const source = sourceOf(a.source);
      await upsertMine(db, id, food, name, { aka, portions, own, source: source || null }, old); // new numbers carry their own source: an old one is dropped
      // calories that do not fit the macros usually mean a per-serving number slipped in; saved all the same, with a note to check it
      const expect = Math.round(4 * own.p + 4 * own.c + 9 * own.f);
      const off = Math.abs(own.kcal - expect) > Math.max(60, 0.3 * Math.max(own.kcal, expect));
      return {
        saved: { food, name, unit: u, per_100: { kcal: own.kcal, protein_g: own.p, carbs_g: own.c, fat_g: own.f }, portions, ...(source ? { source } : {}) },
        replaced: !!(old && old.own),
        ...(off ? { check: 'Protein, carbs and fat add up to about ' + expect + ' kcal per 100 ' + u + ', but ' + own.kcal + ' was saved. Alcohol and fibre explain some difference; a per-serving number does not. Compare with the label before relying on it.' } : {}),
      };
    },
  },
  {
    name: 'save_meal', title: 'Save meal', annotations: WR,
    inputSchema: obj({
      name: { type: 'string', description: 'What the person calls it, e.g. "my usual breakfast". A saved meal with the same name is replaced.' },
      items: { type: 'array', minItems: 1, maxItems: 12, description: 'The foods, as for logging a meal.', items: obj({
        food: { type: 'string' }, grams: { type: 'number' }, portion: obj({ label: { type: 'string' }, count: { type: 'number' } }, ['label']), estimated: { type: 'boolean' },
      }, ['food']) },
      from_entry: obj({ date: { type: 'string', description: 'YYYY-MM-DD' }, entry_id: { type: 'string', description: 'The id of an entry in the food log.' } }, ['date', 'entry_id']),
    }, ['name']),
    description: 'Save a meal the person eats often, so it can be logged again with one tap in the app or by its id. Give the foods, or point at an entry already in the food log. The nutrients are worked out from the tables when it is saved.',
    run: async (db, a, ctx) => {
      const name = str(a.name, 60);
      if (!name) fail('Give the meal a name.');
      let items: Item[];
      let all: Saved[];
      let root: Json;
      if (a.from_entry) {
        if (!realDate(a.from_entry.date)) fail(DATE_ERR);
        let doc: Json;
        [doc, all, root] = await Promise.all([db.get('yc/food/' + a.from_entry.date), loadMeals(db), db.get('yc')]);
        const e = entryAt(doc, str(a.from_entry.entry_id, 60));
        items = (Array.isArray(e.items) ? e.items : e.src && e.g ? [{ src: e.src, ref: e.ref, name: e.name, g: e.g, u: e.u, kcal: e.kcal, p: e.p, c: e.c, f: e.f, est: e.est }] : []).slice(0, 12).map(cleanItem).filter(Boolean) as Item[];
        if (!items.length) fail('That entry has no foods to save: it was typed in by hand.');
      } else {
        const raw = Array.isArray(a.items) ? a.items : [];
        if (!raw.length) fail('Give the foods, or an entry to save.');
        if (raw.length > 12) fail('At most 12 foods in a saved meal.');
        const [fdb, mine, saved, rootDoc] = await Promise.all([ctx.foods(), loadMine(db), loadMeals(db), db.get('yc')]);
        all = saved;
        root = rootDoc;
        const mineBy = new Map(mine.map((m) => [m.food, m]));
        items = raw.map((it: Json) => resolveItem(withOwn(fdb, mine), mineBy, it).item);
      }
      const same = all.find((m) => fold(m.name) === fold(name));
      if (!same && all.length >= SAVED_MAX) fail('There are already ' + SAVED_MAX + ' saved meals.');
      const base = slug(name) || 'meal';
      let id = same ? same.id : base;
      if (!same) for (let n = 2; all.some((m) => m.id === id); n += 1) id = base + '-' + n;
      await db.put('yc/meals/' + id, { name, items, ...sumItems(items), n: same ? same.n : 0, last: Date.now() });
      return { saved: savedOut({ id, name, items, n: same ? same.n : 0, last: Date.now() }, caloriesShown(root)), replaced: !!same };
    },
  },
  {
    name: 'remove_saved', title: 'Remove saved food or meal', annotations: WR,
    inputSchema: obj({
      food: { type: 'string', description: 'The "food" value of a remembered food, to forget it.' },
      meal: { type: 'string', description: 'The id of a saved meal, to remove it.' },
    }),
    description: 'Forget one remembered food (its words and portion sizes) or remove one saved meal, for when the person asks. Entries already in the food log stay as they are.',
    run: async (db, a) => {
      if (!!a.food === !!a.meal) fail('Give either a food or a meal, not both.');
      if (a.food) {
        const key = str(a.food, 40);
        const hit = toMine(myId(key), await db.get('yc/myfoods/' + myId(key)));
        if (!hit || hit.food !== key) fail('That food is not remembered.');
        await db.put('yc/myfoods/' + hit.id, { gone: true });
        return { removed: { food: hit.food, name: hit.name } };
      }
      const id = str(a.meal, 60);
      const hit = toSaved(id, await db.get('yc/meals/' + id));
      if (!hit) fail('No saved meal with that id.');
      await db.put('yc/meals/' + hit.id, { gone: true });
      return { removed: { meal: hit.id, name: hit.name } };
    },
  },
  {
    name: 'remove_food_entry', title: 'Remove food entry', annotations: WR,
    inputSchema: obj({ date: { type: 'string', description: 'YYYY-MM-DD of the entry.' }, entry_id: { type: 'string', description: 'The id of a food entry, as listed for that day.' } }, ['date', 'entry_id']),
    description: 'Remove one entry from the food log, for when the person asks or an entry was logged by mistake. The entry is gone from their day; it can be logged again.',
    run: async (db, a) => {
      if (!realDate(a.date)) fail(DATE_ERR);
      const path = 'yc/food/' + a.date;
      const id = str(a.entry_id, 60);
      const [doc, root] = await Promise.all([db.get(path), db.get('yc')]);
      const gone = entryAt(doc, id);
      // one merge step that empties this entry (the app skips empty entries), so an entry added meanwhile stays
      const after = await db.patch(path, { entries: { [id]: null } });
      return { removed: entryOut(id, gone, caloriesShown(root)), day: foodDayOut(a.date, after, root) };
    },
  },
];

// ---------------------------------------------------------------- MCP over HTTP
const CORS = { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'authorization, content-type, mcp-protocol-version, mcp-session-id, accept', 'access-control-allow-methods': 'POST, GET, OPTIONS', 'access-control-expose-headers': 'www-authenticate' };
const reply = (body: Json, status = 200, extra: Record<string, string> = {}) => new Response(body == null ? null : JSON.stringify(body), { status, headers: { ...CORS, ...(body == null ? {} : { 'content-type': 'application/json' }), ...extra } });
const rpcOk = (id: Json, result: Json) => ({ jsonrpc: '2.0', id, result });
const rpcErr = (id: Json, code: number, message: string) => ({ jsonrpc: '2.0', id: id ?? null, error: { code, message } });

export const createHandler = (env: Env, f: typeof fetch = fetch) => {
  let foodsLoad: Promise<FoodDb> | null = null; // the food tables, fetched once per running copy of the function
  const ctx: Ctx = { foods: () => { if (!foodsLoad) foodsLoad = loadFoods(env, f).catch((e) => { foodsLoad = null; throw e; }); return foodsLoad; } };
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
        const out = await tool.run(db, (m.params && m.params.arguments) || {}, ctx);
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
  Deno.serve(createHandler({ url, anonKey: (Deno.env.get('YC_ANON_KEY') || Deno.env.get('SUPABASE_ANON_KEY')) as string, publicUrl: Deno.env.get('MCP_PUBLIC_URL') || url + '/functions/v1/mcp', siteUrl: Deno.env.get('YC_SITE_URL') || 'https://godellovbp.github.io/yes-coach/' }));
}
