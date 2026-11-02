"""Build the food tables the Food search loads on demand: foods-nevo.json and foods-usda.json.
NEVO: NEVO2025_v9.0.csv from RIVM (values unchanged; only the decimal comma is read as a number).
USDA: the SR Legacy CSV download from FoodData Central (public domain).
Usage: python3 tools/build_foods.py <NEVO2025_v9.0.csv> <usda sr_legacy folder>"""
import csv, json, sys, collections, pathlib
OUT = pathlib.Path(__file__).resolve().parent.parent

def num(v):
    v = (v or '').strip().replace(',', '.')
    try: return float(v)
    except ValueError: return None

def r1(v): return None if v is None else round(v, 1)

def nevo(path):
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig'), delimiter='|'))
    groups = sorted({r['Food group'] for r in rows})
    gi = {g: i for i, g in enumerate(groups)}
    foods = []
    for r in rows:
        kcal = num(r['ENERCC (kcal)'])
        if kcal is None: continue
        foods.append([r['NEVO-code'], r['Voedingsmiddelnaam/Dutch food name'].strip(), r['Engelse naam/Food name'].strip(), r['Synoniem'].strip(), gi[r['Food group']],
                      round(kcal), r1(num(r['PROT (g)'])), r1(num(r['CHO (g)'])), r1(num(r['FAT (g)'])), 'ml' if 'ml' in r['Hoeveelheid/Quantity'] else 'g'])
    doc = {'v': 1, 'src': 'nevo', 'credit': 'NEVO online version 2025/9.0, RIVM, Bilthoven', 'groups': groups, 'foods': foods}
    (OUT / 'foods-nevo.json').write_text(json.dumps(doc, separators=(',', ':'), ensure_ascii=False))
    print('nevo', len(foods))

def usda(folder):
    d = pathlib.Path(folder)
    cats = {r['id']: r['description'] for r in csv.DictReader(open(d / 'food_category.csv'))}
    units = {r['id']: r['name'] for r in csv.DictReader(open(d / 'measure_unit.csv'))}
    skip = {'Baby Foods', 'Quality Control Materials', 'Branded Food Products Database', 'American Indian/Alaska Native Foods'}
    NUT = {'1008': 'kcal', '1003': 'p', '1005': 'c', '1004': 'f', '2047': 'k2', '2048': 'k3'}
    vals = collections.defaultdict(dict)
    for r in csv.DictReader(open(d / 'food_nutrient.csv')):
        k = NUT.get(r['nutrient_id'])
        if k and r['amount'] != '': vals[r['fdc_id']][k] = float(r['amount'])
    por = collections.defaultdict(list)
    for r in csv.DictReader(open(d / 'food_portion.csv')):
        g = num(r['gram_weight'])
        if not g or g <= 0: continue
        amt = ('%g' % float(r['amount'])) if r['amount'] else '1'
        unit = units.get(r['measure_unit_id'], '')
        unit = '' if unit == 'undetermined' else unit
        label = ' '.join(x for x in [amt, unit, (r['modifier'] or r['portion_description'] or '').strip()] if x)
        por[r['fdc_id']].append((int(r['seq_num'] or 0), label[:40], round(g, 1)))
    out = []
    for f in csv.DictReader(open(d / 'food.csv')):
        cat = cats.get(f['food_category_id'], '')
        if cat in skip: continue
        v = vals.get(f['fdc_id'], {})
        kcal = v.get('kcal', v.get('k2', v.get('k3')))
        if kcal is None: continue
        out.append([int(f['fdc_id']), f['description'], cat, round(kcal), r1(v.get('p', 0)), r1(v.get('c', 0)), r1(v.get('f', 0)), [[l, g] for _, l, g in sorted(por.get(f['fdc_id'], []))][:4]])
    cl = sorted({o[2] for o in out}); ci = {c: i for i, c in enumerate(cl)}
    for o in out: o[2] = ci[o[2]]
    doc = {'v': 1, 'src': 'usda', 'credit': 'USDA FoodData Central', 'groups': cl, 'foods': out}
    (OUT / 'foods-usda.json').write_text(json.dumps(doc, separators=(',', ':'), ensure_ascii=False))
    print('usda', len(out))

if __name__ == '__main__':
    nevo(sys.argv[1])
    usda(sys.argv[2])
