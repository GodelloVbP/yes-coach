// The starter plans the app builds without an AI: every exercise exists, fits the place, and is not one marked hard on shoulders.
import { readFileSync } from 'node:fs';
const src = readFileSync(new URL('../src/yes-coach.html', import.meta.url), 'utf8');
const LIB = JSON.parse(src.match(/const LIB = (\[.*?\]);\n/)[1]);
const BY = new Map(LIB.map((l) => [l.id, l]));
const STARTER = eval('(' + src.match(/const STARTER = (\{[\s\S]*?\n {2}\});/)[1] + ')');
const NEW = eval('(' + src.match(/const STARTER_NEW = (\{.*?\});/)[1] + ')');
const kit = (name) => new RegExp(src.match(new RegExp(name + ': (/\\^.*?\\$/),'))[1].slice(1, -1));
const PLACE = { home: kit('home'), bodyweight: kit('bodyweight') };
const fits = (l, where) => !PLACE[where] || String(l.equipment).toLowerCase().split(/ or /).some((a) => a.split(/,\s*/).every((p) => PLACE[where].test(p.trim())));
let n = 0;
const ok = (c, m) => { n += 1; if (!c) { console.error('FAIL', m); process.exit(1); } };
for (const [where, splits] of Object.entries(STARTER)) {
  ok(splits.full && splits.full.length >= 2, where + ': has full-body days');
  for (const [split, days] of Object.entries(splits)) {
    for (const [name, kind, focus, ids] of days) {
      ok(ids.length >= 5 && new Set(ids).size === ids.length, `${where} ${name}: 5 or more different exercises`);
      ok(['Push', 'Pull', 'Legs', 'Other'].includes(kind) && focus, `${where} ${name}: kind and focus`);
      for (const id of ids) {
        const l = BY.get(id);
        ok(l, `${where} ${split} ${name}: ${id} exists`);
        ok(l.shoulder !== 'skip', `${where} ${name}: ${id} is not hard on shoulders`);
        ok(fits(l, where), `${where} ${name}: ${l.name} (${l.equipment}) fits ${where}`);
      }
    }
  }
}
for (const [a, b] of Object.entries(NEW)) ok(BY.has(a) && BY.has(b) && BY.get(a).group === BY.get(b).group, `beginner swap ${a} -> ${b} keeps the muscle group`);
console.log(n + ' starter checks passed');
