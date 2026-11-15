// The plan check (plancheck.js): every library exercise maps to fixed muscles, movements are recognised, the findings are right for
// good and bad plans (one of them a real plan with warm-up drills, numbers in notes and once-a-week upper body), and the connector's copy is the same.
import { createRequire } from 'module';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
const require = createRequire(import.meta.url);
const PC = require('../plancheck.js');
const src = readFileSync(new URL('../src/yes-coach.html', import.meta.url), 'utf8');
const LIB = JSON.parse(src.match(/const LIB = (\[.*?\]);\n/)[1]);
let n = 0;
const ok = (c, m) => { n += 1; if (!c) { console.error('FAIL', m); process.exit(1); } };

// ---- muscles: every library exercise counts for at least one muscle, except the few that train something not counted
const NOT_COUNTED = /traps|adductors|forearm|grip|tibialis/i;
for (const l of LIB) {
  if (l.category === 'cardio') continue;
  const m = PC.musclesOf(l);
  ok(Object.keys(m).length > 0 || NOT_COUNTED.test(l.primary), l.name + ' maps to a muscle: ' + l.primary);
  ok(Object.values(m).every((v) => v > 0 && v <= 1), l.name + ': each muscle at most once, at most a full set');
}
ok(JSON.stringify(PC.splitTags('Hip abductors (glute medius, glute minimus), Core')) === JSON.stringify(['hip abductors (glute medius, glute minimus)', 'core']), 'a comma inside brackets does not split');
ok(PC.musclesOf({ primary: 'Front and side delts', secondary: 'Triceps' }).side_delts === 0.5, 'a press counts half for the side delts');
ok(PC.musclesOf({ primary: 'Mid back, lats', secondary: 'Biceps' }).back === 1, 'a row credits the back once, not twice');

// ---- movements and roles, from the name (also for your own exercises)
const pat = { 'Squat': 'knee', 'Leg press': 'knee', 'Bulgarian split squat': 'knee', 'Romanian deadlift': 'hinge', 'Hip thrust': 'hinge', '45° back extension (hips)': 'hinge',
  'Barbell bench press': 'hpush', 'Incline dumbbell bench press': 'hpush', 'Assisted dips': 'hpush', 'Push-up': 'hpush', 'Dumbbell shoulder press': 'vpush', 'Overhead press': 'vpush',
  'Seated cable row': 'hpull', 'One-handed dumbbell row': 'hpull', 'T-bar row': 'hpull', 'Lat pulldown': 'vpull', 'Assisted pull-up': 'vpull', 'Pull-up (reverse grip)': 'vpull',
  'Prone leg curl': 'legcurl', 'Seated leg curl': 'legcurl', 'Lateral raise': '', 'Upright row': '', 'Face pull': '' };
for (const [name, p] of Object.entries(pat)) ok(PC.patternOf(name) === p, name + ' is ' + (p || 'no main movement') + ', got ' + PC.patternOf(name));
ok(PC.describe({ name: 'Calf raise', group: 'Other' }).muscles.calves === 1, 'your own "Calf raise" counts for calves by its name');
ok(PC.describe({ name: 'Warm-up cardio', group: 'Other', unit: 'min' }).role === 'cardio', 'cardio is not counted as sets');
ok(PC.describe(null).unknown, 'a missing exercise is unknown');

// ---- plans
const byName = new Map(LIB.map((l) => [l.name.toLowerCase(), l]));
const lib = (name) => byName.get(name.toLowerCase());
const it = (name, sets, reps, rest = 90, extra = {}) => Object.assign({ ex: name, sets, reps, rest_s: rest }, extra);
const lookupLib = (id) => { const l = lib(id); return l ? Object.assign({}, l) : null; };
const codes = (r, level) => r.findings.filter((f) => !level || f.level === level).map((f) => f.code);
const ctx = (o) => Object.assign({ lookup: lookupLib, experience: 'some', goal: 'muscle', length: 'medium' }, o);

