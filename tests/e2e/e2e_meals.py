"""A meal logged by a connected AI is one line in the day with its foods tucked under it; guessed amounts show a ~; the foods survive removing and adding it again."""
import subprocess, time, datetime
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
def until(fn, secs=6):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn(): return True
        except Exception: pass
        PAGE['p'].wait_for_timeout(100)
    return False

MEAL = '2 slices bread with egg and cheese'
ITEMS = [
    {'src': 'nevo', 'ref': '1', 'name': 'Tarwebrood bruin', 'g': 70, 'u': 'g', 'kcal': 160, 'p': 5.2, 'c': 29.0, 'f': 1.4, 'est': True},
    {'src': 'nevo', 'ref': '2', 'name': 'Ei kippen- gekookt gem', 'g': 50, 'u': 'g', 'kcal': 75, 'p': 6.2, 'c': 0.0, 'f': 5.3},
    {'src': 'nevo', 'ref': '3', 'name': 'Kaas Goudse 48+ gem', 'g': 20, 'u': 'g', 'kcal': 72, 'p': 5.0, 'c': 0.0, 'f': 5.9, 'est': True},
]
def seed(be, show_cal):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': show_cal}}})
    t = int(time.time() * 1000)
    be.docs.append({'path': 'yc/food/' + TODAY, 'data': {'date': TODAY, 'entries': {
        'm1': {'name': MEAL, 'kcal': 307, 'p': 16.4, 'c': 29.0, 'f': 12.6, 'at': t, 'via': 'connector', 'items': ITEMS},
        'a1': {'name': 'Appel', 'kcal': 62, 'p': 0.3, 'c': 14.0, 'f': 0.2, 'at': t + 1, 'src': 'nevo', 'ref': '9', 'g': 120, 'u': 'g', 'est': True, 'via': 'connector'},
        'b1': {'name': 'Banana', 'kcal': 90, 'p': 1.3, 'c': 20.0, 'f': 0.3, 'at': t + 2},
    }}})
