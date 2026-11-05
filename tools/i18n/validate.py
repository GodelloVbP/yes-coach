import json, re, sys
inp, out, kind = sys.argv[1], sys.argv[2], sys.argv[3]
src = json.load(open(inp)); tr = json.load(open(out))
ph = lambda s: sorted(re.findall(r'\{\d+\}', s))
bad = [(k, src[int(k)], v) for k, v in tr.items() if not (k.isdigit() and int(k) < len(src)) or ph(src[int(k)]) != ph(v)]
empty = [k for k, v in tr.items() if not isinstance(v, str) or not v.strip()]
print('entries', len(tr), 'of', len(src), '| bad placeholders/keys', len(bad), '| empty', len(empty))
for b in bad[:15]: print(b)
miss = [i for i in range(len(src)) if str(i) not in tr]
print('missing (omitted) count', len(miss))
if kind == 'lib': print('lib must be complete: missing', len(miss))
