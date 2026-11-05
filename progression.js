// Progression: the weight and reps to suggest for the next session of one exercise, from what was logged before.
// Pure: no page, no storage. Used by the app (window.YC_PROGRESSION) and by tests/progression.test.mjs.
(function (root) {
  'use strict';

  // Reason lines. English templates; the app shows them as written and the translation tables carry the same text with {0}, {1}, {2}.
  var R = {
    up: '+{0}: all {1} sets reached {2} last time',
    less_help: '-{0}: all {1} sets reached {2} last time',
    at_limit: 'Same weight: your last sets were close to failure',
    short: 'Same weight again: not every set reached {0}',
    stuck: 'Stuck at {0}: same weight again',
    deload: 'Down to {0}: short on reps at the same weight three sessions running',
    rep_up: 'Same weight, aim for one more rep',
    back: 'Back after {0} days: same weight as last time',
    long_off: 'Down to {0}: {1} days since your last session',
    fewer_sets: 'Same weight: last time you did {0} of {1} sets',
    max: 'Beat last time: {0} reps',
    bw_up: 'One more rep on each set',
    bw_load: 'You reached {0} reps on every set: add some weight'
  };

  var INC_DEFAULT = 2.5;
  var BARBELL = /barbell|ez-bar|trap bar|safety squat/i;
  var LEGS = /deadlift|squat|leg press|lunge|hip thrust/i;

  var round2 = function (x) { return Math.round(x * 100) / 100; };
  var numStr = function (x) { return String(round2(x)); };
  var fill = function (tpl, args) { return tpl.replace(/\{(\d)\}/g, function (_, i) { return args[Number(i)]; }); };

  // The step for one exercise: an own setting wins, else it follows the kind of equipment.
  // ex: { inc, unit, load_basis, equipment, name, group }
  function defaultInc(ex) {
    ex = ex || {};
    var own = Number(ex.inc);
    if (own > 0) return own;
    if (ex.unit === 'stack') return 1;
    if (ex.unit === 'assist') return 5;
    if (ex.unit === 'kg' && ex.load_basis === 'per_side') return 1.25;
    var eq = String(ex.equipment || '');
    if (/dumbbell|kettlebell/i.test(eq)) return 2;
    if (/cable/i.test(eq)) return 2.5;
    if (BARBELL.test(eq)) return ex.group === 'Legs' || LEGS.test(ex.name || '') ? 5 : 2.5;
    return INC_DEFAULT;
  }

  // Plan reps: "8" or "10 per arm" is fixed, "8-12" is a range, "max" is as many as possible. Anything else gives null.
  function parseReps(text) {
    var t = String(text == null ? '' : text).toLowerCase().replace(/,/g, '.').trim();
    if (!t) return null;
    if (/max|amrap/.test(t)) return { mode: 'max' };
    var nums = (t.match(/\d+(\.\d+)?/g) || []).map(Number);
    if (!nums.length) return null;
    if (nums.length >= 2 && /^\s*\d+(\.\d+)?\s*(-|–|—|to)\s*\d+/.test(t)) {
      var lo = Math.min(nums[0], nums[1]), hi = Math.max(nums[0], nums[1]);
      return lo === hi ? { mode: 'fixed', n: lo } : { mode: 'range', lo: lo, hi: hi };
    }
    return { mode: 'fixed', n: nums[0] };
  }

  // the smallest weight step the suggestion is rounded to
  function stepFor(inc) { return inc >= 2.5 ? 1.25 : inc >= 2 ? 1 : inc; }
  function snap(x, step) { return round2(Math.round(x / step) * step); }

  function daysBetween(a, b) {
    var pa = String(a).slice(0, 10).split('-').map(Number), pb = String(b).slice(0, 10).split('-').map(Number);
    return Math.round((Date.UTC(pb[0], pb[1] - 1, pb[2]) - Date.UTC(pa[0], pa[1] - 1, pa[2])) / 864e5);
  }

  var isWork = function (st) { return !!st && (st.kind == null || st.kind === 'work'); };
  var has = function (v) { return v != null && v !== '' && !isNaN(Number(v)); };

  // the load most sets were done at (ties go to the harder one)
  function modeLoad(sets, lowerIsHarder) {
    var count = {};
    sets.forEach(function (s) { count[s.load] = (count[s.load] || 0) + 1; });
    var best = null;
    Object.keys(count).forEach(function (k) {
      var v = Number(k);
      if (best == null || count[k] > count[best] || (count[k] === count[best] && (lowerIsHarder ? v < best : v > best))) best = v;
    });
    return best;
  }

  /* input: {
       unit:    'kg' | 'stack' | 'assist' | 'bw' | 'min'
       reps:    the plan's reps text
       sets:    planned number of sets
       inc:     step for one jump (see defaultInc)
       uw:      unit word shown after a weight ("kg", "pin")
       today:   'YYYY-MM-DD'
       target, targetAt: the plan's own target and the day it was set
       history: sessions of this exercise, newest first: [{ date, sets: [{ n, load, reps, rir, kind }] }]
     }
     output: null when the rule has nothing to say (the screen then shows what it always did), else
       { load, reps, repsBySet, kind: 'up' | 'down' | 'same', delta, reason, lastLoad }  */
  function suggest(input) {
    var unit = input.unit || 'kg';
    if (unit === 'min') return null;
    var plan = parseReps(input.reps);
    if (!plan) return null;
    var hist = (input.history || []).map(function (s) { return { date: s.date, sets: (s.sets || []).filter(isWork) }; }).filter(function (s) { return s.sets.length; });
    if (!hist.length) return null;
    var s0 = hist[0];
    // a target the plan set after the last session is the plan's call, not the rule's
    if (String(input.target || '').trim() && (!input.targetAt || String(input.targetAt) > String(s0.date))) return null;

    var uw = input.uw || 'kg';
    var amt = function (x) { return numStr(x) + (uw ? ' ' + uw : ''); };
    var planned = Math.max(1, Number(input.sets) || s0.sets.length);
    var out = function (o) { o.lastLoad = o.lastLoad == null ? null : o.lastLoad; return o; };

    // ---- bodyweight: reps only
    if (unit === 'bw') {
      var last = s0.sets.slice().sort(function (a, b) { return a.n - b.n; });
      var rs = last.map(function (s) { return Number(s.reps) || 0; });
      if (plan.mode === 'max') {
        var bestBw = Math.max.apply(null, rs);
        return out({ load: null, reps: bestBw + 1, repsBySet: null, kind: 'up', delta: 0, reason: fill(R.max, [bestBw + 1]) });
      }
      var topBw = plan.mode === 'range' ? plan.hi : plan.n;
      if (rs.length >= planned && rs.every(function (r) { return r >= topBw; })) {
        return out({ load: null, reps: topBw, repsBySet: null, kind: 'same', delta: 0, reason: fill(R.bw_load, [topBw]) });
      }
      var per = [];
      for (var i = 0; i < Math.max(planned, rs.length); i += 1) {
        var r0 = i < rs.length ? rs[i] : rs[rs.length - 1];
        per.push(Math.min(topBw, r0 + 1));
      }
      return out({ load: null, reps: per[0], repsBySet: per, kind: 'up', delta: 0, reason: R.bw_up });
    }

    // ---- loaded: kg, pin or assistance
    var assist = unit === 'assist';
    var loaded = function (s) { return { n: s.n, load: has(s.load) ? Number(s.load) : null, reps: has(s.reps) ? Number(s.reps) : 0, rir: has(s.rir) ? Number(s.rir) : null }; };
    var sess = hist.map(function (s) {
      var sets = s.sets.map(loaded).filter(function (x) { return x.load != null; });
      return { date: s.date, sets: sets };
    }).filter(function (s) { return s.sets.length; });
    if (!sess.length) return null;
    var inc = Number(input.inc) > 0 ? Number(input.inc) : INC_DEFAULT;
    var step = stepFor(inc);
    var atOrAbove = function (s, L) { return s.sets.filter(function (x) { return assist ? x.load <= L : x.load >= L; }); };
    var lowTarget = plan.mode === 'range' ? plan.lo : plan.mode === 'fixed' ? plan.n : 0;
    var L = modeLoad(sess[0].sets, assist);
    var at = atOrAbove(sess[0], L);
    var days = daysBetween(sess[0].date, input.today || sess[0].date);
    var harder = function (x, d) { return assist ? Math.max(0, x - d) : x + d; };
    var easier = function (x) { return assist ? snap(x * 1.1, step) : snap(x * 0.9, step); };
    var easierThan = function (x) { var y = easier(x); return assist ? (y <= x ? x + step : y) : (y >= x ? Math.max(0, x - step) : y); };
    var repsFor = function (n) { return plan.mode === 'range' ? plan.lo : plan.mode === 'fixed' ? plan.n : n; };

    // ---- time off
    if (days > 28) {
      var back = easierThan(L);
      return out({ load: back, reps: repsFor(0), repsBySet: null, kind: 'down', delta: back - L, reason: fill(R.long_off, [amt(back), days]), lastLoad: L });
    }
    if (days >= 15) {
      return out({ load: L, reps: repsFor(0), repsBySet: null, kind: 'same', delta: 0, reason: fill(R.back, [days]), lastLoad: L });
    }

    // ---- max reps: beat last time at the same weight
    if (plan.mode === 'max') {
      var bestMax = Math.max.apply(null, at.map(function (x) { return x.reps; }));
      return out({ load: L, reps: bestMax + 1, repsBySet: null, kind: 'same', delta: 0, reason: fill(R.max, [bestMax + 1]), lastLoad: L });
    }

    var top = plan.mode === 'range' ? plan.hi : plan.n;
    var rirs = at.filter(function (x) { return x.rir != null; });
    var tooHard = rirs.length > 0 && rirs.reduce(function (a, x) { return a + x.rir; }, 0) / rirs.length < 1;
    var allTop = at.length >= planned && at.every(function (x) { return x.reps >= top; });
    var short = at.some(function (x) { return x.reps < lowTarget; });

    if (allTop) {
      if (tooHard) return out({ load: L, reps: repsFor(0), repsBySet: null, kind: 'same', delta: 0, reason: R.at_limit, lastLoad: L });
      var up = harder(L, inc);
      return out({ load: up, reps: repsFor(0), repsBySet: null, kind: assist ? 'down' : 'up', delta: up - L, reason: fill(assist ? R.less_help : R.up, [amt(inc), at.length, top]), lastLoad: L });
    }

    if (short) {
      // sessions in a row that were short at this same weight
      var c = 0;
      for (var j = 0; j < sess.length; j += 1) {
        if (modeLoad(sess[j].sets, assist) !== L) break;
        var atJ = atOrAbove(sess[j], L);
        if (!atJ.some(function (x) { return x.reps < lowTarget; })) break;
        c += 1;
      }
      if (c >= 3) {
        var d = easierThan(L);
        return out({ load: d, reps: repsFor(0), repsBySet: null, kind: 'down', delta: d - L, reason: fill(R.deload, [amt(d)]), lastLoad: L });
      }
      return out({ load: L, reps: repsFor(0), repsBySet: null, kind: 'same', delta: 0, reason: c === 2 ? fill(R.stuck, [amt(L)]) : fill(R.short, [lowTarget]), lastLoad: L });
    }

    if (at.length < planned) {
      return out({ load: L, reps: repsFor(0), repsBySet: null, kind: 'same', delta: 0, reason: fill(R.fewer_sets, [at.length, planned]), lastLoad: L });
    }

    // Only a range is left here: a fixed plan that missed is a short set, and one that hit everything is allTop.
    // No short sets, not all at the top of the range: one more rep than last time.
    var ordered = at.slice().sort(function (a, b) { return a.n - b.n; });
    var per2 = [];
    for (var k = 0; k < Math.max(planned, ordered.length); k += 1) {
      var r1 = k < ordered.length ? ordered[k].reps : ordered[ordered.length - 1].reps;
      per2.push(Math.min(plan.hi, r1 + 1));
    }
    return out({ load: L, reps: per2[0], repsBySet: per2, kind: 'same', delta: 0, reason: R.rep_up, lastLoad: L });
  }

  var api = { suggest: suggest, parseReps: parseReps, defaultInc: defaultInc, stepFor: stepFor, REASONS: R };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.YC_PROGRESSION = api;
})(typeof window !== 'undefined' ? window : this);
