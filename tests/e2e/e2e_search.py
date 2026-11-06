"""The food search: your own meals and foods first, one calm line per result, no synonym noise, Show more; your portion sizes in the amount card."""
import subprocess, time, datetime, json, re, unicodedata
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

passed = failed = 0
def check(name, cond, extra=''):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print('FAIL', name, extra)

TODAY = datetime.date.today().isoformat()
PAGE = {}
def until(fn, secs=8):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn(): return True
        except Exception: pass
        PAGE['p'].wait_for_timeout(100)
    return False

NEVO = json.load(open(REPO + '/foods-nevo.json'))['foods']
def row(name): return next(r for r in NEVO if r[1] == name)
def fold(t): return unicodedata.normalize('NFD', str(t)).encode('ascii', 'ignore').decode().lower()
def words(t): return [w for w in re.split(r'[^a-z0-9]+', fold(t)) if w]
GOUDA = 'Kaas Goudse 48+ jong'; MUSTARD = 'Mosterd'
BREAD = 'Tarwebrood bruin'
def item(name, g):
    r = row(name); k = g / 100
    return {'src': 'nevo', 'ref': str(r[0]), 'name': name, 'g': g, 'u': 'g', 'kcal': int(r[5] * k + 0.5), 'p': round(r[6] * k, 1), 'c': round(r[7] * k, 1), 'f': round(r[8] * k, 1)}
# a food whose only match for some word is a synonym: the word is in no food's name, English name or other synonyms' names
name_words = set()
for r in NEVO: name_words.update(words(r[1])); name_words.update(words(r[2] or ''))
for r in json.load(open(REPO + '/foods-usda.json'))['foods']: name_words.update(words(r[1]))
SYN = None
for r in NEVO:
    own = set(words(r[1]) + words(r[2] or ''))
    for w in words(r[3] or ''):
        if len(w) >= 7 and w not in own and not any(nw.startswith(w) for nw in name_words):
            SYN = (w, r[1]); break
    if SYN: break

def seed(be, show_cal=False):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': show_cal}}})
    be.docs.append({'path': 'yc/meals/kaas-toast', 'data': {'name': 'Kaas toast', 'items': [item(BREAD, 70), item(GOUDA, 20)], 'n': 1, 'last': 5, 'kcal': 270, 'p': 12.5, 'c': 30, 'f': 9}})
    be.docs.append({'path': 'yc/meals/gone-meal', 'data': {'gone': True, 'name': 'Kaas ghost'}})
    r = row(GOUDA)
    be.docs.append({'path': 'yc/myfoods/nevo-%s' % r[0], 'data': {'food': 'nevo:%s' % r[0], 'name': GOUDA, 'aka': {'kaas': 1}, 'n': 4, 'last': 9, 'portions': {'plak': 22, 'dikke plak': 35}}})
    be.docs.append({'path': 'yc/myfoods/gone', 'data': {'gone': True}})
    be.docs.append({'path': 'yc/myfoods/broken', 'data': {'food': 5, 'name': 7}})
