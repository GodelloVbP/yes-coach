// The sample workout: a small, believable plan and two earlier sessions, in the same documents the app stores.
// web.js loads them into memory when the page is opened with ?demo. Nothing here is ever written to a database.
(() => {
  'use strict';
  const iso = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  const daysAgo = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return d; };
  const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const dayName = (n) => WEEKDAYS[(daysAgo(-n).getDay() + 6) % 7]; // Mon..Sun, n days from today

  // id, library id, name, group, unit; reps and loads per session, newest first
  const EXERCISES = [
    ['barbell-bench-press', 'l04', 'Barbell bench press', 'Chest', 'kg', { reps: '8', last: [8, 8, 8], load: 80, before: [8, 8, 7], beforeLoad: 77.5 }],
    ['incline-dumbbell-press', 'l02', 'Incline dumbbell press', 'Chest', 'kg', { reps: '10', last: [10, 10, 9], load: 24, before: [10, 9, 9], beforeLoad: 24 }],
    ['lateral-raise', 'l22', 'Lateral raise', 'Shoulders', 'kg', { reps: '12', last: [12, 12, 12], load: 10, before: [12, 11, 10], beforeLoad: 10 }],
    ['tricep-rope-pushdown', 'l36', 'Tricep rope pushdown', 'Triceps', 'stack', { reps: '10', last: [10, 10, 10], load: 35, before: [10, 10, 9], beforeLoad: 32 }],
  ];

  const session = (daysBack, which) => {
    const date = iso(daysAgo(daysBack));
    const start = daysAgo(daysBack); start.setHours(18, 0, 0, 0);
    const sets = {};
    let order = 0;
    EXERCISES.forEach(([id, , , , , p]) => {
      (which === 'last' ? p.last : p.before).forEach((reps, i) => {
        order += 1;
        const at = start.getTime() + order * 150000;
        sets[id + '_' + (i + 1)] = { ex: id, n: i + 1, order, kind: 'work', reps, load: which === 'last' ? p.load : p.beforeLoad, done: true, at, ticked_at: at };
      });
    });
    return ['yc/sessions/' + date, { date, source: 'live', template: 'push', split: 'Chest', label: 'Push day', note: null, started_at: start.getTime(), finished_at: start.getTime() + order * 150000, updated_at: start.getTime(), sets }];
  };

  window.YC_DEMO_DOCS = () => {
    // three training days a week, today one of them
    const days = [dayName(0), dayName(2), dayName(4)].sort((a, b) => WEEKDAYS.indexOf(a) - WEEKDAYS.indexOf(b));
    const docs = [['yc', { app: 'yes-coach', schema: 1, created_at: Date.now(), intro_seen: true, schedule: { enabled: true, mode: 'rotation', days, rotation: ['push'] } }]];
    EXERCISES.forEach(([id, lib, name, group, unit]) => {
      docs.push(['yc/exercises/' + id, { name, group, category: 'strength', unit, better: 'higher', per_side: false, rest_s: unit === 'stack' ? 75 : 90, shoulder: null, library_id: lib }]);
    });
    docs.push(['yc/templates/push', {
      name: 'Push day', order: 1, kind: 'Push', focus: 'Chest, shoulders and triceps',
      items: EXERCISES.map(([id, , , , , p], i) => ({ ex: id, order: i + 1, sets: 3, reps: p.reps, target: '', target_at: iso(daysAgo(14)), rest_s: 90, note: null })),
    }]);
    docs.push(session(3, 'last'), session(10, 'before'));
    return docs;
  };
})();
