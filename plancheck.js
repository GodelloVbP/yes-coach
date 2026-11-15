// Plan check: is a training plan a good one? Sets per muscle per week, sessions per muscle, the time a day takes, the movements
// covered, and plain findings. Pure: no page, no storage. The app loads it as window.YC_PLANCHECK; the connector carries a copy
// (supabase/functions/mcp/index.ts, between the PLANCHECK markers), kept the same by tools/sync_plancheck.py and tests/plancheck.test.mjs.
// The rules and numbers are in PLAN_MAKER.md.
(function (root) {
  'use strict';

  var MUSCLES = ['chest', 'back', 'front_delts', 'side_delts', 'rear_delts', 'biceps', 'triceps', 'quads', 'hamstrings', 'glutes', 'calves', 'core'];
  var MAJOR = ['chest', 'back', 'quads', 'hamstrings', 'glutes'];
  var SMALL = ['side_delts', 'rear_delts', 'biceps', 'triceps', 'calves'];
  var MUSCLE_NAME = { chest: 'Chest', back: 'Back', front_delts: 'Front delts', side_delts: 'Side delts', rear_delts: 'Rear delts', biceps: 'Biceps', triceps: 'Triceps', quads: 'Quads', hamstrings: 'Hamstrings', glutes: 'Glutes', calves: 'Calves', core: 'Core' };

  // the library's muscle words (free text) to fixed muscles; words not here (grip, lower back, hip flexors, heart and lungs) are not counted
  var TAGS = [
    [/^(upper |lower |inner )?chest$/, { chest: 1 }],
    [/^(lats|mid back|upper back|back|lower traps)$/, { back: 1 }],
    [/^front and side delts$/, { front_delts: 1, side_delts: 0.5 }],
    [/^front delts$/, { front_delts: 1 }],
    [/^side delts$/, { side_delts: 1 }],
    [/^rear delts$/, { rear_delts: 1 }],
    [/^shoulders$/, { front_delts: 0.5, side_delts: 0.5 }],
    [/^(biceps|brachialis|brachioradialis)\b/, { biceps: 1 }],
    [/^triceps\b/, { triceps: 1 }],
    [/^quads$/, { quads: 1 }],
    [/^hamstrings$/, { hamstrings: 1 }],
    [/^(glutes|glute max|glute medius|hip abductors)\b/, { glutes: 1 }],
    [/^(calves|soleus)$/, { calves: 1 }],
    [/^(abs|lower abs|obliques|deep core|core)$/, { core: 1 }],
    [/^legs$/, { quads: 0.5, hamstrings: 0.5, glutes: 0.5 }],
    [/^arms$/, { biceps: 0.5, triceps: 0.5 }],
  ];
  // an exercise of your own, with nothing but its body part
  var GROUP_MUSCLES = {
    chest: { chest: 1, triceps: 0.5, front_delts: 0.5 }, back: { back: 1, biceps: 0.5 }, shoulders: { front_delts: 0.5, side_delts: 0.5 },
    arms: { biceps: 0.5, triceps: 0.5 }, biceps: { biceps: 1 }, triceps: { triceps: 1 }, legs: { quads: 0.5, hamstrings: 0.5, glutes: 0.5 },
    quads: { quads: 1, glutes: 0.5 }, 'hamstrings and glutes': { hamstrings: 1, glutes: 1 }, calves: { calves: 1 }, core: { core: 1 },
  };

  // an exercise of your own, from its name (before its body part)
  var NAME_MUSCLES = [
    [/calf|calves/, { calves: 1 }],
    [/leg curl|hamstring curl|nordic/, { hamstrings: 1 }],
    [/leg extension/, { quads: 1 }],
    [/abduct/, { glutes: 1 }],
    [/lateral raise|side raise|lat raise/, { side_delts: 1 }],
    [/face pull|rear delt|reverse fly|reverse pec/, { rear_delts: 1 }],
    [/tricep|pushdown|push-down|skull|kickback|french press/, { triceps: 1 }],
    [/curl/, { biceps: 1 }],
    [/crunch|plank|sit-?up|leg raise|ab wheel|rollout|dead ?bug|pallof/, { core: 1 }],
    [/fly|flye|pec deck|crossover/, { chest: 1, front_delts: 0.5 }],
    [/shrug/, {}],
  ];
  // "Hip abductors (glute medius, glute minimus), core" is two words, not three
  function splitTags(text) {
    var out = [], depth = 0, cur = '';
    String(text || '').split('').forEach(function (ch) {
      if (ch === '(') depth += 1;
      if (ch === ')') depth = Math.max(0, depth - 1);
      if (ch === ',' && depth === 0) { out.push(cur); cur = ''; } else cur += ch;
    });
    out.push(cur);
    return out.map(function (t) { return t.trim().toLowerCase(); }).filter(function (t) { return t && t !== 'none'; });
  }
  function tagMuscles(tag) {
    for (var i = 0; i < TAGS.length; i += 1) if (TAGS[i][0].test(tag)) return TAGS[i][1];
    return null;
  }
  // per muscle the share of one set it gets: primary 1, secondary half; a muscle is credited once per exercise (its largest share)
  function musclesOf(entry) {
    var out = {};
    var add = function (map, k) { Object.keys(map).forEach(function (m) { out[m] = Math.max(out[m] || 0, map[m] * k); }); };
    splitTags(entry && entry.primary).forEach(function (t) { var m = tagMuscles(t); if (m) add(m, 1); });
    splitTags(entry && entry.secondary).forEach(function (t) { var m = tagMuscles(t); if (m) add(m, 0.5); });
    return out;
  }

  // the movement, from the name (works for your own exercises too)
  var PATTERNS = [
    ['legcurl', /leg curl|hamstring curl|nordic|ball curl|glute[- ]ham/],
    ['vpull', /pull-?ups?\b|chin-?ups?\b|pull-?down|lat pull/],
    ['hpull', /\brows?\b|t-bar/],
    ['vpush', /overhead press|shoulder press|military press|arnold press|push press|pike push|handstand push|landmine press/],
    ['hpush', /bench press|chest press|push-?ups?\b|press-?ups?\b|\bdips?\b|floor press|dumbbell press|incline press|decline press|svend/],
    ['hinge', /deadlift|\brdl\b|good morning|hip thrust|glute bridge|back extension|hyperextension|kettlebell swing|pull-through|hip hinge/],
    ['knee', /squat|leg press|lunge|step-?ups?\b|hack|pistol|belt squat/],
  ];
  var COMPOUND = { knee: 1, hinge: 1, hpush: 1, vpush: 1, hpull: 1, vpull: 1 };
  var CARDIO = /\b(run|running|walk|walking|jog|bike|cycling|cycle|rower|rowing machine|elliptical|cardio|treadmill|jump rope|stairs|swim|hike|hiking|rucking)\b/;
  var WARMUP_NAME = /warm-?up|mobility|stretch|rotation|cat-cow|foam roll|activation|dislocat/;
  function patternOf(name) {
    var n = String(name || '').toLowerCase();
    if (/upright row|reverse nordic/.test(n)) return '';
    for (var i = 0; i < PATTERNS.length; i += 1) if (PATTERNS[i][1].test(n)) return PATTERNS[i][0];
    return '';
  }

  // everything the check needs about one exercise. ex: { name, group, category, unit, primary, secondary, shoulder, library }
  // the muscles of a compound lift of your own, from its movement
  var PATTERN_MUSCLES = {
    knee: { quads: 1, glutes: 0.5 }, hinge: { hamstrings: 1, glutes: 1 }, hpush: { chest: 1, triceps: 0.5, front_delts: 0.5 },
    vpush: { front_delts: 1, side_delts: 0.5, triceps: 0.5 }, hpull: { back: 1, biceps: 0.5, rear_delts: 0.5 }, vpull: { back: 1, biceps: 0.5 },
  };
  function describe(ex) {
    if (!ex) return { name: '', pattern: '', role: 'isolation', muscles: {}, estimated: false, unknown: true, shoulder: '', unit: 'kg', warmupName: false };
    var name = String(ex.name || '');
    var low = name.toLowerCase();
    var pattern = patternOf(name);
    var muscles, estimated = false;
    if (ex.primary) muscles = musclesOf(ex); // a library exercise: its own muscles, also when none of them is counted (shrugs, grip)
    else {
      estimated = true;
      var byName = null;
      for (var i = 0; i < NAME_MUSCLES.length && !byName; i += 1) if (NAME_MUSCLES[i][0].test(low)) byName = NAME_MUSCLES[i][1];
      muscles = byName || PATTERN_MUSCLES[pattern] || GROUP_MUSCLES[String(ex.group || '').toLowerCase()] || {};
    }
    // squats, leg presses and lunges barely train the hamstrings (they stay about the same length): no credit for them
    if (pattern === 'knee' && muscles.hamstrings && muscles.hamstrings < 1) { muscles = Object.assign({}, muscles); delete muscles.hamstrings; }
    var cardio = ex.category === 'cardio' || ex.unit === 'min' || (CARDIO.test(low) && !pattern);
    var role = cardio ? 'cardio' : COMPOUND[pattern] ? 'compound' : (muscles.core && Object.keys(muscles).length === 1) ? 'core' : 'isolation';
    return { name: name, pattern: pattern, role: role, muscles: cardio ? {} : muscles, estimated: estimated && !cardio && Object.keys(muscles).length > 0,
      unknown: false, shoulder: ex.shoulder || '', unit: ex.unit || 'kg', warmupName: WARMUP_NAME.test(low) };
  }

  // reps text: a range, a fixed number, max, or a time; per arm or leg doubles the work
  function repsInfo(text) {
    var t = String(text == null ? '' : text).toLowerCase();
    var timed = /\d\s*(s|sec|secs|seconds|min|mins|minutes)\b/.test(t);
    return { range: /\d+(\.\d+)?\s*(-|–|—|to)\s*\d+/.test(t), max: /max|amrap/.test(t), timed: timed, perSide: /per (arm|leg|side)|each (arm|leg|side)|per kant|per been|per arm/.test(t),
      minutes: (t.match(/(\d+(\.\d+)?)\s*(min|mins|minutes)\b/) || [])[1] ? Number(t.match(/(\d+(\.\d+)?)\s*(min|mins|minutes)\b/)[1]) : null };
  }

  var BANDS = { 'new': { major: [6, 10], small: [3, 8] }, some: { major: [10, 16], small: [6, 10] }, years: { major: [12, 20], small: [8, 14] } };
  function bandsFor(experience, goal) {
    var b = BANDS[experience] || BANDS.some;
    var low = goal === 'lose' ? 2 : 0; // losing weight: the low end is lower, the top stays
    return { major: [Math.max(2, b.major[0] - low), b.major[1]], small: [Math.max(2, b.small[0] - low), b.small[1]] };
  }
  var LENGTH_MIN = { short: 45, medium: 60, long: 90 };
  var MUST = [['knee', 'squat or leg press'], ['hinge', 'hinge (deadlift, hip thrust or back extension)'], ['push', 'press for chest or shoulders'], ['pull', 'row, pull-up or pulldown']];
  var NOTE_NUMBERS = /hold\b.{0,40}?\buntil|\d+(\.\d+)?\s*(kg|lbs?|pin)\b|\b\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b|\d{4}-\d{2}-\d{2}|@\s*\d|\d+\s*[x×]\s*\d+\s*(@|at)\s*\d/i;

  var r1 = function (x) { return Math.round(x * 10) / 10; };
  var fill = function (tpl, args) { return tpl.replace(/\{(\d)\}/g, function (_, i) { return args[Number(i)]; }); };
  var T = {
    unknown: '{0} is not an exercise in the list.',
    over_time: '{0} takes about {1} minutes, more than the {2} you have.',
    missing: 'No {0} in the week.',
    shoulder_skip: '{0} is hard on the shoulders.',
    freq: 'Trained less than twice a week: {0}. Twice works better.',
    attendance: 'You train about {0} times a week and the plan is set for {1}, so each day comes round less often than planned. Fewer, fuller days fit better.',
    vol_low: '{0}: {1} hard sets a week, the range for you is {2} to {3}.',
    vol_low_time: '{0}: {1} hard sets a week, below {2} to {3}, but your sessions are full.',
    vol_high: '{0}: {1} hard sets a week, above {2}. More sets add less from here.',
    session_muscle: '{0}: {1} hard sets for {2} in one session, more than 10.',
    pull_push: 'More pressing ({0} sets) than pulling ({1} sets) a week.',
    order: '{0}: {1} comes before a heavier lift.',
    consecutive: '{0} and {1} come one after the other and both load {2}.',
    fixed_reps: 'A fixed number of reps: {0}. A range such as 8 to 12 lets the weight go up in smaller steps.',
    note_numbers: 'Notes with numbers or dates that go out of date: {0}.',
    warmup_unmarked: '{0} looks like a warm-up but counts as working sets.',
    estimated: 'Counted from the name or body part: {0}.',
    extras: 'Not in the week, if there is room: {0}.',
  };
  var EXTRA_WORD = { vpush: 'an overhead press', legcurl: 'a leg curl', vpull: 'a pull-up or pulldown', hpull: 'a row' };

  /* plan: { days: [{ name, items: [{ ex, sets, reps, rest_s, kind, group, note }] }], perWeek }
     ctx:  { lookup(exId) -> exercise fields (see describe), experience: 'new' | 'some' | 'years', goal, length: 'short' | 'medium' | 'long' or minutes,
             shoulder: true when the person has a shoulder limit, legacy: true for a plan saved before rep ranges were the rule,
             tracked(exId) -> true for an exercise they log with a weight and build up (never called a warm-up),
             actualPerWeek: sessions a week they log (left out when there is too little to tell) }
     plan.days[i].perWeek: how often that day comes round in a week, when not every day comes round equally (a rotation with repeats);
     plan.order: the order the days come in, as indexes into plan.days, for the check on two heavy days in a row
     out:  { weekly: { muscle: { sets, sessions } }, minutes: [per day], findings: [{ level, code, args, text }], bands, perWeek } */
  function check(plan, ctx) {
    ctx = ctx || {};
    var kept = [];
    var days = (plan && plan.days || []).filter(function (d, i) { var ok = d && (d.items || []).length; if (ok) kept.push(i); return ok; });
    var perWeek = Math.max(1, Number(plan && plan.perWeek) || days.length || 1);
    var f = days.length ? perWeek / days.length : 0; // how often each day comes round in a week, unless the day says (d.perWeek: a rotation with repeats)
    var bands = bandsFor(ctx.experience, ctx.goal);
    var minutesAllowed = typeof ctx.length === 'number' ? ctx.length : LENGTH_MIN[ctx.length] || 60;
    var findings = [];
    var add = function (level, code, args) { findings.push({ level: level, code: code, args: args, text: fill(T[code], args) }); };
    var weekly = {};
    MUSCLES.forEach(function (m) { weekly[m] = { sets: 0, sessions: 0 }; });
    var seen = {}, estimated = [], fixed = [], noted = [], pushSets = 0, pullSets = 0, minutes = [], daySets = [];
    var lookup = function (id) { return describe(ctx.lookup ? ctx.lookup(id) : null); };

    days.forEach(function (d) {
      var perMuscle = {}, mainSets = {}, compoundSets = {}, total = 0, firstCompound = {}, sawCompound = false, orderFlag = null;
      var fd = d.perWeek != null && isFinite(Number(d.perWeek)) ? Number(d.perWeek) : f;
      var sec = 5 * 60; // getting started
      var items = d.items;
      for (var i = 0; i < items.length; i += 1) {
        var it = items[i] || {};
        var x = lookup(it.ex);
        var sets = Math.max(0, Number(it.sets) || 0);
        var rp = repsInfo(it.reps);
        var rest = it.rest_s == null ? 90 : Number(it.rest_s) || 0;
        var nextSame = it.group && items[i + 1] && items[i + 1].group === it.group;
        var warm = it.kind === 'warmup';
        if (x.unknown && !warm) add('error', 'unknown', [it.ex]);
        // time: the work, the rest (once per round in a superset), ramp-up sets for the first heavy lift of a muscle, a minute to change over
        if (warm || x.role === 'cardio') sec += (rp.minutes ? rp.minutes * 60 : 60) * Math.max(1, sets);
        else {
          sec += sets * (rp.perSide ? 80 : 40) + (nextSame ? 0 : sets * rest) + 60;
          if (x.role === 'compound' && x.unit === 'kg') {
            var main = Object.keys(x.muscles).filter(function (m) { return x.muscles[m] >= 1; })[0] || x.pattern;
            sec += firstCompound[main] ? 90 : 180;
            firstCompound[main] = true;
          }
        }
        if (warm) continue;
        var strengthAfter = items.slice(i + 1).some(function (o) { return o && o.kind !== 'warmup' && lookup(o.ex).role !== 'cardio'; });
        // a drill they log with a weight and build up (shoulder rehab) is theirs to track: not called a warm-up, not counted as muscle work
        if (x.warmupName && ctx.tracked && ctx.tracked(it.ex)) continue;
        if (x.warmupName || (x.role === 'cardio' && i === 0 && strengthAfter)) { add('warn', 'warmup_unmarked', [x.name || it.ex]); continue; } // a drill is not a working set: flagged, not counted
        if (x.role === 'cardio') continue;
        if (x.estimated && estimated.indexOf(x.name) < 0) estimated.push(x.name);
        if (x.shoulder === 'skip' && ctx.shoulder) add('error', 'shoulder_skip', [x.name]);
        if (it.note && NOTE_NUMBERS.test(String(it.note)) && noted.indexOf(x.name) < 0) noted.push(x.name);
        if (!rp.range && !rp.max && !rp.timed && x.unit !== 'bw' && x.unit !== 'min' && x.role !== 'core' && fixed.indexOf(x.name) < 0) fixed.push(x.name);
        if (x.role === 'compound') { if (orderFlag && !sawCompound) orderFlag.after = true; sawCompound = true; }
        else if (x.role === 'isolation' && !sawCompound && !orderFlag) orderFlag = { name: x.name, after: false };
        if (x.pattern) seen[x.pattern] = true;
        if (x.pattern === 'hpush' || x.pattern === 'vpush') pushSets += sets * fd;
        if (x.pattern === 'hpull' || x.pattern === 'vpull' || (x.muscles.rear_delts || 0) >= 1) pullSets += sets * fd; // rear-delt work (face pulls) counts as pulling
        Object.keys(x.muscles).forEach(function (m) {
          perMuscle[m] = (perMuscle[m] || 0) + sets * x.muscles[m];
          if (x.muscles[m] >= 1) mainSets[m] = (mainSets[m] || 0) + sets;
          if (x.role === 'compound' && x.muscles[m] >= 1) compoundSets[m] = (compoundSets[m] || 0) + sets;
        });
        total += sets;
      }
      if (orderFlag && orderFlag.after) add('warn', 'order', [d.name, orderFlag.name]);
      Object.keys(perMuscle).forEach(function (m) {
        weekly[m].sets += perMuscle[m] * fd;
        if (perMuscle[m] >= 2) weekly[m].sessions += fd;
      });
      Object.keys(mainSets).forEach(function (m) { if (mainSets[m] > 10 && MUSCLE_NAME[m] && m !== 'glutes') add('warn', 'session_muscle', [d.name, mainSets[m], MUSCLE_NAME[m].toLowerCase()]); });
      minutes.push(Math.round(sec / 60));
      daySets.push(compoundSets);
      if (sec / 60 > minutesAllowed * 1.2) add('error', 'over_time', [d.name, Math.round(sec / 60), minutesAllowed]);
    });

    // the week must have these; the rest is filled in when there is room
    MUST.forEach(function (m) {
      var has = m[0] === 'push' ? seen.hpush || seen.vpush : m[0] === 'pull' ? seen.hpull || seen.vpull : seen[m[0]];
      if (days.length && !has) add('error', 'missing', [m[1]]);
    });
    var full = minutes.length && minutes.every(function (x) { return x >= minutesAllowed * 0.8; });
    var once = [];
    MAJOR.forEach(function (m) { if (perWeek >= 3 && days.length >= 2 && weekly[m].sets > 0 && weekly[m].sessions < 1.5) once.push(MUSCLE_NAME[m]); });
    if (once.length) add('warn', 'freq', [once.join(', ')]);
    MAJOR.concat(SMALL).forEach(function (m) {
      var b = MAJOR.indexOf(m) >= 0 ? bands.major : bands.small;
      var s = r1(weekly[m].sets);
      if (s < b[0]) add(full ? 'info' : 'warn', full ? 'vol_low_time' : 'vol_low', [MUSCLE_NAME[m], s, b[0], b[1]]);
      else if (s > b[1] * 1.25 && m !== 'glutes') add('info', 'vol_high', [MUSCLE_NAME[m], s, b[1]]); // more keeps helping a little; recovery, not growth, is the limit // glutes get counted in full from every squat and hinge
    });
    if (pushSets > pullSets * 1.1 + 1) add('warn', 'pull_push', [r1(pushSets), r1(pullSets)]);
    // what they log against what the plan is set for (ctx.actualPerWeek: sessions a week over the last weeks)
    var actual = Number(ctx.actualPerWeek);
    if (ctx.actualPerWeek != null && isFinite(actual) && actual < perWeek * 0.7) add('warn', 'attendance', [r1(actual), perWeek]);
    // the same muscles heavy on two days that follow each other in the order of the days (plan.order: a rotation with repeats, as day indexes)
    var given = Array.isArray(plan && plan.order) ? plan.order.map(function (i) { return kept.indexOf(i); }).filter(function (i) { return i >= 0; }) : [];
    var ord = given.length >= 2 ? given : days.map(function (_, i) { return i; });
    var pairsSeen = {};
    if (days.length >= 2 && perWeek >= 4) for (var k = 0; k < ord.length; k += 1) {
      if (k === ord.length - 1 && ord.length === 2) break;
      var ia = ord[k], ib = ord[(k + 1) % ord.length];
      if (ia === ib || pairsSeen[ia + '>' + ib]) continue;
      pairsSeen[ia + '>' + ib] = true;
      var a = daySets[ia], b2 = daySets[ib];
      var both = MAJOR.filter(function (m) { return (a[m] || 0) >= 3 && (b2[m] || 0) >= 3; });
      if (both.length) add('warn', 'consecutive', [days[ia].name, days[ib].name, both.map(function (m) { return MUSCLE_NAME[m].toLowerCase(); }).join(', ')]);
    }
    var extras = ['vpush', 'legcurl', 'vpull', 'hpull'].filter(function (p) { return !seen[p] && !(ctx.shoulder && p === 'vpush'); }).map(function (p) { return EXTRA_WORD[p]; });
    if (extras.length && !full) add('info', 'extras', [extras.join(', ')]);
    var few = function (list) { return list.slice(0, 3).join(', ') + (list.length > 3 ? ' and ' + (list.length - 3) + ' more' : ''); };
    if (fixed.length) add(ctx.legacy ? 'info' : 'warn', 'fixed_reps', [few(fixed)]);
    if (noted.length) add('warn', 'note_numbers', [noted.join(', ')]); // every name: a fix request may change only what it names
    if (estimated.length) add('info', 'estimated', [few(estimated)]);

    var rank = { error: 0, warn: 1, info: 2 };
    findings.sort(function (x, y) { return rank[x.level] - rank[y.level]; });
    var out = {};
    MUSCLES.forEach(function (m) { out[m] = { sets: r1(weekly[m].sets), sessions: r1(weekly[m].sessions) }; });
    return { weekly: out, minutes: minutes, findings: findings, bands: bands, perWeek: perWeek, minutesAllowed: minutesAllowed };
  }

  var api = { check: check, describe: describe, musclesOf: musclesOf, patternOf: patternOf, splitTags: splitTags, bandsFor: bandsFor, repsInfo: repsInfo, MUSCLES: MUSCLES, MAJOR: MAJOR, SMALL: SMALL, MUSCLE_NAME: MUSCLE_NAME, TEXT: T };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.YC_PLANCHECK = api;
})(typeof window !== 'undefined' ? window : this);