// a sound upper/lower week, 4 days, 60 minutes
const upperA = { name: 'Upper A', items: [it('Barbell bench press', 3, '6 to 8', 150), it('Seated cable row', 3, '8 to 12', 120), it('Dumbbell shoulder press', 3, '8 to 12', 90), it('Lat pulldown', 3, '8 to 12', 90), it('Lateral raise', 3, '12 to 20', 60), it('Tricep rope pushdown', 2, '10 to 15', 60), it('Alternating dumbbell curl', 2, '10 to 15', 60)] };
const lowerA = { name: 'Lower A', items: [it('Squat', 3, '6 to 8', 180), it('Romanian deadlift', 3, '8 to 12', 120), it('Leg extension', 3, '10 to 15', 75), it('Prone leg curl', 3, '10 to 15', 75), it('Standing calf raise', 3, '12 to 20', 60), it('Plank', 2, '30 to 45 s', 45)] };
const upperB = { name: 'Upper B', items: [it('Incline dumbbell press', 3, '8 to 12', 120), it('One-handed dumbbell row', 3, '8 to 12 per arm', 90), it('Assisted pull-up', 3, '6 to 10', 120), it('Machine chest press', 2, '10 to 12', 90), it('Face pull', 3, '12 to 15', 60), it('Hammer curl', 2, '10 to 15', 60), it('Overhead cable extension', 2, '10 to 15', 60)] };
const lowerB = { name: 'Lower B', items: [it('Leg press', 3, '8 to 12', 150), it('Hip thrust', 3, '8 to 12', 120), it('Bulgarian split squat', 2, '8 to 12 per leg', 90), it('Seated leg curl', 3, '10 to 15', 75), it('Seated calf raise', 3, '12 to 20', 60), it('Cable crunch', 2, '10 to 15', 60)] };
let r = PC.check({ perWeek: 4, days: [upperA, lowerA, upperB, lowerB] }, ctx());
ok(!codes(r, 'error').length && !codes(r).includes('freq') && !codes(r).includes('missing'), 'a sound upper/lower week has no errors and every big muscle twice: ' + JSON.stringify(r.findings));
ok(r.weekly.chest.sessions === 2 && r.weekly.back.sets >= 10 && r.weekly.quads.sets >= 10, 'sets and sessions per week are counted: ' + JSON.stringify(r.weekly));
ok(r.minutes.every((m) => m >= 30 && m <= 72), 'each day fits about an hour: ' + r.minutes);
ok(!codes(r).includes('pull_push') && !codes(r).includes('consecutive'), 'balanced, and the two lower days are not next to each other');

// the same week as a rotation of 4 days done 2 times a week: everything once a week
r = PC.check({ perWeek: 2, days: [upperA, lowerA, upperB, lowerB] }, ctx());
ok(r.weekly.chest.sessions === 1 && (codes(r).includes('vol_low') || codes(r).includes('vol_low_time')), 'four days done twice a week halves the volume: ' + JSON.stringify(r.weekly.chest));

// only upper body: the must-haves are missing
r = PC.check({ perWeek: 2, days: [upperA, upperB] }, ctx());
ok(codes(r, 'error').filter((c) => c === 'missing').length === 2 && r.findings[0].level === 'error', 'no squat and no hinge are errors, listed first: ' + r.findings.map((f) => f.text).join(' | '));

// two lower days in a row
r = PC.check({ perWeek: 4, days: [upperA, lowerA, lowerB, upperB] }, ctx());
ok(codes(r).includes('consecutive'), 'two lower days next to each other are flagged');

// pressing without pulling
r = PC.check({ perWeek: 3, days: [{ name: 'Push', items: [it('Barbell bench press', 4, '6 to 8', 150), it('Dumbbell shoulder press', 3, '8 to 12'), it('Incline dumbbell press', 3, '8 to 12'), it('Squat', 3, '6 to 8', 180), it('Romanian deadlift', 3, '8 to 12'), it('Seated cable row', 2, '8 to 12')] }] }, ctx());
ok(codes(r).includes('pull_push'), 'more pressing than pulling is flagged');

