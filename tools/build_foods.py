"""Build the food tables the Food search loads on demand: foods-nevo.json and foods-usda.json.
NEVO: NEVO2025_v9.0.csv from RIVM (values unchanged; only the decimal comma is read as a number).
USDA: the SR Legacy CSV download from FoodData Central (public domain). Both per 100 g: no household portions, so every food works the same way.
Usage: python3 tools/build_foods.py <NEVO2025_v9.0.csv> <usda sr_legacy folder>"""
import csv, json, sys, collections, pathlib
OUT = pathlib.Path(__file__).resolve().parent.parent

def num(v):
    v = (v or '').strip().replace(',', '.')
    try: return float(v)
    except ValueError: return None

def r1(v): return None if v is None else round(v, 1)

# short food-type tags, the same words for both tables
NEVO_TYPE = {'Potatoes and tubers': 'Potatoes', 'Vegetables': 'Vegetables', 'Meat and poultry': 'Meat', 'Pastry and biscuits': 'Pastry', 'Cereal products and types of flour': 'Grains',
    'Milk and milk products': 'Dairy', 'Sugar, sweets and sweet sauces': 'Sweets', 'Bread': 'Bread', 'Non-alcoholic beverages': 'Drinks', 'Fruits': 'Fruit',
    'Fish, crustacean and shellfish': 'Fish', 'Mixed dishes': 'Meals', 'Savoury sauces': 'Sauces', 'Cheese': 'Cheese', 'Savoury snacks': 'Snacks', 'Fats and oils': 'Fats and oils',
    'Cold meat cuts': 'Cold cuts', 'Meat substitutes and dairy substitutes': 'Plant-based', 'Foods for special nutritional use': 'Supplements', 'Herbs and spices': 'Spices',
    'Alcoholic beverages': 'Alcohol', 'Legumes': 'Legumes', 'Nuts and seeds': 'Nuts and seeds', 'Soups': 'Soups', 'Savoury bread spreads': 'Spreads', 'Miscellaneous foods': 'Other', 'Eggs': 'Eggs'}
USDA_TYPE = {'Alcoholic Beverages': 'Alcohol', 'Baked Products': 'Bakery', 'Beef Products': 'Meat', 'Beverages': 'Drinks', 'Breakfast Cereals': 'Cereals', 'Cereal Grains and Pasta': 'Grains',
    'Dairy and Egg Products': 'Dairy', 'Fast Foods': 'Fast food', 'Fats and Oils': 'Fats and oils', 'Finfish and Shellfish Products': 'Fish', 'Fruits and Fruit Juices': 'Fruit',
    'Lamb, Veal, and Game Products': 'Meat', 'Legumes and Legume Products': 'Legumes', 'Meals, Entrees, and Side Dishes': 'Meals', 'Nut and Seed Products': 'Nuts and seeds',
    'Pork Products': 'Meat', 'Poultry Products': 'Meat', 'Restaurant Foods': 'Restaurant', 'Sausages and Luncheon Meats': 'Cold cuts', 'Snacks': 'Snacks',
    'Soups, Sauces, and Gravies': 'Sauces and soups', 'Spices and Herbs': 'Spices', 'Sweets': 'Sweets', 'Vegetables and Vegetable Products': 'Vegetables'}

def nevo(path):
    rows = list(csv.DictReader(open(path, encoding='utf-8-sig'), delimiter='|'))
    groups = sorted({NEVO_TYPE.get(r['Food group'], 'Other') for r in rows})
    gi = {g: i for i, g in enumerate(groups)}
    foods = []
    for r in rows:
        kcal = num(r['ENERCC (kcal)'])
        if kcal is None: continue
        foods.append([r['NEVO-code'], r['Voedingsmiddelnaam/Dutch food name'].strip(), r['Engelse naam/Food name'].strip(), r['Synoniem'].strip(), gi[NEVO_TYPE.get(r['Food group'], 'Other')],
                      round(kcal), r1(num(r['PROT (g)'])), r1(num(r['CHO (g)'])), r1(num(r['FAT (g)'])), 'ml' if 'ml' in r['Hoeveelheid/Quantity'] else 'g', r1(num(r['SUGAR (g)'])), r1(num(r['FIBT (g)']))])
    doc = {'v': 1, 'src': 'nevo', 'credit': 'NEVO online version 2025/9.0, RIVM, Bilthoven', 'groups': groups, 'foods': foods}
    (OUT / 'foods-nevo.json').write_text(json.dumps(doc, separators=(',', ':'), ensure_ascii=False))
    print('nevo', len(foods))

def usda(folder):
    d = pathlib.Path(folder)
    cats = {r['id']: r['description'] for r in csv.DictReader(open(d / 'food_category.csv'))}
    units = {r['id']: r['name'] for r in csv.DictReader(open(d / 'measure_unit.csv'))}
    skip = {'Baby Foods', 'Quality Control Materials', 'Branded Food Products Database', 'American Indian/Alaska Native Foods'}
    NUT = {'1008': 'kcal', '1003': 'p', '1005': 'c', '1004': 'f', '2047': 'k2', '2048': 'k3', '2000': 's', '1063': 's2', '1079': 'fib'}
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
        typ = USDA_TYPE.get(cat, 'Other')
        if cat in skip: continue
        v = vals.get(f['fdc_id'], {})
        kcal = v.get('kcal', v.get('k2', v.get('k3')))
        if kcal is None: continue
        out.append([int(f['fdc_id']), f['description'], typ, round(kcal), r1(v.get('p', 0)), r1(v.get('c', 0)), r1(v.get('f', 0)), r1(v.get('s', v.get('s2'))), r1(v.get('fib'))])
    cl = sorted({o[2] for o in out}); ci = {c: i for i, c in enumerate(cl)}
    for o in out: o[2] = ci[o[2]]
    doc = {'v': 1, 'src': 'usda', 'credit': 'USDA FoodData Central', 'groups': cl, 'foods': out}
    (OUT / 'foods-usda.json').write_text(json.dumps(doc, separators=(',', ':'), ensure_ascii=False))
    print('usda', len(out))

if __name__ == '__main__':
    nevo(sys.argv[1])
    usda(sys.argv[2])
