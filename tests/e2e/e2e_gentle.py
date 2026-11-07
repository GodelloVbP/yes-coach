"""Gentler numbers: reaching a target is enough, calories get a band, entries without calories are not a verdict, and a rough entry is fine."""
import subprocess, time, datetime, json, re
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today().isoformat()

def seed(be, kcal, protein, show_cal=True, targets=(2000, 100), no_kcal=False):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': show_cal}, 'nutrition': {'kcal': targets[0], 'protein': targets[1]}}})
    e = {'name': 'Big day', 'p': protein, 'at': 1}
    if not no_kcal: e['kcal'] = kcal
    be.docs.append({'path': 'yc/food/' + TODAY, 'data': {'date': TODAY, 'entries': {'a': e}}})
def entries(be):
    d = next((x['data'] for x in be.docs if x['path'] == 'yc/food/' + TODAY), {'entries': {}})
    return [v for v in d.get('entries', {}).values() if v]

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        def meter(kcal, protein, **kw):
            be = Backend(); seed(be, kcal, protein, **kw); out = {}
            def sc(page):
                page.click('#tab-food'); page.wait_for_selector('#fd-meter .fd-mrow', timeout=8000); page.wait_for_timeout(300)
                out['text'] = page.inner_text('#fd-meter')
                out['over'] = page.locator('#fd-meter .fd-bar.over').count()
                out['k'] = page.locator('#fd-meter .fd-mrow:has-text("Calories") .note').inner_text() if page.locator('#fd-meter .fd-mrow:has-text("Calories") .note').count() else ''
                out['p'] = page.locator('#fd-meter .fd-mrow:has-text("Protein") .note').inner_text()
            errs = session(pw, be, ALICE, sc, width=390); out['errs'] = errs
            return out
        a = meter(1500, 60);   check('below the targets: what is left', 'left' in a['k'] and 'left' in a['p'] and a['over'] == 0, a)
        a = meter(1900, 100);  check('protein reached says so', a['p'] == 'Target reached.', a['p'])
        check('calories within 10% say On target, with no mark', a['k'] == 'On target.' and a['over'] == 0, a)
        a = meter(2200, 100);  check('the top of the band is still on target', a['k'] == 'On target.' and a['over'] == 0, a['k'])
        a = meter(1800, 100);  check('the bottom of the band is still on target', a['k'] == 'On target.', a['k'])
        a = meter(2500, 180);  check('more protein than the target is never "above"', a['p'] == 'Target reached.' and 'above' not in a['p'])
        check('calories well above are said plainly, and marked', 'above your target' in a['k'] and a['over'] == 1, a)
        a = meter(1700, 100);  check('below the band is what is left', a['k'].endswith('kcal left') and a['over'] == 0, a['k'])
        check('no page errors (meter)', not a['errs'], a['errs'])

        # ---- a day with entries that have no calories is a minimum, not a verdict
        a = meter(0, 40, no_kcal=True)
        check('entries without calories say so', 'Some entries have no calories yet.' in a['text'], a['text'])
        a = meter(500, 40)
        check('and the note is not there when every entry has calories', 'no calories yet' not in a['text'])
        a = meter(0, 40, show_cal=False, no_kcal=True)
        check('nothing about calories when they are hidden', 'no calories yet' not in a['text'] and 'Calories' not in a['text'])

        # ---- rough entries, calories shown
        be = Backend(); seed(be, 0, 0, no_kcal=True)
        be.docs[-1]['data']['entries'] = {}
        def rough(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-name', state='visible', timeout=8000)
            def own(name):
                page.fill('#fd-name', name); until(lambda: vis(page, '#fd-hits') and page.locator('#fd-hits .fd-once').count() > 0); page.wait_for_timeout(150)
                page.click('#fd-hits .fd-once'); page.wait_for_selector('#fd-form', state='visible')
            own('Big lunch')
            check('own numbers offers a rough guess', vis(page, '#fd-rough') and page.locator('#fd-rough .fd-chip').count() == 3)
            page.click('#fd-add')
            check('nothing at all asks for calories or protein', 'calories (kcal) or the protein' in page.inner_text('#fd-msg'), page.inner_text('#fd-msg'))
            page.fill('#fd-kcal', 'abc'); page.click('#fd-add')
            check('calories that are not a number are refused', 'as a number' in page.inner_text('#fd-msg'))
            page.fill('#fd-kcal', '')
            page.click('#fd-rough .fd-chip:has-text("Medium")')
            check('a size fills in its protein and is marked', page.input_value('#fd-p') == '25' and page.get_attribute('#fd-rough .fd-chip:has-text("Medium")', 'aria-pressed') == 'true')
            page.click('#fd-add')
            check('protein alone is enough, calories can stay empty', until(lambda: any(e.get('name') == 'Big lunch' for e in entries(be))), page.inner_text('#fd-msg'))
            e = next(e for e in entries(be) if e['name'] == 'Big lunch')
            check('saved as a rough guess without calories', e['p'] == 25 and e.get('kcal') is None and e.get('rough') is True, e)
            check('shown with a ~', 'P ~25 g' in page.inner_text('#fd-list'), page.inner_text('#fd-list'))
            check('and the day says some entries have no calories', until(lambda: 'Some entries have no calories yet.' in page.inner_text('#fd-meter')))
            # typing your own number is not a guess
            own('Soup')
            page.click('#fd-rough .fd-chip:has-text("Small")'); page.fill('#fd-p', '12'); page.click('#fd-add')
            check('typing over a guess is not marked as one', until(lambda: any(e.get('name') == 'Soup' for e in entries(be))) and next(e for e in entries(be) if e['name'] == 'Soup').get('rough') is None, [e for e in entries(be)])
            # a normal food from the tables has no rough chips
            page.fill('#fd-name', 'mosterd'); until(lambda: page.locator('#fd-hits .fd-hit').count() > 0); page.wait_for_timeout(150)
            page.locator('#fd-hits .fd-hit').first.click(); page.wait_for_selector('#fd-form', state='visible')
            page.click('#fd-adjust')
            check('a food from the tables has no rough guess', not vis(page, '#fd-rough'))
            page.click('#fd-cancel')
            check('no horizontal overflow on a phone', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, rough, width=390); check('no page errors (rough)', not errs, errs)
        # ---- calories hidden: rough works there too
        be = Backend(); seed(be, 0, 0, show_cal=False); be.docs[-1]['data']['entries'] = {}
        def hidden(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-name', state='visible', timeout=8000)
            page.fill('#fd-name', 'Salad'); until(lambda: page.locator('#fd-hits .fd-once').count() > 0); page.wait_for_timeout(150)
            page.click('#fd-hits .fd-once'); page.wait_for_selector('#fd-form', state='visible')
            page.click('#fd-rough .fd-chip:has-text("Large")'); page.click('#fd-add')
            check('with calories hidden a rough entry is saved too', until(lambda: any(e.get('name') == 'Salad' and e.get('p') == 40 and e.get('rough') for e in entries(be))), entries(be))
        errs = session(pw, be, ALICE, hidden, width=390); check('no page errors (hidden)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