// far too long
r = PC.check({ perWeek: 2, days: [Object.assign({}, upperA, { items: upperA.items.concat(upperB.items) }), lowerA] }, ctx({ length: 'short' }));
ok(codes(r, 'error').includes('over_time'), 'a day far over the session length is an error: ' + r.minutes);

// fixed reps: a warning in a new plan, only information in a plan made before ranges were the rule
const fixedDay = { name: 'Full', items: [it('Squat', 3, '8', 150), it('Romanian deadlift', 3, '10'), it('Barbell bench press', 3, '8'), it('Seated cable row', 3, '10')] };
ok(PC.check({ perWeek: 2, days: [fixedDay] }, ctx()).findings.find((f) => f.code === 'fixed_reps').level === 'warn', 'fixed reps warn in a new plan');
ok(PC.check({ perWeek: 2, days: [fixedDay] }, ctx({ legacy: true })).findings.find((f) => f.code === 'fixed_reps').level === 'info', 'and are only information in an existing plan');

// bands follow experience and goal
ok(JSON.stringify(PC.bandsFor('new', 'muscle').major) === '[6,10]' && JSON.stringify(PC.bandsFor('years', 'muscle').major) === '[12,20]' && PC.bandsFor('new', 'lose').major[0] === 4, 'bands by experience, lower for losing weight');

// a real plan: own exercises (no library data), warm-up drills as exercises, numbers in notes, upper body once a week
const own = { 'warm-up-cardio': ['Warm-up cardio', 'Other', 'min'], 'full-shoulder-rotation': ['Full shoulder rotation', 'Shoulders', 'kg'], 'assisted-pull-up': ['Assisted pull-up', 'Back', 'assist'], 'lat-pulldown': ['Lat pulldown', 'Back', 'stack'], 'seated-cable-row': ['Seated cable row', 'Back', 'stack'], 'one-handed-dumbbell-row': ['One-handed dumbbell row', 'Back', 'kg'], 'face-pull': ['Face pull', 'Shoulders', 'stack'], 'cable-crunch': ['Cable crunch', 'Core', 'stack'], 'dumbbell-preacher-curl': ['Dumbbell preacher curl', 'Arms', 'kg'], squat: ['Squat', 'Legs', 'kg'], 'back-extension-hips': ['45° back extension (hips)', 'Legs', 'kg'], 'leg-press': ['Leg press', 'Legs', 'stack'], 'prone-leg-curl': ['Prone leg curl', 'Legs', 'stack'], 'calf-raise': ['Calf raise', 'Other', 'kg'], 'shoulder-rotation-pulley': ['Shoulder rotation (pulley)', 'Shoulders', 'stack'], 'incline-dumbbell-bench-press': ['Incline dumbbell bench press', 'Chest', 'kg'], 'assisted-dips': ['Assisted dips', 'Chest', 'assist'], 'machine-chest-fly': ['Machine chest fly', 'Chest', 'stack'], 'tricep-extension': ['Tricep extension', 'Arms', 'stack'], 'lateral-raise': ['Lateral raise', 'Shoulders', 'kg'], 'cross-armed-extension': ['Cross armed extension', 'Shoulders', 'stack'], 'seated-leg-curl': ['Seated leg curl', 'Legs', 'stack'], 'leg-extension': ['Leg extension', 'Legs', 'stack'], 'hip-abduction-machine': ['Hip abduction machine', 'Legs', 'stack'] };
const key = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const libByKey = new Map(LIB.map((l) => [key(l.name), l]));
const lookupOwn = (id) => { const [name, group, unit] = own[id]; const l = libByKey.get(key(name)); return Object.assign({ name, group, unit }, l ? { primary: l.primary, secondary: l.secondary, shoulder: l.shoulder } : {}); };
const o = (e, sets, reps, rest, note) => ({ ex: e, sets, reps, rest_s: rest, note });
const mine = { perWeek: 4, days: [
  { name: 'Back A', items: [o('warm-up-cardio', 1, '', 0), o('full-shoulder-rotation', 2, '10', 30), o('assisted-pull-up', 3, '8', 120, 'Hold 20.3 until all three sets reach 8, then one step less assistance.'), o('lat-pulldown', 3, '8', 90), o('seated-cable-row', 3, '10', 90), o('one-handed-dumbbell-row', 3, '10 per arm', 75), o('face-pull', 3, '15', 60), o('cable-crunch', 3, '10 to 12', 60), o('dumbbell-preacher-curl', 3, '10', 75)] },
  { name: 'Legs A', items: [o('squat', 3, '8', 150), o('back-extension-hips', 3, '12', 60), o('leg-press', 3, '10', 90), o('prone-leg-curl', 3, '10 to 12', 75), o('calf-raise', 3, '15', 60)] },
  { name: 'Chest and shoulders', items: [o('shoulder-rotation-pulley', 2, '80 total', 30), o('incline-dumbbell-bench-press', 3, '10', 120), o('assisted-dips', 3, '10', 120), o('machine-chest-fly', 3, '10', 75, 'Pain-free range only. 5 Nov: 73, 79, 79, all 10.'), o('tricep-extension', 2, '10', 60), o('lateral-raise', 3, '12 to 15', 60), o('cross-armed-extension', 3, '15', 60)] },
  { name: 'Legs B', items: [o('squat', 5, '8', 150), o('seated-leg-curl', 3, '12', 90), o('leg-extension', 3, '12', 90), o('hip-abduction-machine', 3, '12 to 15', 60), o('cable-crunch', 3, '12', 75)] }] };
