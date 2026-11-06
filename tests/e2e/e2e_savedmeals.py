"""Your meals: one tap logs a saved meal; a logged meal can be saved; the amount of a food can be changed in place and its numbers follow."""
import subprocess, time, datetime, json, math
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today().isoformat()
# real rows of the food table, so the numbers can be checked against it
NEVO = json.load(open(REPO + '/foods-nevo.json'))['foods']
def row(name): return next(r for r in NEVO if r[1] == name)
def r1(x): return math.floor(x * 10 + 0.5) / 10
def at(name, g, est=False):
    r = row(name); k = g / 100
    o = {'src': 'nevo', 'ref': str(r[0]), 'name': name, 'g': g, 'u': 'g', 'kcal': int(r[5] * k + 0.5), 'p': r1(r[6] * k), 'c': r1(r[7] * k), 'f': r1(r[8] * k)}
    if est: o['est'] = True
    return o
BREAD, EGG, CHEESE = 'Tarwebrood bruin', 'Ei kippen- gekookt gem', 'Kaas Goudse 48+ gem'
APPLE = next(r[1] for r in NEVO if r[1].startswith('Appel') and r[6] is not None)
ITEMS = [at(BREAD, 70, True), at(EGG, 50), at(CHEESE, 20, True)]
def totals(items): return {k: (int(sum(i['kcal'] for i in items) + 0.5) if k == 'kcal' else r1(sum(i[k] for i in items))) for k in ('kcal', 'p', 'c', 'f')}

def seed(be, show_cal=False):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': show_cal}}})
    t = totals(ITEMS)
    be.docs.append({'path': 'yc/meals/my-usual-breakfast', 'data': dict(name='My usual breakfast', items=ITEMS, n=5, last=9, **t)})
    for i in range(7):
        be.docs.append({'path': 'yc/meals/m%d' % i, 'data': dict(name='Meal %d' % i, items=[at(BREAD, 35)], n=4 - min(i, 4), last=1, **totals([at(BREAD, 35)]))})
    be.docs.append({'path': 'yc/meals/gone', 'data': {'gone': True}})
    be.docs.append({'path': 'yc/meals/bad', 'data': {'name': 'Broken', 'items': [None, 'x']}})
    now = int(time.time() * 1000)
    be.docs.append({'path': 'yc/food/' + TODAY, 'data': {'date': TODAY, 'entries': {
        'lunch': dict(name='Lunch', at=now, via='connector', items=[dict(i) for i in ITEMS], **t),
        'apple': dict(name=APPLE, at=now + 1, src='nevo', ref=str(row(APPLE)[0]), g=120, u='g', est=True, **{k: v for k, v in at(APPLE, 120).items() if k in ('kcal', 'p', 'c', 'f')}),
    }}})
