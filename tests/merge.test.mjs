// The deep merges in web.js and src/yes-coach.html must never write to Object.prototype.
// Run: node tests/merge.test.mjs
import fs from 'node:fs';
import assert from 'node:assert/strict';
const grab = (file, name) => {
  const s = fs.readFileSync(new URL('../' + file, import.meta.url), 'utf8');
  const i = s.indexOf('const ' + name + ' = (a, b) => {');
  assert.ok(i >= 0, name + ' not found in ' + file);
  const j = s.indexOf('\n  };', i) + 5;
  return new Function(s.slice(i, j) + '; return ' + name + ';')();
};
let n = 0;
for (const [file, name] of [['web.js', 'merge'], ['src/yes-coach.html', 'deepMerge']]) {
  const merge = grab(file, name);
  for (const evil of ['{"__proto__":{"polluted":"yes"}}', '{"a":{"__proto__":{"polluted":"yes"}}}', '{"constructor":{"prototype":{"polluted":"yes"}}}']) {
    merge({ a: {} }, JSON.parse(evil));
    assert.equal({}.polluted, undefined, file + ' polluted by ' + evil); n += 1;
  }
  const r = merge({ a: { x: 1 }, b: 2 }, { a: { y: 2 }, c: [1] });
  assert.deepEqual(r, { a: { x: 1, y: 2 }, b: 2, c: [1] }); n += 1; // normal merging still works
}
console.log(n + ' checks passed');
