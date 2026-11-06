"""Quick food for the days you forget or can't be bothered: a home-screen shortcut, I ate something (fill it in later), the same as yesterday, a nudge after training."""
import subprocess, time, datetime, json, re
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

passed = failed = 0
def check(name, cond, extra=''):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print('FAIL', name, extra)

TODAY = datetime.date.today().isoformat()
YDAY = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
BACK = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
PAGE = {}
def until(fn, secs=8):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn(): return True
        except Exception: pass
        PAGE['p'].wait_for_timeout(100)
    return False

def root(be, extra=None):
    be.docs.append({'path': 'yc', 'data': dict({'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': False}}, **(extra or {}))})
def entries(be, date=TODAY):
    d = next((x['data'] for x in be.docs if x['path'] == 'yc/food/' + date), {'entries': {}})
    return {k: v for k, v in d.get('entries', {}).items() if v}
def vis(page, sel): return page.is_visible(sel)

# ---- the manifest
man = json.load(open(REPO + '/manifest.webmanifest'))
sc = man.get('shortcuts', [])
check('the manifest has a Log food and a Train shortcut', [x['name'] for x in sc] == ['Log food', 'Train'], sc)
check('they open the right page inside the app scope', all(x['url'].startswith('./#') and x['url'][3:] in ('food', 'train') for x in sc) and man['scope'] == './' and man['start_url'] == './')
check('and have an icon each', all(x.get('icons') and x['icons'][0]['src'].startswith('icon-192') for x in sc))

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- the shortcut opens Food
        be = Backend(); root(be)
        def shortcut(page):
            PAGE['p'] = page
            page.goto(BASE + '?from=shortcut#food')
            check('a signed-in person who taps the shortcut lands on Food', until(lambda: vis(page, '#v-food') and vis(page, '#fd-body')), page.url)
            page.goto(BASE + '?from=shortcut2#train')
            check('and the Train shortcut lands on Train', until(lambda: vis(page, '#v-train')))
        errs = session(pw, be, ALICE, shortcut, width=390); check('no page errors (shortcut)', not errs, errs)

        # ---- I ate something, then fill it in
        be = Backend(); root(be)
        def ate(page):
            PAGE['p'] = page
            page.click('#tab-food'); page.wait_for_selector('#fd-ate', state='visible', timeout=8000)
            page.click('#fd-ate')
            check('one tap saves a placeholder with the time', until(lambda: page.locator('#fd-list .fd-quickrow').count() == 1) and re.search(r'Ate something · \d\d:\d\d', page.locator('#fd-list .fd-quickrow').inner_text()) is not None, page.inner_text('#fd-list'))
            q = list(entries(be).values())
            check('stored without numbers, flagged, with the time', len(q) == 1 and q[0]['quick'] is True and q[0]['name'] == 'Ate something' and abs(q[0]['at'] - time.time() * 1000) < 120000 and q[0].get('kcal') is None, q)
            check('the day says something is still to fill in', 'One meal is still to fill in.' in page.inner_text('#fd-meter'))
            check('and counts for nothing in the totals', page.locator('#fd-meter .fd-mrow:has-text("Protein") b').first.inner_text() == '0')
            check('and says so in the toast', 'Fill it in later' in page.inner_text('#toast-text'))
            page.click('#fd-ate'); page.wait_for_timeout(300)
            check('two of them: some meals are still to fill in', 'Some meals are still to fill in.' in page.inner_text('#fd-meter') and page.locator('#fd-list .fd-quickrow').count() == 2)
            page.fill('#fd-name', 'ate'); page.wait_for_timeout(500)
            check('a placeholder is not offered as one of your foods', 'Ate something' not in page.inner_text('#fd-hits') if vis(page, '#fd-hits') else True)
            page.fill('#fd-name', ''); page.keyboard.press('Escape')

            # fill one in: the food replaces it
            page.locator('#fd-list .fd-quickrow').first.locator('.skew').click()
            check('Fill in asks what it was and puts you in the search', vis(page, '#fd-fill') and 'replaces this entry' in page.inner_text('#fd-fill') and page.evaluate("document.activeElement && document.activeElement.id") == 'fd-name')
            page.fill('#fd-name', 'mosterd'); until(lambda: vis(page, '#fd-hits') and page.locator('#fd-hits .fd-hit').count() > 0); page.wait_for_timeout(150)
            page.locator('#fd-hits .fd-hit').first.click(); page.wait_for_selector('#fd-form', state='visible'); page.click('#fd-add')
            check('the food replaces the placeholder', until(lambda: page.locator('#fd-list .fd-quickrow').count() == 1 and page.locator('#fd-list .fd-row:has-text("Mosterd")').count() == 1))
            check('in the data too', len([e for e in entries(be).values() if e.get('quick')]) == 1 and any(e.get('name') == 'Mosterd' for e in entries(be).values()), entries(be))
            check('and the note is gone, with one meal left to fill in', not vis(page, '#fd-fill') and 'One meal is still to fill in.' in page.inner_text('#fd-meter'))
            # cancel keeps it
            page.locator('#fd-list .fd-quickrow .skew').click(); page.click('#fd-fill >> text=Cancel')
            check('Cancel drops the filling in', not vis(page, '#fd-fill'))
            page.fill('#fd-name', 'mosterd'); until(lambda: page.locator('#fd-hits .fd-hit').count() > 0); page.wait_for_timeout(150)
            page.locator('#fd-hits .fd-hit').first.click(); page.wait_for_selector('#fd-form', state='visible'); page.click('#fd-add'); page.wait_for_timeout(500)
            check('so the next food does not replace it', page.locator('#fd-list .fd-quickrow').count() == 1 and page.locator('#fd-list .fd-row:has-text("Mosterd")').count() == 2)
            # remove and undo
            page.click('#fd-list .fd-quickrow .icon')
            check('a placeholder can be removed', until(lambda: page.locator('#fd-list .fd-quickrow').count() == 0))
            page.click('#toast-undo')
            check('and comes back with Undo, still a placeholder', until(lambda: page.locator('#fd-list .fd-quickrow').count() == 1) and any(e.get('quick') for e in entries(be).values()))
            # a past day has no I ate
            page.click('#fd-prev')
            check('on an earlier day there is no I ate something', not vis(page, '#fd-ate'))
            check('no horizontal overflow on a phone', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, ate, width=390); check('no page errors (I ate)', not errs, errs)

        # ---- the same as yesterday
        be = Backend(); root(be)
        meal = {'name': 'Lunch', 'kcal': 400, 'p': 20, 'c': 40, 'f': 10, 'at': 1, 'via': 'connector', 'items': [{'name': 'Bread', 'g': 70, 'u': 'g', 'kcal': 160, 'p': 5, 'c': 29, 'f': 1, 'src': 'nevo', 'ref': '1', 'est': True}, {'name': 'Egg', 'g': 50, 'u': 'g', 'kcal': 75, 'p': 6, 'c': 0, 'f': 5, 'src': 'nevo', 'ref': '2'}]}
        be.docs.append({'path': 'yc/food/' + YDAY, 'data': {'date': YDAY, 'entries': {'a': meal, 'b': {'name': 'Apple', 'kcal': 62, 'p': 0.3, 'c': 14, 'f': 0.2, 'at': 2}, 'c': {'name': 'Ate something', 'quick': True, 'at': 3}, 'd': None}}})
        def yday(page):
            PAGE['p'] = page
            page.click('#tab-food'); page.wait_for_selector('#fd-body', state='visible', timeout=8000)
            check('an empty day after a logged one offers Same as yesterday', until(lambda: vis(page, '#fd-yday')))
            page.click('#fd-yday')
            check('one tap copies the real entries, not the placeholder', until(lambda: page.locator('#fd-list .fd-row').count() == 2) and page.locator('#fd-list .fd-quickrow').count() == 0, page.inner_text('#fd-list'))
            t = list(entries(be).values())
            lunch = next(e for e in t if e['name'] == 'Lunch')
            check('with their foods, amounts and numbers, as new entries', len(t) == 2 and len(lunch['items']) == 2 and lunch['items'][0]['est'] is True and lunch['p'] == 20 and lunch['at'] > 1 and 'via' not in lunch, t)
            check('yesterday is untouched', len(entries(be, YDAY)) == 3)
            check('the day total follows, and the button goes', page.locator('#fd-meter .fd-mrow:has-text("Protein") b').first.inner_text() == '20' and not vis(page, '#fd-yday'))
            check('a toast says so, with Undo', 'Copied yesterday' in page.inner_text('#toast-text'))
            page.click('#toast-undo')
            check('Undo takes the copies off again and the button returns', until(lambda: len(entries(be)) == 0 and vis(page, '#fd-yday')), entries(be))
        errs = session(pw, be, ALICE, yday, width=390); check('no page errors (yesterday)', not errs, errs)
        be = Backend(); root(be)
        be.docs.append({'path': 'yc/food/' + YDAY, 'data': {'date': YDAY, 'entries': {'a': {'name': 'Apple', 'p': 0.3, 'at': 1}}}})
        be.docs.append({'path': 'yc/food/' + TODAY, 'data': {'date': TODAY, 'entries': {'x': {'name': 'Banana', 'p': 1, 'at': 1}}}})
        def has_today(page):
            PAGE['p'] = page
            page.click('#tab-food'); page.wait_for_selector('#fd-body', state='visible', timeout=8000); page.wait_for_timeout(300)
            check('no Same as yesterday when today already has food', not vis(page, '#fd-yday'))
        errs = session(pw, be, ALICE, has_today, width=390); check('no page errors (has food)', not errs, errs)

        # ---- after training
        def workout_seed(be, food_today):
            be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
            be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
            wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
            be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [{'ex': 'bench', 'order': 1, 'sets': 1, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}]}})
            if food_today: be.docs.append({'path': 'yc/food/' + TODAY, 'data': {'date': TODAY, 'entries': {'x': {'name': 'Banana', 'p': 1, 'at': 1}}}})
        def finish_day(page):
            PAGE['p'] = page
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000); page.click('text=Start Push day')
            page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(300)
            page.fill('#f-bench_1-load', '60'); page.fill('#f-bench_1-reps', '8'); page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_timeout(400)
            page.locator('button.skew:visible', has_text='Finish day').first.click(); page.wait_for_selector('#fin-done', state='visible')
        be = Backend(); workout_seed(be, False)
        def nudge(page):
            finish_day(page)
            check('after training with no food logged, the finish screen offers to log it', vis(page, '.fin-eat button'))
            page.click('.fin-eat button')
            check('it goes to Food with the search ready', until(lambda: vis(page, '#v-food') and not vis(page, '#fin-done')) and page.evaluate("document.activeElement && document.activeElement.id") == 'fd-name')
        errs = session(pw, be, ALICE, nudge, width=390); check('no page errors (nudge)', not errs, errs)
        be = Backend(); workout_seed(be, True)
        def no_nudge(page):
            finish_day(page)
            check('with food already logged today, no nudge', not vis(page, '.fin-eat button'))
        errs = session(pw, be, ALICE, no_nudge, width=390); check('no page errors (no nudge)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
print('passed', passed, 'failed', failed)
raise SystemExit(1 if failed else 0)