def food_doc(be): return next(d['data'] for d in be.docs if d['path'] == 'yc/food/' + TODAY)
def vis(page, sel): return page.is_visible(sel)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- calories hidden: the default for people who never switched them on
        be = Backend(); seed(be, False)
        def phone(page):
            PAGE['p'] = page
            page.click('#tab-food'); page.wait_for_selector('#fd-list .fd-row', timeout=8000)
            rows = page.locator('#fd-list .fd-row')
            check('three entries, a meal is one of them, not four lines', rows.count() == 3 and page.locator('.fd-items').count() == 1, rows.count())
            meal = page.locator('.fd-row:has(.fd-items)')
            check('the meal shows its own words and its protein', MEAL in meal.inner_text() and 'P 16.4 g' in meal.inner_text())
            check('its foods are tucked away until opened', not vis(page, '.fd-items li') and page.get_attribute('.fd-items', 'open') is None)
            check('a single food and a plain entry have nothing to open', page.locator('.fd-row:has-text("Appel") .fd-items').count() == 0 and page.locator('.fd-row:has-text("Banana") .fd-items').count() == 0)
            check('a guessed amount on a single food shows a ~', '· ~120 g' in page.locator('.fd-row:has-text("Appel")').inner_text())
            check('no calories anywhere while they are hidden', 'kcal' not in page.inner_text('#fd-list'))
            page.click('.fd-items summary')
            lis = page.locator('.fd-items li')
            check('opened: one line per food', lis.count() == 3)
            texts = [lis.nth(i).inner_text() for i in range(3)]
            check('guessed amounts have a ~, a said weight does not', '~70 g' in texts[0] and '· 50 g' in texts[1] and '~' not in texts[1] and '~20 g' in texts[2], texts)
            check('each food shows its protein', 'P 5.2 g' in texts[0] and 'P 6.2 g' in texts[1])
            prot = page.locator('#fd-meter .fd-mrow:has-text("Protein") b').first.inner_text().replace(',', '')
            check('the day total counts the meal once', int(prot) == round(16.4 + 0.3 + 1.3), prot)

            # remove the meal, then undo: it comes back with its foods
            page.click('button[aria-label="Remove %s"]' % MEAL)
            check('removing takes the whole meal off the day', until(lambda: page.locator('#fd-list .fd-row').count() == 2 and page.locator('.fd-items').count() == 0))
            page.click('#toast-undo')
            check('undo brings it back with its foods', until(lambda: page.locator('#fd-list .fd-row').count() == 3 and page.locator('.fd-items').count() == 1))
            saved = [e for e in food_doc(be)['entries'].values() if e.get('name') == MEAL and e.get('items')]
            check('and the saved entry has them too', len(saved) >= 1 and len(saved[-1]['items']) == 3 and saved[-1]['items'][0].get('est') is True, saved)

            # add it again from your own foods
            page.fill('#fd-name', 'slices')
            check('the meal is offered under your own foods', until(lambda: vis(page, '#fd-hits .fd-hit:has(.mine)'), 8))
            page.click('#fd-hits .fd-hit:has(.mine)')
            page.wait_for_selector('#fd-form', state='visible'); page.click('#fd-add')
            check('added again, still a meal with foods under it', until(lambda: page.locator('.fd-row:has(.fd-items)').count() == 2 and page.locator('#fd-list .fd-row').count() == 4), page.locator('#fd-list .fd-row').count())
            again = [e for e in food_doc(be)['entries'].values() if e.get('name') == MEAL and e.get('items')]
            check('the new entry kept its foods', len(again) >= 2 and all(len(e['items']) == 3 for e in again))
            check('no horizontal overflow on a phone', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, phone, width=390); check('no page errors (hidden calories)', not errs, errs)

        # ---- calories shown
        be = Backend(); seed(be, True)
        def shown(page):
            PAGE['p'] = page
            page.click('#tab-food'); page.wait_for_selector('#fd-list .fd-row', timeout=8000)
            check('with calories on, the meal shows its total', '307 kcal' in page.locator('.fd-row:has(.fd-items)').inner_text())
            check('and the foods inside stay one line each', (page.click('.fd-items summary'), page.locator('.fd-items li').count())[1] == 3)
        errs = session(pw, be, ALICE, shown, width=390); check('no page errors (shown calories)', not errs, errs)
        # ---- whatever a connected app stored, the day still shows what is real; the time zone is saved once
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': True}}})
        be.docs.append({'path': 'yc/food/' + TODAY, 'data': {'date': TODAY, 'entries': {
            'gone': None, 'str': 'x', 'num': {'name': 42, 'p': 5}, 'odd': {'name': 'Odd meal', 'p': '5', 'kcal': 'lots', 'at': 1, 'items': [None, 'x', {'name': 'Ok', 'g': 10, 'p': 1}, {'name': 'Also ok', 'g': 'ten'}]},
            'fine': {'name': 'Fine', 'p': 2, 'kcal': 40, 'at': 2}}}})
        tzw = lambda: [r for r in be.requests if r[3] and '"tz"' in __import__('json').dumps(r[3])]
        def odd(page):
            PAGE['p'] = page
            page.click('#tab-food'); page.wait_for_selector('#fd-list .fd-row', timeout=8000)
            names = [page.locator('#fd-list .fd-row-name').nth(i).inner_text() for i in range(page.locator('#fd-list .fd-row').count())]
            check('only real entries are listed, the rest of the day still shows', names == ['Odd meal', 'Fine'], names)
            check('text stored as a number is not shown or added up', 'NaN' not in page.inner_text('#fd-list') and 'lots' not in page.inner_text('#fd-list') and page.locator('#fd-meter .fd-mrow:has-text("Protein") b').first.inner_text() == '2')
            page.click('.fd-items summary')
            check('only real foods inside a meal are listed', [page.locator('.fd-items li').nth(i).inner_text() for i in range(page.locator('.fd-items li').count())] == ['Ok · 10 g · P 1 g', 'Also ok'])
            tz = page.evaluate('Intl.DateTimeFormat().resolvedOptions().timeZone')
            check('the time zone is saved for the connector', until(lambda: (next(d for d in be.docs if d['path'] == 'yc')['data'].get('settings') or {}).get('tz') == tz), tz)
            check('without touching the other settings', next(d for d in be.docs if d['path'] == 'yc')['data']['settings'].get('show_calories') is True)
            settled(page); page.reload(); page.wait_for_timeout(1500)
            check('saved once, not on every visit', len(tzw()) == 1, len(tzw()))
        errs = session(pw, be, ALICE, odd, width=390); check('no page errors (odd data)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
print('passed', passed, 'failed', failed)
raise SystemExit(1 if failed else 0)