r = PC.check(mine, { lookup: lookupOwn, experience: 'some', goal: 'muscle', length: 'medium', legacy: true });
const txt = r.findings.map((f) => f.level + ': ' + f.text).join('\n');
ok(!codes(r, 'error').length, 'the real plan has no errors: ' + txt);
ok(r.findings.filter((f) => f.code === 'warmup_unmarked').length === 3, 'three warm-up drills are flagged: ' + txt);
ok(r.findings.filter((f) => f.code === 'note_numbers').length === 1 && /Assisted pull-up, Machine chest fly/.test(r.findings.find((f) => f.code === 'note_numbers').text), 'both notes with numbers are named in one line (hold until, a date): ' + txt);
ok(/Chest, Back/.test((r.findings.find((f) => f.code === 'freq') || {}).text || ''), 'chest and back are trained once a week: ' + txt);
ok(r.weekly.quads.sessions === 2 && r.weekly.calves.sets <= 6, 'legs twice a week, calves low: ' + JSON.stringify(r.weekly));
ok(r.weekly.front_delts.sets < 9, 'the shoulder drills are not counted as shoulder work: ' + r.weekly.front_delts.sets);

// squats and leg presses give no hamstring credit; a hinge and a leg curl do
ok(!('hamstrings' in PC.describe(LIB.find((l) => l.name === 'Squat')).muscles) && !('hamstrings' in PC.describe(LIB.find((l) => l.name === 'Leg press')).muscles), 'no hamstring credit from squat or leg press');
ok(PC.describe(LIB.find((l) => l.name === 'Romanian deadlift')).muscles.hamstrings === 1 && PC.describe(LIB.find((l) => l.name === 'Seated leg curl')).muscles.hamstrings === 1, 'a hinge and a leg curl count in full');
ok(r.weekly.hamstrings.sets === 9, 'hamstrings: back extension and two leg curls, 9 sets: ' + r.weekly.hamstrings.sets);

// the real schedule: 7 slots (Back A, Legs A, Chest, Legs B, Back A, Legs A, Chest) at 5 a week, so Legs B comes round half as often
const slots = [0, 1, 2, 3, 0, 1, 2];
const per = 5;
const weighted = { perWeek: per, order: slots, days: mine.days.map((d, i) => Object.assign({}, d, { perWeek: (slots.filter((x) => x === i).length * per) / slots.length })) };
const rw = PC.check(weighted, { lookup: lookupOwn, experience: 'some', goal: 'muscle', length: 'medium', legacy: true });
const close = (a, b) => Math.abs(a - b) < 0.11;
ok(close(rw.weekly.back.sets, 12 * 10 / 7 + 1.5 * 10 / 7), 'back: Back A twice in 7 slots at 5 a week: ' + rw.weekly.back.sets);
ok(close(rw.weekly.quads.sessions, 15 / 7), 'quads: Legs A twice and Legs B once in 7 slots: ' + rw.weekly.quads.sessions);
ok(!rw.findings.some((f) => f.code === 'vol_high' && f.level !== 'info'), 'above the range is information only: ' + rw.findings.map((f) => f.text).join(' | '));

