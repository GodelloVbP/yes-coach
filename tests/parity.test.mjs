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
console.log(n, 'parity checks passed');
