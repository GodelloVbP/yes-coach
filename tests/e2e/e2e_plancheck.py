"""The plan check on the Plan page: minutes, findings with errors first, sets per muscle, and Fix my plan only when something is plainly wrong.
While it is new, config.js planCheckOnly names who sees it."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

D = datetime.date.today().isoformat()
EX = {'squat': ('Back squat', 'Legs'), 'bench': ('Bench press', 'Chest'), 'legext': ('Leg extension', 'Legs'), 'row': ('Barbell row', 'Back'), 'rdl': ('Romanian deadlift', 'Legs')}

def seed(be, days, profile=None):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'profile': profile or {'experience': 'some', 'session_length': 'medium', 'days_per_week': 2},
                                           'schedule': {'enabled': True, 'mode': 'rotation', 'days': ['Mon', 'Thu'], 'rotation': [k for k, _ in days]}}})
    for k, (nm, g) in EX.items():
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    for i, (tid, items) in enumerate(days):
        be.docs.append({'path': 'yc/templates/' + tid, 'data': {'name': tid.title(), 'order': i, 'kind': 'Other', 'focus': '', 'items': [
            {'ex': ex, 'order': j + 1, 'sets': sets, 'reps': '8 to 12', 'target': '', 'target_at': D, 'rest_s': 120, 'note': None} for j, (ex, sets) in enumerate(items)]}})

def only(page, who):
    def cfg(r):
        t = re.sub(r"planCheckOnly: \[[^\]]*\]", 'planCheckOnly: [%s]' % who, r.fetch().text(), count=1)
        r.fulfill(status=200, content_type='application/javascript', body=t)
    page.route('**/config.js', cfg)
    page.goto(BASE); page.wait_for_selector('#today-card', timeout=8000)

def to_plan(page):
    page.click('#tab-plan'); page.wait_for_selector('.pw-card', timeout=8000); page.wait_for_timeout(300)

# no hinge and no pull in the week: errors
BAD = [('upper', [('bench', 4)]), ('lower', [('squat', 4), ('legext', 3)])]
GOOD = [('a', [('squat', 3), ('bench', 3), ('row', 3)]), ('b', [('rdl', 3), ('bench', 3), ('row', 3)])]

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # 1. the shipped config names only the owner: someone else does not see it
        be = Backend(); seed(be, BAD)
        def s1(page):
            to_plan(page)
            check('not on the list: no plan check', page.locator('#plan-check').count() == 0)
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (hidden)', not errs, errs)

        # 2. on the list: the card, errors first, Fix my plan opens the adjust screen with the findings filled in
        be = Backend(); seed(be, BAD)
        def s2(page):
            only(page, "'alice@example.com'"); to_plan(page)
            card = page.locator('#plan-check')
            check('the card shows', card.count() == 1 and 'plan check' in card.inner_text().lower(), card.count())
            text = card.inner_text()
            check('minutes and the time they have', re.search(r'takes (about )?\d+.*You have 60', text) is not None, text)
            lis = card.locator('.wz-items li')
            check('at most 3 findings shown', 1 <= lis.count() <= 3, lis.count())
            check('an error comes first', 'bad' in (lis.first.get_attribute('class') or '') and 'No ' in lis.first.inner_text(), lis.first.inner_text())
            check('missing hinge and pull are named', 'hinge' in text and 'row, pull-up or pulldown' in text, text)
            check('sets per muscle closed at first', card.locator('.pc-mus').count() == 0)
            page.click('#pc-mus-tog'); page.wait_for_timeout(200)
            mus = page.locator('#plan-check .pc-mus li')
            check('10 muscles listed', mus.count() == 10, mus.count())
            chest = page.locator('#plan-check .pc-mus li', has_text='Chest')
            check('chest: 4 sets a week (twice round 2 days in 2 sessions), shown low', chest.locator('b').inner_text() == '4' and 'low' in (chest.get_attribute('class') or ''), chest.inner_text())
            check('Fix my plan is there', page.locator('#pc-fix').count() == 1)
            page.click('#pc-fix'); page.wait_for_selector('#wz-adjust', timeout=5000)
            ask = page.locator('#wz-adjust').input_value()
            check('the adjust screen has the findings as the request', ask.startswith('Fix what the app') and 'hinge' in ask, ask)
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (shown)', not errs, errs)

        # 3. a sound plan: no Fix my plan button
        be = Backend(); seed(be, GOOD)
        def s3(page):
            only(page, "'alice@example.com'"); to_plan(page)
            card = page.locator('#plan-check')
            check('the card shows (sound plan)', card.count() == 1)
            check('no errors in a sound plan', card.locator('li.bad').count() == 0, card.inner_text())
            check('no Fix my plan without errors', page.locator('#pc-fix').count() == 0)
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (sound)', not errs, errs)

        # 4. an empty list in config: everyone sees it, also in Dutch
        be = Backend(); seed(be, BAD)
        def s4(page):
            only(page, ''); to_plan(page)
            card = page.locator('#plan-check')
            check('empty list: shown to everyone', card.count() == 1)
            check('Dutch: the card is translated', 'schemacheck' in card.inner_text().lower() and 'Een training duurt' in card.inner_text(), card.inner_text())
        errs = session(pw, be, ALICE, s4, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
