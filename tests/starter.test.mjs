// The first plans the app makes without an AI (starter.js): every combination of days a week (1 to 7), place, session length and
// experience is built and run through the plan check. None may have an error; every week has a squat or leg press, a hinge, a push
// and a pull; every day fits the session; weighted exercises have a rep range; and the gym and home plans with 3 or more days and
// an hour or more have no frequency, balance or too-much warnings.
import { createRequire } from 'module';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const PC = require('../plancheck.js');
const ST = require('../starter.js');
const src = readFileSync(new URL('../src/yes-coach.html', import.meta.url), 'utf8');
const LIB = JSON.parse(src.match(/const LIB = (\[.*?\]);\n/)[1]);
const lib = new Map(LIB.map((l) => [l.id, l]));
const kit = (name) => new RegExp(src.match(new RegExp(name + ': (/\\^.*?\\$/),'))[1].slice(1, -1));
const PLACE = { home: kit('home'), bodyweight: kit('bodyweight') };
const fits = (l, where) => !PLACE[where] || String(l.equipment).toLowerCase().split(/ or /).some((a) => a.split(/,\s*/).every((p) => PLACE[where].test(p.trim())));
let n = 0;
const ok = (c, m) => { n += 1; if (!c) { console.error('FAIL', m); process.exit(1); } };

// every exercise named in the slots exists
for (const [where, slots] of Object.entries(ST.SLOTS)) for (const [slot, s] of Object.entries(slots)) for (const id of [...(s.new || []), ...(s.any || [])]) ok(lib.has(id), `${where} ${slot}: ${id} exists`);

const LIMIT = { short: 45, medium: 60, long: 90 };
for (const where of ['gym', 'home', 'bodyweight']) for (let d = 1; d <= 7; d += 1) for (const len of ['short', 'medium', 'long']) for (const exp of ['new', 'some', 'years']) {
  const tag = `${where} ${d} days ${len} ${exp}`;
  const env = { lib, fits, describe: PC.describe,
    minutes: (day) => PC.check({ perWeek: 1, days: [day] }, { lookup: (id) => lib.get(id), length: len }).minutes[0],
    check: (pl) => PC.check(pl, { lookup: (id) => lib.get(id), experience: exp, goal: 'muscle', length: len }) };
  const plan = ST.build({ where, days_per_week: d, session_length: len, experience: exp }, env);
  const r = env.check(plan);
  const txt = r.findings.map((f) => f.level + ': ' + f.text).join(' | ');
  ok(plan.perWeek === d && plan.days.length >= 1 && plan.summary, tag + ': a plan with a summary');
  ok(!r.findings.some((f) => f.level === 'error'), tag + ': no errors: ' + txt);
  ok(r.minutes.every((m) => m <= LIMIT[len] + 2), tag + ': every day fits the session: ' + r.minutes);
  for (const day of plan.days) for (const it of day.items) {
    const l = lib.get(it.ex);
    ok(l && fits(l, where) && l.shoulder !== 'skip', `${tag} ${day.name}: ${it.ex} exists, fits ${where}, not hard on shoulders`);
    ok(it.role === 'cardio' || /\bto\b|max|\bs\b/.test(it.reps), `${tag} ${day.name}: ${l.name} has a range: ${it.reps}`);
    ok(it.sets >= 1 && it.sets <= 5 && it.rest_s >= 0, `${tag}: sane sets and rest`);
  }
  for (const day of plan.days) ok(new Set(day.items.map((x) => x.ex)).size === day.items.length, `${tag} ${day.name}: no exercise twice in a day`);
  if (where !== 'bodyweight' && d >= 3 && len !== 'short') {
    const bad = r.findings.filter((f) => f.level === 'warn' && ['freq', 'pull_push', 'consecutive', 'vol_high', 'session_muscle', 'order', 'warmup_unmarked', 'fixed_reps', 'note_numbers'].includes(f.code));
    ok(!bad.length, tag + ': no frequency, balance or too-much warnings: ' + bad.map((f) => f.text).join(' | '));
  }
}
console.log(n + ' starter checks passed');