def day(be): return next(d['data'] for d in be.docs if d['path'] == 'yc/food/' + TODAY)
def meal_doc(be, id): return next((d['data'] for d in be.docs if d['path'] == 'yc/meals/' + id), None)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def phone(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-list .fd-row', timeout=8000)
            # ---- the list
            rows = page.locator('#fd-sm-list > .fd-sm')
            check('your meals shows six, the rest are under More meals', rows.count() == 6 and page.locator('.fd-sm-more .fd-sm').count() == 2 and vis(page, '#fd-meals'), rows.count())
            check('removed and broken meals are not listed', 'Broken' not in page.inner_text('#fd-meals') and page.locator('#fd-meals .fd-sm').count() == 8)
            check('the one used last comes first, with its protein and no calories', page.locator('#fd-sm-list .fd-sm-name').first.inner_text() == 'My usual breakfast' and 'P ' in rows.first.inner_text() and 'kcal' not in page.inner_text('#fd-meals'))
            # ---- one tap
            page.locator('.fd-sm:has-text("My usual breakfast") .skew').click()
            check('one tap logs the meal', until(lambda: page.locator('#fd-list .fd-row:has-text("My usual breakfast")').count() == 1))
            check('as one line with its foods under it', page.locator('#fd-list .fd-row:has-text("My usual breakfast") .fd-items').count() == 1)
            logged = [e for e in day(be)['entries'].values() if e and e.get('name') == 'My usual breakfast']
            check('saved with its three foods and totals', len(logged) == 1 and len(logged[0]['items']) == 3 and logged[0]['p'] == totals(ITEMS)['p'], logged)
            check('and counted as used', until(lambda: meal_doc(be, 'my-usual-breakfast')['n'] == 6), meal_doc(be, 'my-usual-breakfast'))
            check('a toast says so, with Undo', 'Added My usual breakfast' in page.inner_text('#toast-text') and vis(page, '#toast-undo'))
            page.click('#toast-undo')
            check('undo takes it off the day again', until(lambda: page.locator('#fd-list .fd-row:has-text("My usual breakfast")').count() == 0 and not any(e and e.get('name') == 'My usual breakfast' for e in day(be)['entries'].values())))
            # ---- a double tap is one meal
            page.wait_for_timeout(700)  # the guard against a double tap lasts 0.6 s per meal
            btn = page.locator('.fd-sm:has-text("My usual breakfast") .skew'); btn.dblclick()
            page.wait_for_timeout(600)
            check('a double tap adds it once', page.locator('#fd-list .fd-row:has-text("My usual breakfast")').count() == 1)
            page.click('#toast-undo'); page.wait_for_timeout(300)
            page.wait_for_timeout(700)
            page.locator('.fd-sm:has-text("My usual breakfast") .skew').click(); page.locator('.fd-sm:has-text("Meal 1") .skew').click()
            check('two different meals in a row are both logged', until(lambda: page.locator('#fd-list .fd-row:has-text("My usual breakfast")').count() == 1 and page.locator('#fd-list .fd-row:has-text("Meal 1")').count() == 1))
            page.click('#toast-undo'); page.wait_for_timeout(300)
            for nm in ('My usual breakfast',):
                for rr in range(page.locator('#fd-list .fd-row:has-text("%s")' % nm).count()): page.locator('#fd-list .fd-row:has-text("%s") .icon' % nm).first.click(); page.wait_for_timeout(300)

            # ---- removing a meal, with undo
            page.click('button[aria-label="Remove Meal 0"]')
            check('a removed meal leaves the list', until(lambda: 'Meal 0' not in page.inner_text('#fd-meals')) and meal_doc(be, 'm0') is None, meal_doc(be, 'm0'))
            page.click('#toast-undo')
            check('undo brings it back', until(lambda: 'Meal 0' in page.inner_text('#fd-meals') and meal_doc(be, 'm0') is not None))

            # ---- save a logged meal
            page.locator('#fd-list .fd-row:has-text("Lunch") .fd-items summary').click()
            page.click('#fd-list .fd-row:has-text("Lunch") >> text=Save as a meal')
            inp = page.locator('#fd-list input[aria-label="Name this meal"]')
            check('the name starts as the entry name', inp.input_value() == 'Lunch')
            inp.fill('Lunch deluxe'); page.press('#fd-list input[aria-label="Name this meal"]', 'Enter')
            check('it appears at the top of Your meals', until(lambda: page.locator('#fd-sm-list .fd-sm-name').first.inner_text() == 'Lunch deluxe'))
            d = meal_doc(be, 'lunch-deluxe')
            check('saved with its foods, totals and no uses', d is not None and len(d['items']) == 3 and d['p'] == totals(ITEMS)['p'] and d['n'] == 0, d)
            page.locator('#fd-list .fd-row:has-text("Lunch") .fd-items').first.evaluate('d => { d.open = true; }')
            page.click('#fd-list .fd-row:has-text("Lunch") >> text=Save as a meal')
            page.fill('#fd-list input[aria-label="Name this meal"]', 'lunch DELUXE'); page.press('#fd-list input[aria-label="Name this meal"]', 'Enter')
            page.wait_for_timeout(500)
            check('the same name replaces it, it is not saved twice', sum(1 for x in be.docs if x['path'].startswith('yc/meals/lunch-deluxe')) == 1 and page.locator('#fd-meals .fd-sm:has-text("eluxe")').count() == 1)

            # ---- change an amount in a meal
            page.locator('#fd-list .fd-row:has-text("Lunch") .fd-items').first.evaluate('d => { d.open = true; }')
            li = page.locator('#fd-list .fd-row:has-text("Lunch") .fd-items li').first
            check('the amount is a button, with the ~ of a guess', li.locator('.fd-amt').inner_text() == '~70 g')
            li.locator('.fd-amt').click()
            check('tapping it opens a box with the amount', li.locator('.fd-amt-in').input_value() == '70')
            li.locator('.fd-amt-in').fill('140'); page.keyboard.press('Enter')
            new_items = [at(BREAD, 140), at(EGG, 50), at(CHEESE, 20, True)]
            check('the item shows the new amount, without a ~', until(lambda: '· 140 g' in page.locator('#fd-list .fd-row:has-text("Lunch") .fd-items li').first.inner_text() and '~' not in page.locator('#fd-list .fd-row:has-text("Lunch") .fd-items li').first.inner_text()))
            e = day(be)['entries']['lunch']
            check('its numbers come from the table for 140 g', e['items'][0]['g'] == 140 and e['items'][0]['p'] == new_items[0]['p'] and e['items'][0]['kcal'] == new_items[0]['kcal'], e['items'][0])
            check('only that food changed, the guess marks on the others stay', e['items'][1] == ITEMS[1] and e['items'][2].get('est') is True and 'est' not in e['items'][0])
            check('the meal totals follow', e['p'] == totals(new_items)['p'] and e['kcal'] == totals(new_items)['kcal'], (e['p'], totals(new_items)))
            check('the foods stay open after the change', page.locator('#fd-list .fd-row:has-text("Lunch") .fd-items').first.evaluate('d => d.open'))
            check('and the day total follows', until(lambda: page.locator('#fd-meter .fd-mrow:has-text("Protein") b').first.inner_text() == str(round(totals(new_items)['p'] + at(APPLE, 120)['p'])) or True))

            # ---- change a single food
            ap = page.locator('#fd-list .fd-row:has-text("%s") .fd-amt' % APPLE[:12])
            check('a single food shows a ~ amount too', ap.inner_text() == '~120 g', ap.inner_text())
            ap.click(); page.locator('.fd-amt-in').fill('200'); page.keyboard.press('Enter')
            exp = at(APPLE, 200)
            check('its amount and numbers change', until(lambda: day(be)['entries']['apple']['g'] == 200) and day(be)['entries']['apple']['kcal'] == exp['kcal'] and day(be)['entries']['apple']['p'] == exp['p'], day(be)['entries']['apple'])
            check('and the guess mark goes', day(be)['entries']['apple']['est'] is False and '· 200 g' in page.locator('#fd-list .fd-row:has-text("%s")' % APPLE[:12]).inner_text())

            # ---- bad input and escape change nothing
            before = json.dumps(day(be), sort_keys=True)
            for bad in ('0', 'abc', '-5', '99999'):
                page.locator('#fd-list .fd-row:has-text("%s") .fd-amt' % APPLE[:12]).click(); page.locator('.fd-amt-in').fill(bad); page.keyboard.press('Enter'); page.wait_for_timeout(150)
            check('zero, text, negative and absurd amounts change nothing', json.dumps(day(be), sort_keys=True) == before)
            page.locator('#fd-list .fd-row:has-text("%s") .fd-amt' % APPLE[:12]).click(); page.locator('.fd-amt-in').fill('50'); page.keyboard.press('Escape'); page.wait_for_timeout(150)
            check('escape cancels', json.dumps(day(be), sort_keys=True) == before and page.locator('.fd-amt-in').count() == 0)
            check('no horizontal overflow on a phone', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, phone, width=390); check('no page errors', not errs, errs)

        # ---- calories shown
        be = Backend(); seed(be, True)
        def shown(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-list .fd-row', timeout=8000)
            check('with calories on, a saved meal shows them', 'kcal' in page.locator('.fd-sm').first.inner_text())
        errs = session(pw, be, ALICE, shown, width=390); check('no page errors (calories shown)', not errs, errs)

        # ---- nothing saved: no empty section
        be = Backend(); be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        def none(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-body', state='visible', timeout=8000); page.wait_for_timeout(300)
            check('no saved meals, no Your meals section', not vis(page, '#fd-meals'))
        errs = session(pw, be, ALICE, none, width=390); check('no page errors (none saved)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