def day(be): return next((d['data'] for d in be.docs if d['path'] == 'yc/food/' + TODAY), {'entries': {}})
def entries(be): return [e for e in day(be).get('entries', {}).values() if e]
def vis(page, sel): return page.is_visible(sel)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def phone(page):
            PAGE['p'] = page
            page.click('#tab-food'); page.wait_for_selector('#fd-name', state='visible', timeout=8000)
            def search(q):
                page.fill('#fd-name', q)
                until(lambda: vis(page, '#fd-hits') and page.locator('#fd-hits .fd-hit').count() > 0)
                page.wait_for_timeout(150)
            def names(): return [page.locator('#fd-hits .fd-hit b').nth(i).inner_text() for i in range(page.locator('#fd-hits .fd-hit').count())]

            # ---- calm rows, and no synonym noise
            search('mosterd')
            n = names()
            check('mustard: real matches only, no vegetable or soup', 'Mosterd' in n and not any(x.startswith(('Amsoi', 'Soep')) for x in n), n)
            dbrows = page.locator('#fd-hits .fd-hit:not(.fd-new):not(.fd-more)')
            check('at most five results from the tables', dbrows.count() <= 5, dbrows.count())
            first = page.locator('#fd-hits .fd-hit').first
            line = first.locator('.fd-mini').inner_text()
            check('one line: a portion, its amount and protein', re.search(r'\d+(\.\d+)? g · P \d', line) is not None, line)
            check('the data source credit is still shown', 'NEVO' in page.inner_text('#fd-hits .fd-credit'))
            check('no per-100 g numbers, no group tag, no calories', 'per 100' not in page.inner_text('#fd-hits') and page.locator('#fd-hits .fd-bub').count() == 0 and 'kcal' not in page.inner_text('#fd-hits'))
            # a word that is only a synonym still finds its food when nothing else matches
            if SYN:
                search(SYN[0])
                check('a synonym still finds its food when the names hardly match (%s)' % SYN[0], SYN[1] in names(), names())
            else: check('a synonym-only word exists in the data', False)

            # ---- your own first
            search('kaas')
            n = names()
            check('your meal and your food come before the tables', n[0] == 'Kaas toast' and n[1] == GOUDA, n[:4])
            check('the meal is tagged, the food is tagged Yours', page.locator('#fd-hits .fd-hit').nth(0).locator('.fd-bub').inner_text() == 'Your meal' and page.locator('#fd-hits .fd-hit').nth(1).locator('.fd-bub').inner_text() == 'Yours')
            check('removed and broken ones are not offered', 'Kaas ghost' not in n)
            check('your food shows your own portion first', page.locator('#fd-hits .fd-hit').nth(1).locator('.fd-mini').inner_text().startswith('plak · 22 g'), page.locator('#fd-hits .fd-hit').nth(1).locator('.fd-mini').inner_text())
            check('it is not listed a second time from the tables', n.count(GOUDA) == 1, n)
            # ---- show more
            n_before = len(names())
            check('a long list shows a Show more', vis(page, '#fd-hits .fd-more'))
            page.click('#fd-hits .fd-more')
            check('Show more adds the rest and goes away', len(names()) > n_before and page.locator('#fd-hits .fd-more').count() == 0, (n_before, len(names())))
            # ---- enter never logs a meal
            page.fill('#fd-name', 'kaas'); until(lambda: page.locator('#fd-hits .fd-hit').count() > 0); page.wait_for_timeout(150)
            rows_before = len(entries(be))
            page.press('#fd-name', 'Enter')
            check('enter opens your food, it does not log the meal', until(lambda: vis(page, '#fd-form')) and len(entries(be)) == rows_before and 'kaas goudse' in page.inner_text('#fd-card-title').lower(), (len(entries(be)), rows_before))
            chips = [page.locator('#fd-amount .fd-chip').nth(i).inner_text() for i in range(page.locator('#fd-amount .fd-chip').count())]
            check('your portion sizes are the first chips', chips[:2] == ['plak · 22 g', 'dikke plak · 35 g'] and page.locator('#fd-amount .fd-chip.mine').count() == 2, chips[:4])
            check('and the amount starts at your first portion', page.input_value('#fd-g') == '22')
            page.click('#fd-amount .fd-chip:has-text("dikke plak")')
            check('a chip sets the amount', page.input_value('#fd-g') == '35')
            page.click('#fd-add')
            ok = until(lambda: any(e.get('name') == GOUDA and e.get('g') == 35 for e in entries(be)))
            check('added at your portion size, with its table numbers', ok and next(e for e in entries(be) if e.get('name') == GOUDA)['src'] == 'nevo', entries(be))

            # ---- tapping your meal logs it
            page.fill('#fd-name', 'kaas t'); until(lambda: page.locator('#fd-hits .fd-meal').count() > 0)
            page.click('#fd-hits .fd-meal')
            check('a tap on your meal logs it, closes the list and clears the box', until(lambda: any(e.get('name') == 'Kaas toast' and len(e.get('items', [])) == 2 for e in entries(be))) and page.input_value('#fd-name') == '' and not vis(page, '#fd-hits'))
            check('with an Undo toast', 'Added Kaas toast' in page.inner_text('#toast-text'))

            # ---- the amount card still works for plain foods, drinks and US foods (the portions code moved)
            search('mosterd'); page.locator('#fd-hits .fd-hit').first.click()
            check('a plain food opens its card with portions', until(lambda: vis(page, '#fd-form')) and page.locator('#fd-amount .fd-chip').count() >= 1 and page.locator('#fd-amount .fd-chip.mine').count() == 0)
            page.click('#fd-add')
            check('and adds', until(lambda: any(e.get('name') == MUSTARD for e in entries(be))))
            search('melk'); drink = page.locator('#fd-hits .fd-hit:not(.fd-new):not(.fd-more)')
            picked = None
            for i in range(drink.count()):
                if re.search(r'· ?\d+ ml', drink.nth(i).locator('.fd-mini').inner_text()): picked = i; break
            check('a drink shows its amount in ml', picked is not None, [drink.nth(i).locator('.fd-mini').inner_text() for i in range(drink.count())])
            if picked is not None:
                drink.nth(picked).click(); page.wait_for_selector('#fd-form', state='visible')
                chips = [page.locator('#fd-amount .fd-chip').nth(i).inner_text() for i in range(page.locator('#fd-amount .fd-chip').count())]
                check('a drink has ml sizes', any(' ml' in c for c in chips), chips)
                page.click('#fd-cancel')
            search('chicken breast')
            us = [i for i in range(page.locator('#fd-hits .fd-hit:not(.fd-new):not(.fd-more)').count())]
            if us:
                page.locator('#fd-hits .fd-hit:not(.fd-new):not(.fd-more)').first.click(); page.wait_for_selector('#fd-form', state='visible')
                chips = [page.locator('#fd-amount .fd-chip').nth(i).inner_text() for i in range(page.locator('#fd-amount .fd-chip').count())]
                check('a food with sizes has small, medium and large, or household portions', len(chips) >= 1, chips)
                page.click('#fd-cancel')
            check('no horizontal overflow on a phone', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, phone, width=390); check('no page errors', not errs, errs)

        # ---- calories shown
        be = Backend(); seed(be, True)
        def shown(page):
            PAGE['p'] = page
            page.click('#tab-food'); page.wait_for_selector('#fd-name', state='visible', timeout=8000)
            page.fill('#fd-name', 'mosterd'); until(lambda: page.locator('#fd-hits .fd-hit').count() > 0); page.wait_for_timeout(150)
            check('with calories on, a result shows them on its one line', 'kcal' in page.locator('#fd-hits .fd-hit').first.locator('.fd-mini').inner_text())
        errs = session(pw, be, ALICE, shown, width=390); check('no page errors (calories shown)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
print('passed', passed, 'failed', failed)
raise SystemExit(1 if failed else 0)
