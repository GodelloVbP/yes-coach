"""Quick food for the days you forget or can't be bothered: a home-screen shortcut, the same as yesterday, a nudge after training. (I ate something is gone; old placeholders can be removed.)"""
import subprocess, time, datetime, json, re
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today().isoformat()
YDAY = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
BACK = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
def root(be, extra=None):
    be.docs.append({'path': 'yc', 'data': dict({'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': False}}, **(extra or {}))})
def entries(be, date=TODAY):
    d = next((x['data'] for x in be.docs if x['path'] == 'yc/food/' + date), {'entries': {}})
    return {k: v for k, v in d.get('entries', {}).items() if v}

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
            page.goto(BASE + '?from=shortcut#food')
            check('a signed-in person who taps the shortcut lands on Food', until(lambda: vis(page, '#v-food') and vis(page, '#fd-body')), page.url)
            page.goto(BASE + '?from=shortcut2#train')
            check('and the Train shortcut lands on Train', until(lambda: vis(page, '#v-train')))
        errs = session(pw, be, ALICE, shortcut, width=390); check('no page errors (shortcut)', not errs, errs)

        # ---- I ate something is gone; a placeholder an earlier version saved can still be removed
        be = Backend(); root(be)
        be.docs.append({'path': 'yc/food/' + TODAY, 'data': {'date': TODAY, 'entries': {
            'old': {'name': 'Ate something', 'quick': True, 'at': 1700000000000},
            'real': {'name': 'Apple', 'kcal': 62, 'p': 0.3, 'c': 14, 'f': 0.2, 'at': 5}}}})
        def ate(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-body', state='visible', timeout=8000)
            check('there is no I ate something button', page.locator('#fd-ate').count() == 0 and 'I ate something' not in page.inner_text('#v-food'))
            check('and no fill-in note', page.locator('#fd-fill').count() == 0)
            check('an old placeholder is still listed, with the time', until(lambda: page.locator('#fd-list .fd-quickrow').count() == 1) and re.search(r'Ate something · \d\d:\d\d', page.locator('#fd-list .fd-quickrow').inner_text()) is not None, page.inner_text('#fd-list'))
            check('without a Fill in button', page.locator('#fd-list .fd-quickrow .skew').count() == 0)
            check('the day no longer talks about meals to fill in', 'still to fill in' not in page.inner_text('#fd-meter'))
            check('and the placeholder counts for nothing in the totals', '14 g' in page.inner_text('#fd-meter'), page.inner_text('#fd-meter'))  # only the apple counts
            page.fill('#fd-name', 'ate'); page.wait_for_timeout(500)
            check('a placeholder is not offered as one of your foods', 'Ate something' not in page.inner_text('#fd-hits') if vis(page, '#fd-hits') else True)
            page.fill('#fd-name', ''); page.keyboard.press('Escape')
            page.click('#fd-list .fd-quickrow .icon')
            check('a placeholder can be removed', until(lambda: page.locator('#fd-list .fd-quickrow').count() == 0))
            page.click('#toast-undo')
            check('and comes back with Undo', until(lambda: page.locator('#fd-list .fd-quickrow').count() == 1) and any(e.get('quick') for e in entries(be).values()))
            # removing sends only that entry: a food another phone or the connector added since is not wiped
            names = lambda: sorted(e['name'] for e in entries(be).values())
            next(d for d in be.docs if d['path'] == 'yc/food/' + TODAY)['data']['entries']['elsewhere'] = {'name': 'Added elsewhere', 'p': 3, 'at': 5}
            page.click('#fd-list .fd-quickrow .icon'); page.wait_for_timeout(600)
            check('removing an entry keeps what was added elsewhere', 'Added elsewhere' in names() and 'Apple' in names() and 'Ate something' not in names(), names())
            check('no horizontal overflow on a phone', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, ate, width=390); check('no page errors (old placeholder)', not errs, errs)

        # ---- the same as yesterday
        be = Backend(); root(be)
        meal = {'name': 'Lunch', 'kcal': 400, 'p': 20, 'c': 40, 'f': 10, 'at': 1, 'via': 'connector', 'items': [{'name': 'Bread', 'g': 70, 'u': 'g', 'kcal': 160, 'p': 5, 'c': 29, 'f': 1, 'src': 'nevo', 'ref': '1', 'est': True}, {'name': 'Egg', 'g': 50, 'u': 'g', 'kcal': 75, 'p': 6, 'c': 0, 'f': 5, 'src': 'nevo', 'ref': '2'}]}
        be.docs.append({'path': 'yc/food/' + YDAY, 'data': {'date': YDAY, 'entries': {'a': meal, 'b': {'name': 'Apple', 'kcal': 62, 'p': 0.3, 'c': 14, 'f': 0.2, 'at': 2}, 'c': {'name': 'Ate something', 'quick': True, 'at': 3}, 'd': None}}})
        def yday(page):
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
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000); page.click('text=Start Push day')
            page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(300)
            page.fill('#f-bench_1-load', '60'); page.fill('#f-bench_1-reps', '8'); page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_timeout(400)
            page.locator('button.skew:visible', has_text='Finish workout').first.click(); page.wait_for_selector('#fin-done', state='visible')
        be = Backend(); workout_seed(be, False)
        def nudge(page):
            finish_day(page)
            check('after training with no food logged, the finish screen offers to log it', vis(page, '.fin-eat button'))
            page.click('.fin-eat button')
            check('it goes to Food with the search ready', until(lambda: vis(page, '#v-food') and not vis(page, '#fin-done')) and page.evaluate("document.activeElement && document.activeElement.id") == 'fd-name')
        errs = session(pw, be, ALICE, nudge, width=390); check('no page errors (nudge)', not errs, errs)
        # the day you looked at last on Food is not where the nudge sends you: the food is about today
        be = Backend(); workout_seed(be, False)
        def nudge_today(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('#tab-food'); page.wait_for_selector('#fd-prev', state='visible'); page.click('#fd-prev'); page.wait_for_timeout(300)
            page.click('#tab-train'); page.click('text=Start Push day')
            page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(300)
            page.fill('#f-bench_1-load', '60'); page.fill('#f-bench_1-reps', '8'); page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_timeout(400)
            page.locator('button.skew:visible', has_text='Finish workout').first.click(); page.wait_for_selector('#fin-done', state='visible')
            page.click('.fin-eat button')
            check('the nudge opens today, not the day looked at before', until(lambda: vis(page, '#v-food') and page.inner_text('#fd-date').lower().startswith('today')), page.inner_text('#fd-date'))
        errs = session(pw, be, ALICE, nudge_today, width=390); check('no page errors (nudge today)', not errs, errs)
        be = Backend(); workout_seed(be, True)
        def no_nudge(page):
            finish_day(page)
            check('with food already logged today, no nudge', not vis(page, '.fin-eat button'))
        errs = session(pw, be, ALICE, no_nudge, width=390); check('no page errors (no nudge)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
