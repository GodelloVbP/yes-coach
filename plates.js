// Plate maths for a barbell: which plates go on each side for a total load, and the nearest loads that can be built.
// Pure: no page, no storage. Used by the app (window.YC_PLATES) and by tests/plates.test.mjs.
(function (root) {
  'use strict';
  var PLATES = [25, 20, 15, 10, 5, 2.5, 1.25];
  var BARS = [20, 15, 10];
  var U = 4; // work in quarter kilos so 1.25 and 2.5 stay whole numbers
  var MAX_SIDE = 400 * U; // 400 kg a side is more than anyone loads
  var u = function (kg) { return Math.round(kg * U); };

  // fewest plates per side for every reachable side weight, in quarter kilos: best[w] = {n, last}
  function table(plates) {
    var ps = plates.map(u).filter(function (p) { return p > 0; }).sort(function (a, b) { return b - a; });
    var n = new Array(MAX_SIDE + 1).fill(Infinity);
    var last = new Array(MAX_SIDE + 1).fill(0);
    n[0] = 0;
    for (var w = 1; w <= MAX_SIDE; w += 1) {
      for (var i = 0; i < ps.length; i += 1) {
        var p = ps[i];
        if (p <= w && n[w - p] + 1 < n[w]) { n[w] = n[w - p] + 1; last[w] = p; }
      }
    }
    return { n: n, last: last };
  }
  function sideOf(t, w) {
    var out = [];
    while (w > 0) { out.push(t.last[w] / U); w -= t.last[w]; }
    return out.sort(function (a, b) { return b - a; });
  }
  // plan(total, bar, plates) -> { total, bar, below, exact, side, lower, upper }
  // lower/upper: the nearest loads you can build under and over the total (each {total, side}), when it cannot be built exactly
  function plan(total, bar, plates) {
    total = Number(total); bar = Number(bar);
    if (!isFinite(total) || !isFinite(bar) || total <= 0) return null;
    var list = (plates && plates.length ? plates : PLATES);
    var t = table(list);
    var raw = (total - bar) / 2 * U;
    var need = Math.round(raw);
    if (total < bar) return { total: total, bar: bar, below: true, exact: false, side: [], lower: null, upper: null };
    var build = function (w) { return { total: bar + 2 * w / U, side: sideOf(t, w) }; };
    var exact = Math.abs(raw - need) < 1e-6 && need <= MAX_SIDE && t.n[need] !== Infinity;
    if (exact) return { total: total, bar: bar, below: false, exact: true, side: sideOf(t, need), lower: null, upper: null };
    var lo = null, hi = null;
    for (var w = Math.floor(raw); w >= 0; w -= 1) if (t.n[w] !== Infinity) { lo = w; break; }
    for (var v = Math.ceil(raw); v <= MAX_SIDE; v += 1) if (t.n[v] !== Infinity) { hi = v; break; }
    return { total: total, bar: bar, below: false, exact: false, side: [], lower: lo === null ? null : build(lo), upper: hi === null ? null : build(hi) };
  }
  // The warm-up ramp for a working load: the empty bar for 10, then 50% for 5, 70% for 3 and 85% for 1, each rounded to 2.5 kg.
  // Under 40 kg there is nothing to warm up for. bar is null for exercises without a bar (the ramp then starts at 50%).
  var WARM_MIN = 40;
  function warmups(total, bar) {
    total = Number(total);
    if (!isFinite(total) || total < WARM_MIN) return [];
    var out = [];
    var take = function (load, reps) {
      var last = out.length ? out[out.length - 1].load : 0;
      if (load > last && load < total) out.push({ load: load, reps: reps });
    };
    if (bar != null && Number(bar) > 0) take(Number(bar), 10);
    [[0.5, 5], [0.7, 3], [0.85, 1]].forEach(function (s) { take(Math.round(total * s[0] / 2.5) * 2.5, s[1]); });
    return out;
  }
  root.YC_PLATES = { PLATES: PLATES, BARS: BARS, plan: plan, warmups: warmups, WARM_MIN: WARM_MIN };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.YC_PLATES;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
