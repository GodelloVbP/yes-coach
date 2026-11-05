import fs from 'fs';
import * as acorn from 'acorn';
import * as walk from 'acorn-walk';
import { fileURLToPath } from 'url';
const root = fileURLToPath(new URL('../../', import.meta.url));
const out = { plain: new Set(), tpl: new Set(), lib: new Set() };
const appSrc = fs.readFileSync(root + 'src/yes-coach.html', 'utf8');
const cssText = [...appSrc.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join('\n').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\{[^}]*\}/g, '{}');
const CLS = new Set([...cssText.matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]));
const isClassList = (t) => t.trim().split(/\s+/).every((w) => CLS.has(w) || /^[a-z]+-[\w-]+$/.test(w));
const norm = (t) => t.replace(/\s+/g, ' ').trim();
const addPlain = (t) => { t = norm(t); if ((t.length > 3 || (t.length >= 2 && /^[A-Z][a-z]+$/.test(t))) && t.length <= 300 && !isClassList(t)) out.plain.add(t); };
const addTpl = (t) => { t = norm(t); if (t.replace(/\{\d+\}/g, '').trim().length >= 2 && !isClassList(t.replace(/\{\d+\}/g, 'x'))) out.tpl.add(t); };
const looksUI = (s) => {
  if (!/[A-Za-z]{3,}/.test(s)) return false;
  if (s.length > 600) return false;
  if (/^[a-z][a-z0-9-]*$/.test(s)) return false;           // css class / id / key
  if (/^[#.\[]|[{}<>]|=>|\bfunction\b|^https?:|\.(js|png|json|css|html)\b/.test(s)) return false;
  if (/^[a-z]+([A-Z][a-z]+)+$/.test(s)) return false;     // camelCase
  if (/^[a-z_]+$/.test(s)) return false;
  if (/^(yc|data|sb)-|^[a-z-]+:/.test(s) && !/ /.test(s)) return false;
  return /[A-Z]/.test(s[0]) || / /.test(s) || /^[a-z]+\.?$/.test(s) === false;
};
const flat = (n, acc) => { if (n.type === 'BinaryExpression' && n.operator === '+') { flat(n.left, acc); flat(n.right, acc); } else acc.push(n); return acc; };
const lit = (n) => (n.type === 'Literal' && typeof n.value === 'string') ? n.value : (n.type === 'TemplateLiteral' && n.expressions.length === 0 ? n.quasis[0].value.cooked : null);
const doScript = (code, file) => {
  let ast;
  try { ast = acorn.parse(code, { ecmaVersion: 'latest', sourceType: 'script', allowAwaitOutsideFunction: true }); } catch (e) { console.error('parse fail', file, e.message); return; }
  const visit = (n) => {
    if (!n || typeof n.type !== 'string') return;
    if (n.type === 'BinaryExpression' && n.operator === '+') {
      const parts = flat(n, []);
      const hasLit = parts.some((p) => lit(p) != null && /[A-Za-z]{2,}/.test(lit(p)));
      if (hasLit) {
        let i = 0, t = '', dyn = false;
        parts.forEach((p) => { const l = lit(p); if (l != null) t += l; else { t += '{' + i++ + '}'; dyn = true; } });
        if (dyn) { if (/[A-Za-z]{2,}/.test(t.replace(/\{\d+\}/g, '')) && t.length < 300) addTpl(t); } else if (looksUI(t)) addPlain(t);
      }
      parts.forEach((p) => { if (lit(p) == null) visit(p); });
      return;
    }
    if (n.type === 'TemplateLiteral' && n.expressions.length) {
      let t = '';
      n.quasis.forEach((q, k) => { t += q.value.cooked; if (k < n.expressions.length) t += '{' + k + '}'; });
      if (/[A-Za-z]{2,}/.test(t.replace(/\{\d+\}/g, '')) && t.length < 300) addTpl(t);
      n.expressions.forEach(visit);
      return;
    }
    if (n.type === 'Literal' && typeof n.value === 'string') { if (looksUI(n.value)) addPlain(n.value); return; }
    if (n.type === 'TemplateLiteral') { const l = lit(n); if (l && looksUI(l)) addPlain(l); return; }
    if (n.type === 'CallExpression' && n.callee.name === 'plural') {
      const a = n.arguments.map(lit);
      if (a[1]) { addTpl('{0} ' + a[1]); addTpl('{0} ' + (a[2] || a[1] + 's')); }
    }
    for (const k of Object.keys(n)) { const v = n[k]; if (Array.isArray(v)) v.forEach(visit); else if (v && typeof v.type === 'string') visit(v); }
  };
  visit(ast);
};
const scriptsOf = (html) => [...html.matchAll(/<script(?![^>]*src)[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
// app source
const app = fs.readFileSync(root + 'src/yes-coach.html', 'utf8');
for (const code of scriptsOf(app)) {
  const m = code.match(/const LIB = (\[.*\]);/);
  if (m) {
    JSON.parse(m[1]).forEach((x) => { ['name', 'desc', 'primary', 'group', 'equipment'].forEach((k) => x[k] && out.lib.add(x[k])); String(x.secondary || '').split(', ').forEach((s) => s && out.lib.add(s)); });
    doScript(code.replace(m[0], 'const LIB=[];'), 'app');
  } else doScript(code, 'app');
}
for (const f of ['tickets.js', 'web.js']) doScript(fs.readFileSync(root + f, 'utf8'), f);
const cons = fs.readFileSync(root + 'consent.html', 'utf8');
scriptsOf(cons).forEach((c) => doScript(c, 'consent'));
// html text and attributes (app, build.py's sign-in section, consent)
const build = fs.readFileSync(root + 'build.py', 'utf8');
const htmlText = (html) => {
  html = html.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '').replace(/<!--[\s\S]*?-->/g, '');
  for (const m of html.matchAll(/>([^<>]+)</g)) { const t = m[1].replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&#39;/g, "'").replace(/&middot;/g, '·').replace(/\s+/g, ' ').trim(); if (/[A-Za-z]{2,}/.test(t) && !/[{}]/.test(t)) out.plain.add(t); }
  for (const m of html.matchAll(/\b(?:aria-label|title|placeholder|alt|aria-description)="([^"]+)"/g)) if (/[A-Za-z]{2,}/.test(m[1])) out.plain.add(m[1]);
};
htmlText(app); htmlText(build); htmlText(cons);
const result = { plain: [...out.plain].sort(), tpl: [...out.tpl].sort(), lib: [...out.lib].sort() };
fs.writeFileSync(fileURLToPath(new URL('./strings.json', import.meta.url)), JSON.stringify(result, null, 1));
console.log('plain', result.plain.length, 'tpl', result.tpl.length, 'lib', result.lib.length);