// more sets than the range: information, not a warning
const big = { name: 'Big', items: [it('Barbell bench press', 8, '6 to 10', 150), it('Incline dumbbell press', 8, '8 to 12'), it('Seated cable row', 8, '8 to 12'), it('Squat', 4, '6 to 10', 150), it('Romanian deadlift', 4, '8 to 12')] };
const rb = PC.check({ perWeek: 2, days: [big] }, ctx({ length: 600 }));
ok(rb.findings.some((f) => f.code === 'vol_high' && f.level === 'info') && !rb.findings.some((f) => f.code === 'vol_high' && f.level === 'warn'), 'chest far above the range: info');

// a drill they log with a weight and build up is not called a warm-up
const rt = PC.check(mine, { lookup: lookupOwn, experience: 'some', goal: 'muscle', length: 'medium', legacy: true, tracked: (id) => id === 'full-shoulder-rotation' || id === 'shoulder-rotation-pulley' });
ok(rt.findings.filter((f) => f.code === 'warmup_unmarked').length === 1, 'only the warm-up cardio is flagged when the drills are tracked: ' + rt.findings.map((f) => f.text).join(' | '));
ok(!rt.findings.some((f) => f.code === 'order'), 'and a tracked drill at the start is no order problem: ' + rt.findings.map((f) => f.text).join(' | '));

// training less often than the plan is set for
ok(PC.check(weighted, { lookup: lookupOwn, legacy: true, actualPerWeek: 2.1 }).findings.some((f) => f.code === 'attendance' && /about 2.1 times a week .* set for 5/.test(f.text)), 'logs 2.1 a week against 5 planned: flagged');
ok(!PC.check(weighted, { lookup: lookupOwn, legacy: true, actualPerWeek: 4.2 }).findings.some((f) => f.code === 'attendance'), '4.2 against 5: fine');
ok(!PC.check(weighted, { lookup: lookupOwn, legacy: true }).findings.some((f) => f.code === 'attendance'), 'no log: nothing said');

// two heavy days in a row follow the rotation order, repeats included
const pushA = { name: 'Push', items: [it('Barbell bench press', 4, '6 to 10', 150), it('Incline dumbbell press', 3, '8 to 12')] };
const pushB = { name: 'Push 2', items: [it('Machine chest press', 4, '8 to 12'), it('Seated cable row', 3, '8 to 12')] };
const legs = { name: 'Legs', items: [it('Squat', 4, '6 to 10', 150), it('Romanian deadlift', 3, '8 to 12')] };
ok(PC.check({ perWeek: 4, days: [pushA, legs, pushB], order: [0, 1, 2, 1] }, ctx()).findings.every((f) => f.code !== 'consecutive'), 'Push, Legs, Push 2, Legs: no chest days in a row');
ok(PC.check({ perWeek: 4, days: [pushA, legs, pushB], order: [0, 2, 1, 1] }, ctx()).findings.some((f) => f.code === 'consecutive'), 'Push then Push 2: flagged');

// ---- the connector carries the same code
execFileSync('python3', [new URL('../tools/sync_plancheck.py', import.meta.url).pathname]);
const fn = readFileSync(new URL('../supabase/functions/mcp/index.ts', import.meta.url), 'utf8');
ok(fn.includes(readFileSync(new URL('../plancheck.js', import.meta.url), 'utf8')), 'the connector carries plancheck.js unchanged (run python3 build.py)');
console.log(n + ' plan check tests passed');
