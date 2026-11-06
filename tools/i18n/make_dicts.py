import json, os, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
ui = json.load(open(str(HERE / 'ui_in.json'))); lib = json.load(open(str(HERE / 'lib_in.json')))
extra = json.load(open(str(HERE / 'extra.json')))
out_dir = str(HERE.parent.parent / 'i18n')
# The names of the library's exercises travel in each dictionary as __names, so the app can leave them in English
# (most people know an exercise by its English name) unless the person switches Translate exercise names on.
# A name that is also a screen label stays translatable.
src = open(str(HERE.parent.parent / 'src' / 'yes-coach.html'), encoding='utf-8').read()
LIB = json.loads(re.search(r'const LIB = (\[.*?\]);\n', src, re.S).group(1))
labels = set(ui) | set(extra)
NAMES = sorted({e['name'] for e in LIB} - labels)
assert len(LIB) > 100 and len(NAMES) > 100, 'the exercise library was not read from the source (%d exercises)' % len(LIB)
for code in ('nl', 'es', 'de', 'fr', 'it'):
    d = {}
    u = json.load(open(str(HERE / 'tr' / '%s_ui.json') % code))
    for k, v in u.items():
        if v.strip() and v != ui[int(k)]: d[ui[int(k)]] = v
    l = json.load(open(str(HERE / 'tr' / '%s_lib.json') % code))
    for k, v in l.items():
        if v.strip() and v != lib[int(k)]: d[lib[int(k)]] = v
    for en, tr in extra.items(): d[en] = tr[code]
    d['__names'] = NAMES
    json.dump(d, open('%s/%s.json' % (out_dir, code), 'w'), ensure_ascii=False, separators=(',', ':'))
    print(code, len(d), os.path.getsize('%s/%s.json' % (out_dir, code)))
