// The first plan the app makes without an AI: a split that fits the days a week, exercise slots with a role (main lift, compound,
// isolation, core), reps, rest and sets from that role and the person's experience, cut to the session length.
// Pure: no page, no storage. The app loads it as window.YC_STARTER; tests/starter.test.mjs builds every combination and runs the
// plan check (plancheck.js) on it. The rules are in PLAN_MAKER.md.
(function (root) {
  'use strict';

  // per place, per slot: library exercises in order of preference; a "new:" list comes first for people new to training
  var SLOTS = {
    gym: {
      kneeMain: { new: ['l43'], any: ['l42', 'l43'] }, kneeSec: { new: ['l48', 'l46'], any: ['l46', 'l44', 'l47'] }, kneeIso: { any: ['l45'] },
      hingeMain: { any: ['l50', 'l53'] }, hingeSec: { any: ['l53', 'l19'] }, legcurl: { any: ['l51', 'l52'] }, legcurl2: { any: ['l52', 'l51'] },
      hpushMain: { new: ['l01'], any: ['l04', 'l01'] }, hpushSec: { any: ['l02', 'l01'] }, chestIso: { any: ['l05', 'l072'] }, vpush: { new: ['l21'], any: ['l20', 'l21'] },
      hpull: { any: ['l14', 'l13'] }, hpull2: { any: ['l16', 'l17'] }, vpull: { any: ['l10'] }, vpull2: { any: ['l116', 'l10'] },
      side: { any: ['l22', 'l132'] }, rear: { any: ['l25', 'l24'] }, biceps: { any: ['l30', 'l34'] }, biceps2: { any: ['l31', 'l33'] },
      triceps: { any: ['l36', 'l37'] }, triceps2: { any: ['l38', 'l39'] }, calves: { any: ['l55', 'l56'] }, calves2: { any: ['l56', 'l55'] },
      core: { any: ['l58', 'l62'] }, core2: { any: ['l60', 'l63'] }, easy: { any: ['l292'] },
    },
    home: {
      kneeMain: { any: ['l48', 'l194'] }, kneeSec: { any: ['l46', 'l198', 'l196'] }, kneeIso: { any: [] },
      hingeMain: { any: ['l50', 'l211'] }, hingeSec: { any: ['l212', 'l220'] }, legcurl: { any: [] }, legcurl2: { any: [] },
      hpushMain: { any: ['l03', 'l08'] }, hpushSec: { any: ['l02', 'l082'] }, chestIso: { any: ['l070'] }, vpush: { any: ['l20', 'l127'] },
      hpull: { any: ['l095', 'l16'] }, hpull2: { any: ['l16', 'l17'] }, vpull: { new: ['l091'], any: ['l11', 'l091'] }, vpull2: { any: ['l091'] },
      side: { any: ['l22'] }, rear: { any: ['l24', 'l142'] }, biceps: { any: ['l30'] }, biceps2: { any: ['l31'] },
      triceps: { any: ['l39'] }, triceps2: { any: ['l176', 'l173'] }, calves: { any: ['l240', 'l241'] }, calves2: { any: ['l241', 'l240'] },
      core: { any: ['l62', 'l58'] }, core2: { any: ['l250', 'l63'] }, easy: { any: ['l292'] },
    },
    bodyweight: {
      kneeMain: { any: ['l206'] }, kneeSec: { any: ['l199', 'l200'] }, kneeIso: { any: [] },
      hingeMain: { any: ['l218'] }, hingeSec: { any: ['l212', 'l220', 'l219'] }, legcurl: { any: [] }, legcurl2: { any: [] },
      hpushMain: { new: ['l082'], any: ['l08'] }, hpushSec: { any: ['l083', 'l165'] }, chestIso: { any: [] }, vpush: { any: ['l145'] },
      hpull: { any: ['l103'] }, hpull2: { any: ['l103'] }, vpull: { any: ['l11', 'l12'] }, vpull2: { any: ['l12', 'l11'] },
      side: { any: [] }, rear: { any: ['l142'] }, biceps: { any: [] }, biceps2: { any: [] },
      triceps: { any: ['l165'] }, triceps2: { any: [] }, calves: { any: ['l241', 'l55'] }, calves2: { any: ['l55', 'l241'] },
      core: { any: ['l58', 'l62'] }, core2: { any: ['l250', 'l63'] }, easy: { any: ['l292'] },
    },
  };

  // the days: slots in order of importance, so a short session keeps the big lifts
  var DAYS = {
    full: ['Full body', 'Other', 'squat, press, row', ['kneeMain', 'hpushMain', 'hpull', 'hingeMain', 'vpull', 'vpush', 'side', 'core']],
    fullA: ['Full body A', 'Other', 'squat, press, row', ['kneeMain', 'hpushMain', 'hpull', 'hingeSec', 'side', 'triceps', 'calves', 'core']],
    fullB: ['Full body B', 'Other', 'legs, shoulders, pull-down', ['hingeMain', 'vpull', 'vpush', 'kneeSec', 'legcurl', 'biceps', 'rear', 'core2']],
    fullC: ['Full body C', 'Other', 'lunge, chest, row', ['kneeSec', 'hpushSec', 'hpull2', 'hingeMain', 'vpull2', 'side', 'triceps2', 'rear', 'core']],
    upperA: ['Upper A', 'Other', 'chest, back, shoulders', ['hpushMain', 'hpull', 'vpush', 'vpull', 'side', 'triceps', 'biceps', 'rear']],
    lowerA: ['Lower A', 'Legs', 'squat, hinge', ['kneeMain', 'hingeMain', 'legcurl', 'kneeIso', 'calves', 'core']],
    upperB: ['Upper B', 'Other', 'chest, back, arms', ['vpull2', 'hpushSec', 'hpull2', 'side', 'rear', 'biceps2', 'triceps2', 'chestIso']],
    lowerB: ['Lower B', 'Legs', 'legs, glutes', ['hingeSec', 'kneeSec', 'legcurl2', 'kneeIso', 'calves2', 'core2']],
    push: ['Push', 'Push', 'chest, shoulders, triceps', ['hpushMain', 'vpush', 'hpushSec', 'chestIso', 'side', 'triceps', 'triceps2']],
    pull: ['Pull', 'Pull', 'back, rear delts, biceps', ['vpull', 'hpull', 'hpull2', 'rear', 'biceps', 'core', 'calves']],
    legs: ['Legs', 'Legs', 'squat, hinge, calves', ['kneeMain', 'hingeMain', 'kneeSec', 'legcurl', 'kneeIso', 'calves', 'core2']],
    pushB: ['Push B', 'Push', 'shoulders, chest, triceps', ['vpush', 'hpushSec', 'hpushMain', 'chestIso', 'side', 'triceps2', 'triceps']],
    pullB: ['Pull B', 'Pull', 'back, rear delts, biceps', ['hpull2', 'vpull2', 'hpull', 'rear', 'biceps2', 'core2', 'calves2']],
    legsB: ['Legs B', 'Legs', 'hinge, lunge, calves', ['hingeMain', 'kneeSec', 'legcurl2', 'kneeIso', 'hingeSec', 'calves2', 'core']],
    easy: ['Easy day', 'Other', 'walk or cycle', ['easy']],
  };
  var SPLITS = {
    1: ['full'], 2: ['fullA', 'fullB'], 3: ['fullA', 'fullB', 'fullC'], 4: ['upperA', 'lowerA', 'upperB', 'lowerB'],
    5: ['upperA', 'lowerA', 'push', 'pull', 'legs'], 6: ['push', 'pull', 'legs', 'pushB', 'pullB', 'legsB'], 7: ['push', 'pull', 'legs', 'pushB', 'pullB', 'legsB', 'easy'],
  };
  var SUMMARY = {
    1: 'Full body, one day a week.', 2: 'Full body, {0} days a week.', 3: 'Full body, {0} days a week.', 4: 'Upper and lower body on alternating days, {0} days a week.',
    5: 'Upper and lower body, then push, pull and legs: {0} days a week.', 6: 'Push, pull and legs, twice: {0} days a week.', 7: 'Push, pull and legs twice, and an easy day: 7 days a week.',
  };
  var COUNT = { short: 4, medium: 6, long: 8 };
  var MAIN = /Main$/;

  var NICE = [3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50];
  function nice(v) { return NICE.reduce(function (a, b) { return Math.abs(b - v) < Math.abs(a - v) ? b : a; }); }
  function repsFor(l, role, slot, experience) {
    var lib = String(l.reps || '10');
    var side = (lib.match(/per (leg|arm|side)/) || [''])[0];
    var tail = side ? ' ' + side : '';
    if (/\d\s*(s|min)\b/.test(lib)) return lib.replace(/^(\d+)\s*s$/, function (_, x) { var n = Number(x); return Math.max(10, n - 10) + ' to ' + (n + 5) + ' s'; });
    if (/max/.test(lib)) return 'max';
    if (l.unit === 'bw' || /bodyweight|^none$|^bar$|^step$/i.test(String(l.equipment || ''))) {
      var n = Number((lib.match(/\d+/) || [10])[0]);
      return nice(n * 0.75) + ' to ' + nice(n * 1.5) + tail;
    }
    if (role === 'main') return (experience === 'years' ? '5 to 8' : experience === 'new' ? '8 to 10' : '6 to 10') + tail;
    if (role === 'compound') return '8 to 12' + tail;
    if (role === 'core') return '10 to 15' + tail;
    if (/^(calves|calves2|side)$/.test(slot)) return '12 to 20' + tail;
    return '10 to 15' + tail;
  }

  /* p:   { where: 'gym' | 'home' | 'bodyweight', days_per_week: 1-7, session_length: 'short' | 'medium' | 'long', experience: 'new' | 'some' | 'years' }
     env: { lib: Map id -> library exercise, fits(l, where), describe(l) -> { role } (plancheck.describe) }
     out: { summary, perWeek, days: [{ name, kind, focus, items: [{ ex, sets, reps, rest_s, role }] }] } */
  function build(p, env) {
    var where = SLOTS[p.where] ? p.where : 'gym';
    var n = Math.min(7, Math.max(1, Number(p.days_per_week) || 3));
    var exp = p.experience === 'new' || p.experience === 'years' ? p.experience : 'some';
    var len = COUNT[p.session_length] || COUNT.medium;
    var split = SPLITS[n];
    var slots = SLOTS[where];
    var pick = function (slot, used) {
      var s = slots[slot] || { any: [] };
      var list = (exp === 'new' && s['new'] ? s['new'] : []).concat(s.any || []);
      for (var i = 0; i < list.length; i += 1) {
        var l = env.lib.get(list[i]);
        if (l && !used[list[i]] && l.shoulder !== 'skip' && (!env.fits || env.fits(l, where))) return l;
      }
      return null;
    };
    var days = split.map(function (key) {
      var d = DAYS[key];
      var used = {}, items = [];
      d[3].forEach(function (slot) {
        if (items.length >= (key === 'easy' ? 1 : len)) return;
        var l = pick(slot, used);
        if (!l) return;
        used[l.id] = true;
        var kind = env.describe(l).role;
        if (kind === 'cardio') { items.push({ ex: l.id, sets: 1, reps: l.reps || '30 min', rest_s: 0, role: 'cardio' }); return; }
        var role = kind === 'compound' ? (MAIN.test(slot) && items.length < 2 ? 'main' : 'compound') : kind === 'core' ? 'core' : 'isolation';
        var sets = role === 'main' ? (exp === 'years' ? 4 : 3) : role === 'compound' ? 3 : role === 'core' ? 2 : (len <= 4 ? 2 : 3);
        if (n <= 2 && exp !== 'new' && role !== 'core') sets += 1; // two days a week carry the week's volume
        var rest = role === 'main' ? (exp === 'years' ? 180 : 150) : role === 'compound' ? 120 : role === 'core' ? 45 : 60;
        if (where === 'bodyweight') rest = role === 'main' || role === 'compound' ? 90 : 45;
        items.push({ ex: l.id, sets: sets, reps: repsFor(l, role, slot, exp), rest_s: rest, role: role });
      });
      var rank = { main: 0, compound: 1, isolation: 2, core: 3, cardio: 4 };
      items.sort(function (a, b) { return rank[a.role] - rank[b.role]; }); // heavy lifts first, isolation and core last
      // fit the session: fewer isolation sets first, then drop the last exercises (never the first two)
      var day = { name: d[0], kind: d[1], focus: d[2], items: items };
      if (env.minutes && key !== 'easy') {
        var limit = { short: 45, medium: 60, long: 90 }[p.session_length] || 60;
        var guard = 0;
        var group = function (x) { var pt = env.describe(env.lib.get(x.ex)).pattern; return pt === 'hpush' || pt === 'vpush' ? 'push' : pt === 'hpull' || pt === 'vpull' ? 'pull' : pt; };
        var needed = function (x) { var g = group(x); return /^(knee|hinge|push|pull)$/.test(g) && items.filter(function (o) { return group(o) === g; }).length === 1; };
        while (env.minutes(day) > limit && guard < 40) {
          guard += 1;
          var iso = items.filter(function (x) { return (x.role === 'isolation' || x.role === 'core') && x.sets > 2; }).pop();
          var drop = items.filter(function (x) { return !needed(x); }).pop();
          var cmp = items.filter(function (x) { return x.sets > 2; }).pop();
          var slow = items.filter(function (x) { return x.rest_s > 90; }).pop();
          if (iso) iso.sets -= 1;
          else if (drop && items.length > 3) items.splice(items.lastIndexOf(drop), 1);
          else if (cmp) cmp.sets -= 1;
          else if (slow) slow.rest_s = 90;
          else break;
        }
      }
      return day;
    });
    var plan = { summary: SUMMARY[n].replace('{0}', String(n)), perWeek: n, days: days };
    if (env.check) balance(plan, p, env);
    return plan;
  }

  // bring each muscle into its weekly range: take sets away where there are too many (isolation first), add sets where there are too few
  // and the day has time left. Glutes and core get plenty from the big lifts and are left alone.
  function balance(plan, p, env) {
    var limit = { short: 45, medium: 60, long: 90 }[p.session_length] || 60;
    var skip = { glutes: 1, core: 1, front_delts: 1 };
    var stuck = {};
    for (var guard = 0; guard < 80; guard += 1) {
      var r = env.check(plan);
      // first: no muscle above 10 sets in one session
      var cap = r.findings.filter(function (f) { return f.code === 'session_muscle'; })[0];
      if (cap) {
        var day0 = plan.days.filter(function (d) { return d.name === cap.args[0]; })[0];
        var key = String(cap.args[2]).replace(/ /g, '_');
        var hits = day0 ? day0.items.filter(function (it) { return (env.describe(env.lib.get(it.ex)).muscles[key] || 0) >= 1 && it.sets > 2; }) : [];
        hits.sort(function (a, b) { return (a.role === 'main') - (b.role === 'main') || (b.role === 'isolation') - (a.role === 'isolation'); });
        if (hits.length) { hits[0].sets -= 1; continue; }
        var drop0 = day0 ? day0.items.filter(function (it) { return it.role !== 'main' && (env.describe(env.lib.get(it.ex)).muscles[key] || 0) >= 1; }).pop() : null;
        if (drop0 && day0.items.length > 3) { day0.items.splice(day0.items.indexOf(drop0), 1); continue; }
      }
      // then: at least as much pulling as pressing
      if (r.findings.some(function (f) { return f.code === 'pull_push'; })) {
        var pushes = [];
        plan.days.forEach(function (d) { d.items.forEach(function (it) { var pt = env.describe(env.lib.get(it.ex)).pattern; if ((pt === 'hpush' || pt === 'vpush') && it.role !== 'main' && it.sets > 2) pushes.push(it); }); });
        if (pushes.length) { pushes.sort(function (a, b) { return b.sets - a.sets; })[0].sets -= 1; continue; }
      }
      var worst = null;
      Object.keys(r.weekly).forEach(function (m) {
        if (skip[m] || stuck[m]) return;
        var band = ['chest', 'back', 'quads', 'hamstrings'].indexOf(m) >= 0 ? r.bands.major : r.bands.small;
        var s = r.weekly[m].sets;
        var gap = s > band[1] * 1.1 ? s - band[1] : s < band[0] ? s - band[0] : 0;
        if (gap && (!worst || Math.abs(gap) > Math.abs(worst.gap))) worst = { m: m, gap: gap };
      });
      if (!worst) return;
      var cands = [];
      plan.days.forEach(function (d, di) {
        d.items.forEach(function (it) {
          var x = env.describe(env.lib.get(it.ex));
          if ((x.muscles[worst.m] || 0) >= 1 && it.role !== 'cardio') cands.push({ it: it, di: di, iso: it.role === 'isolation' || it.role === 'core', main: it.role === 'main' });
        });
      });
      var done = false;
      if (worst.gap > 0) {
        cands.sort(function (a, b) { return (b.iso - a.iso) || (a.main - b.main) || (b.it.sets - a.it.sets); });
        for (var i = 0; i < cands.length && !done; i += 1) if (cands[i].it.sets > (cands[i].main ? 3 : 2)) { cands[i].it.sets -= 1; done = true; } // a main lift keeps 3 sets
        // every set already at 2: leave out an isolation exercise for that muscle, or a second compound for it on a day that has another
        for (var k = 0; k < cands.length && !done; k += 1) {
          var c0 = cands[k], day = plan.days[c0.di];
          if (c0.main || day.items.length <= 3) continue;
          var others = day.items.filter(function (o) { return o !== c0.it && (env.describe(env.lib.get(o.ex)).muscles[worst.m] || 0) >= 1; });
          if (c0.iso || others.length) { day.items.splice(day.items.indexOf(c0.it), 1); done = true; }
        }
      } else {
        cands.sort(function (a, b) { return (b.iso - a.iso) || (a.it.sets - b.it.sets); });
        for (var j = 0; j < cands.length && !done; j += 1) {
          var c = cands[j];
          if (c.it.sets >= 4) continue;
          c.it.sets += 1;
          if (r.minutes[c.di] + 3 > limit || env.minutes(plan.days[c.di]) > limit) c.it.sets -= 1; else done = true;
        }
      }
      if (!done) stuck[worst.m] = true;
    }
  }

  var api = { build: build, SLOTS: SLOTS, DAYS: DAYS, SPLITS: SPLITS };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.YC_STARTER = api;
})(typeof window !== 'undefined' ? window : this);
