import json, os, pathlib
HERE = pathlib.Path(__file__).resolve().parent
ui = json.load(open(str(HERE / 'ui_in.json'))); lib = json.load(open(str(HERE / 'lib_in.json')))
extra = json.load(open(str(HERE / 'extra.json')))
out_dir = str(HERE.parent.parent / 'i18n')
for code in ('nl', 'es', 'de', 'fr', 'it'):
    d = {}
    u = json.load(open(str(HERE / 'tr' / '%s_ui.json') % code))
    for k, v in u.items():
        if v.strip() and v != ui[int(k)]: d[ui[int(k)]] = v
    l = json.load(open(str(HERE / 'tr' / '%s_lib.json') % code))
    for k, v in l.items():
        if v.strip() and v != lib[int(k)]: d[lib[int(k)]] = v
    for en, tr in extra.items(): d[en] = tr[code]
    json.dump(d, open('%s/%s.json' % (out_dir, code), 'w'), ensure_ascii=False, separators=(',', ':'))
    print(code, len(d), os.path.getsize('%s/%s.json' % (out_dir, code)))
