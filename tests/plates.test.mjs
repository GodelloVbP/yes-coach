// Plate maths. Run: node tests/plates.test.mjs
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const { plan, PLATES, BARS } = createRequire(import.meta.url)('../plates.js');
let n = 0;
const ok = (cond, msg) => { assert.ok(cond, msg); n += 1; };
const eq = (a, b, msg) => { assert.deepEqual(a, b, msg); n += 1; };

eq(PLATES, [25, 20, 15, 10, 5, 2.5, 1.25], 'default plates');
eq(BARS, [20, 15, 10], 'bars');
eq(plan(100, 20).side, [25, 15], '100 kg on a 20 kg bar: 25 + 15 a side (two plates)');
eq(plan(60, 20).side, [20], '60 kg: one 20 a side');
eq(plan(20, 20).side, [], 'the empty bar');
ok(plan(20, 20).exact, 'the empty bar is exact');
eq(plan(62.5, 20).side, [20, 1.25], '62.5 kg: 20 + 1.25 a side');
eq(plan(142.5, 20).side.reduce((a, b) => a + b, 0), 61.25, '142.5 kg is 61.25 a side');
eq(plan(40, 15).side, [10, 2.5], '40 kg on a 15 kg bar: 12.5 a side');
eq(plan(30, 10).side, [10], '30 kg on a 10 kg bar');
// below the bar
ok(plan(15, 20).below, '15 kg is lighter than the bar');
// not buildable: 61 kg needs 20.5 a side; the nearest loads are 60 and 62.5
let r = plan(61, 20);
ok(!r.exact, '61 kg cannot be built');
eq([r.lower.total, r.upper.total], [60, 62.5], 'nearest loads around 61 kg');
// custom plate sets
r = plan(60, 20, [25, 15]);
ok(!r.exact, '60 kg cannot be built with 25 and 15 only (20 a side)');
eq(r.side, [], 'no plates for an unbuildable load');
r = plan(60, 20, [25, 10, 5]);
ok(r.exact, 'but 20 a side builds from 10 + 10 when 10 is there');
eq(r.side, [10, 10], '60 kg with 25, 10, 5: 10 + 10');
// the greedy choice would fail here: 30 a side from 25 and 10 and 20 is 20 + 10, not 25 + 5
eq(plan(80, 20, [25, 20, 10]).side, [20, 10], '80 kg with 25, 20, 10: 20 + 10');
// 40 a side from 25 and 20 and 10 prefers fewer plates
eq(plan(100, 20, [25, 20, 10]).side, [20, 20], '100 kg: 20 + 20 rather than 25 + 10 + 5');
ok(plan(100, 20, [25, 20, 10]).side.length === 2, 'fewest plates');
// junk in
ok(plan(0, 20) === null && plan('x', 20) === null && plan(NaN, 20) === null, 'junk gives null');
// a load with an odd decimal
r = plan(61.1, 20);
ok(!r.exact && r.lower.total <= 61.1 && r.upper.total >= 61.1, 'in between lower and upper');
// totals always add up
for (const total of [20, 22.5, 25, 47.5, 87.5, 102.5, 137.5, 182.5, 200, 227.5]) {
  const p = plan(total, 20);
  ok(p.exact, total + ' kg builds');
  eq(20 + 2 * p.side.reduce((a, b) => a + b, 0), total, total + ' kg adds up');
}
console.log(n + ' checks passed');
