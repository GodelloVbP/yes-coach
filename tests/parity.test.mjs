// The app and the connector each carry their own copy of the food ranking (one is a page, the other an Edge Function pasted into Supabase, so they cannot import
// from one place). This keeps the copies from drifting: the tables and the portion ranking must say the same thing in both.
import fs from 'node:fs';
const app = fs.readFileSync(new URL('../src/yes-coach.html', import.meta.url), 'utf8');
const fn = fs.readFileSync(new URL('../supabase/functions/mcp/index.ts', import.meta.url), 'utf8');
let n = 0;
const same = (what, a, b) => { n++; if (a == null || b == null || a.length === 0 || JSON.stringify(a) !== JSON.stringify(b)) { console.error('FAIL', what, '\n app:', JSON.stringify(a), '\n fn: ', JSON.stringify(b)); process.exit(1); } };
const literal = (src, head) => { // the [...] or {...} that follows `head`, balanced
  const i = src.indexOf(head); if (i < 0) return null;
  let j = src.indexOf('=', i) + 1; while (/\s/.test(src[j])) j++;
  const open = src[j], close = open === '[' ? ']' : '}'; let d = 0, k = j;
  for (; k < src.length; k++) { if (src[k] === open) d++; else if (src[k] === close && --d === 0) break; }
  return src.slice(j, k + 1).replace(/\s+/g, ' ');
};
const body = (src, head) => { // the function that follows `head`, up to the closing brace at its own indent
  const i = src.indexOf(head); if (i < 0) return null;
  const j = src.indexOf('{', src.indexOf('=>', i)); let d = 0, k = j;
  for (; k < src.length; k++) { if (src[k] === '{') d++; else if (src[k] === '}' && --d === 0) break; }
  return src.slice(j, k + 1);
};
const parts = (b) => b && [...b.matchAll(/\/(?![*/])((?:[^/\n\\]|\\.)+)\/[a-z]*|return (\d+)|\[('[^\]]*)\]/g)].map((m) => m[0]); // regexes, returned scores, type lists

same('processed words', literal(app, 'const PROCESSED ='), literal(fn, 'const PROCESSED ='));
same('rough sizes by kind of food', literal(app, 'const PORTIONS ='), literal(fn, 'const SIZES: Record<string, number[]> ='));
same('portion ranking', parts(body(app, 'const measureScore =')), parts(body(fn, 'const measureScore =')));
const split = (src) => (src.match(/const wordsOf = .*/) || [''])[0].replace(/foldW|fold/g, 'F').replace(/\(t[^)]*\)[^=]*=>/, '(t) =>');
same('word splitting', split(app), split(fn));
// weight steps: the connector knows the kind of equipment of a library exercise from three lists of ids; they follow the app's library
{
  const i = app.indexOf('const LIB = [') + 'const LIB = '.length;
  let d = 0, k = i; for (; k < app.length; k++) { if (app[k] === '[') d++; else if (app[k] === ']' && --d === 0) break; }
  const lib = JSON.parse(app.slice(i, k + 1));
  const ids = (re) => lib.filter((l) => re.test(l.equipment || '')).map((l) => l.id);
  const inFn = (name) => { const m = fn.match(new RegExp('const ' + name + " = new Set\\('([^']*)'")); return m ? m[1].split(' ') : null; };
  same('dumbbell exercises', ids(/dumbbell|kettlebell/i), inFn('LIB_DUMBBELL'));
  same('cable exercises', ids(/cable/i), inFn('LIB_CABLE'));
  same('barbell exercises', ids(/barbell|ez-bar|trap bar|safety squat/i), inFn('LIB_BARBELL'));
  const prog = fs.readFileSync(new URL('../progression.js', import.meta.url), 'utf8');
  for (const re of ['/dumbbell|kettlebell/i', '/cable/i', '/barbell|ez-bar|trap bar|safety squat/i']) { n++; if (!prog.includes(re) || !fn.includes(re)) { console.error('FAIL the equipment words differ:', re); process.exit(1); } }
}
console.log(n, 'parity checks passed');
