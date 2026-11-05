import { createRequire } from 'module';
import assert from 'assert';
const require = createRequire(import.meta.url);
const P = require('../progression.js');
let n = 0;
const t = (name, fn) => { fn(); n += 1; };
const H = (date, loads, reps, extra = {}) => ({ date, sets: loads.map((l, i) => Object.assign({ n: i + 1, load: l, reps: Array.isArray(reps) ? reps[i] : reps }, extra)) });
const base = { unit: 'kg', reps: '8', sets: 3, inc: 2.5, uw: 'kg', today: '2026-11-05' };
const S = (o) => P.suggest(Object.assign({}, base, o));

t('parseReps', () => {
  assert.deepEqual(P.parseReps('8'), { mode: 'fixed', n: 8 });
  assert.deepEqual(P.parseReps('10 per arm'), { mode: 'fixed', n: 10 });
  assert.deepEqual(P.parseReps('8-12'), { mode: 'range', lo: 8, hi: 12 });
  assert.deepEqual(P.parseReps('8 to 12'), { mode: 'range', lo: 8, hi: 12 });
  assert.deepEqual(P.parseReps('Max'), { mode: 'max' });
  assert.equal(P.parseReps(''), null);
  assert.equal(P.parseReps('until it burns'), null);
});
t('default increments', () => {
  assert.equal(P.defaultInc({ unit: 'kg', equipment: 'Barbell', group: 'Legs', name: 'Squat' }), 5);
  assert.equal(P.defaultInc({ unit: 'kg', equipment: 'Barbell', group: 'Back', name: 'Deadlift' }), 5);
  assert.equal(P.defaultInc({ unit: 'kg', equipment: 'Barbell', group: 'Chest', name: 'Bench press' }), 2.5);
  assert.equal(P.defaultInc({ unit: 'kg', equipment: 'Dumbbell', group: 'Chest' }), 2);
  assert.equal(P.defaultInc({ unit: 'kg', equipment: 'Plate-loaded machine', load_basis: 'per_side' }), 1.25);
  assert.equal(P.defaultInc({ unit: 'kg', equipment: 'Cable' }), 2.5);
  assert.equal(P.defaultInc({ unit: 'stack', equipment: 'Machine' }), 1);
  assert.equal(P.defaultInc({ unit: 'kg', equipment: 'Barbell', inc: 1 }), 1);
});
t('no history or no plan reps: nothing to say', () => {
  assert.equal(S({ history: [] }), null);
  assert.equal(S({ reps: '', history: [H('2026-11-02', [60, 60, 60], 8)] }), null);
  assert.equal(S({ unit: 'min', history: [H('2026-11-02', [60], 8)] }), null);
});
t('plan target newer than the last session wins; an older one does not', () => {
  const h = [H('2026-11-02', [60, 60, 60], 8)];
  assert.equal(S({ history: h, target: '65', targetAt: '2026-11-04' }), null);
  assert.equal(S({ history: h, target: '65' }), null);
  const r = S({ history: h, target: '65', targetAt: '2026-10-30' });
  assert.equal(r.load, 62.5);
});
t('fixed reps, every set reached: add the step', () => {
  const r = S({ history: [H('2026-11-02', [60, 60, 60], 8)] });
  assert.equal(r.load, 62.5); assert.equal(r.reps, 8); assert.equal(r.kind, 'up'); assert.equal(r.delta, 2.5);
  assert.equal(r.reason, '+2.5 kg: all 3 sets reached 8 last time');
});
t('more reps than planned still counts as reached', () => {
  assert.equal(S({ history: [H('2026-11-02', [60, 60, 60], [9, 8, 10])] }).load, 62.5);
});
t('fewer sets than planned: hold, no increase', () => {
  const r = S({ history: [H('2026-11-02', [60, 60], 8)] });
  assert.equal(r.load, 60); assert.equal(r.kind, 'same'); assert.match(r.reason, /2 of 3 sets/);
});
t('a set short for the first time: same weight', () => {
  const r = S({ history: [H('2026-11-02', [60, 60, 60], [8, 8, 6]), H('2026-10-30', [60, 60, 60], 8)] });
  assert.equal(r.load, 60); assert.equal(r.kind, 'same'); assert.match(r.reason, /not every set reached 8/);
});
t('short at the same weight twice: stuck', () => {
  const r = S({ history: [H('2026-11-02', [60, 60, 60], [8, 7, 6]), H('2026-10-29', [60, 60, 60], [8, 6, 6])] });
  assert.equal(r.load, 60); assert.equal(r.reason, 'Stuck at 60 kg: same weight again');
});
t('short at the same weight three times: ten percent down, to a loadable weight', () => {
  const sh = (d) => H(d, [60, 60, 60], [8, 6, 6]);
  const r = S({ history: [sh('2026-11-02'), sh('2026-10-29'), sh('2026-10-26')] });
  assert.equal(r.load, 53.75); assert.equal(r.kind, 'down');
  const r2 = S({ inc: 5, history: [sh('2026-11-02'), sh('2026-10-29'), sh('2026-10-26')] });
  assert.equal(r2.load, 53.75);
  const r3 = S({ inc: 1, history: [sh('2026-11-02'), sh('2026-10-29'), sh('2026-10-26')] });
  assert.equal(r3.load, 54);
});
t('a different weight in between breaks the run of misses', () => {
  const r = S({ history: [H('2026-11-02', [60, 60, 60], [8, 6, 6]), H('2026-10-29', [57.5, 57.5, 57.5], [8, 6, 6])] });
  assert.match(r.reason, /not every set reached/);
});
t('range: all sets at the top goes up and drops to the bottom', () => {
  const r = S({ reps: '8-12', history: [H('2026-11-02', [40, 40, 40], 12)] });
  assert.equal(r.load, 42.5); assert.equal(r.reps, 8); assert.equal(r.kind, 'up');
});
t('range: inside the range, one more rep per set up to the top', () => {
  const r = S({ reps: '8-12', history: [H('2026-11-02', [40, 40, 40], [12, 10, 9])] });
  assert.equal(r.load, 40); assert.deepEqual(r.repsBySet, [12, 11, 10]); assert.equal(r.reps, 12);
});
t('range: below the bottom is short', () => {
  const r = S({ reps: '8-12', history: [H('2026-11-02', [40, 40, 40], [9, 8, 7])] });
  assert.equal(r.load, 40); assert.match(r.reason, /not every set reached 8/);
});
t('low reps in the last logged RIR: no increase', () => {
  const r = S({ history: [H('2026-11-02', [60, 60, 60], 8, { rir: 0 })] });
  assert.equal(r.load, 60); assert.equal(r.kind, 'same'); assert.match(r.reason, /close to failure/);
  assert.equal(S({ history: [H('2026-11-02', [60, 60, 60], 8, { rir: 2 })] }).load, 62.5);
});
t('15 to 28 days off: same weight, no increase', () => {
  const r = S({ history: [H('2026-10-15', [60, 60, 60], 8)] });
  assert.equal(r.load, 60); assert.equal(r.kind, 'same'); assert.equal(r.reason, 'Back after 21 days: same weight as last time');
});
t('14 days is still normal', () => {
  assert.equal(S({ history: [H('2026-10-22', [60, 60, 60], 8)] }).load, 62.5);
});
t('over 28 days off: ten percent down', () => {
  const r = S({ history: [H('2026-09-20', [60, 60, 60], 8)] });
  assert.equal(r.load, 53.75); assert.equal(r.kind, 'down'); assert.match(r.reason, /46 days/);
});
t('max reps: last best plus one, same weight', () => {
  const r = S({ reps: 'max', sets: 1, history: [H('2026-11-02', [20], 11)] });
  assert.equal(r.load, 20); assert.equal(r.reps, 12);
});
t('bodyweight: one more rep per set, then add load', () => {
  const r = S({ unit: 'bw', reps: '8-12', history: [H('2026-11-02', [null, null, null], [10, 9, 8])] });
  assert.deepEqual(r.repsBySet, [11, 10, 9]); assert.equal(r.load, null);
  const top = S({ unit: 'bw', reps: '8-12', history: [H('2026-11-02', [null, null, null], 12)] });
  assert.match(top.reason, /add some weight/); assert.equal(top.reps, 12);
  const cap = S({ unit: 'bw', reps: '8-12', history: [H('2026-11-02', [null, null, null], [12, 11, 12])] });
  assert.deepEqual(cap.repsBySet, [12, 12, 12]);
});
t('assistance: less help when the target is met', () => {
  const r = S({ unit: 'assist', inc: 5, history: [H('2026-11-02', [30, 30, 30], 8)] });
  assert.equal(r.load, 25); assert.equal(r.reason, '-5 kg: all 3 sets reached 8 last time');
  assert.equal(S({ unit: 'assist', inc: 5, history: [H('2026-11-02', [3, 3, 3], 8)] }).load, 0);
  assert.equal(S({ unit: 'assist', inc: 5, history: [H('2026-11-02', [30, 30, 30], [8, 8, 5])] }).load, 30);
});
t('warm-up, drop and test sets are ignored', () => {
  const h = H('2026-11-02', [60, 60, 60], 8);
  h.sets.push({ n: 4, load: 20, reps: 10, kind: 'warmup' }, { n: 5, load: 40, reps: 3, kind: 'drop' }, { n: 6, load: 80, reps: 1, kind: 'test' });
  assert.equal(S({ history: [h] }).load, 62.5);
});
t('steps that do not fit the plates are rounded', () => {
  assert.equal(S({ inc: 2, uw: 'kg', history: [H('2026-11-02', [20, 20, 20], 8)] }).load, 22);
  assert.equal(S({ unit: 'stack', inc: 1, uw: 'pin', history: [H('2026-11-02', [7, 7, 7], 8)] }).reason, '+1 pin: all 3 sets reached 8 last time');
});
console.log('progression ok,', n, 'groups');
