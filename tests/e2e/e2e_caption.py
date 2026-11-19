"""The line above the sets says what the sets are set up for (sets x reps at the weight the first set starts with) and how the last session
went, with its date; no stale target date and no separate Next number that differs from the rows."""
import datetime, subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
BACK = (TD - datetime.timedelta(days=5)).isoformat()
MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
BACK_TXT = '%d %s' % (int(BACK[8:10]), MON[int(BACK[5:7]) - 1])
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be, history=True, target=''):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.docs.append({'path': 'yc/exercises/row', 'data': {'name': 'One-handed dumbbell row', 'group': 'Back', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper B', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': 'row', 'order': 1, 'sets': 3, 'reps': '10 per arm', 'target': target, 'target_at': '2026-01-01', 'rest_s': 75, 'note': None}]}})
    if history:
        be.docs.append({'path': 'yc/sessions/' + BACK, 'data': {'date': BACK, 'template': 'a', 'sets': {
            'row_%d' % n: {'ex': 'row', 'n': n, 'kind': 'work', 'reps': 10, 'load': 10, 'done': True, 'at': n} for n in (1, 2, 3)}}})

def open_day(page):
    page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start'); page.wait_for_selector('#f-row_1-load', state='visible'); page.wait_for_timeout(400)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            open_day(page)
            cap = page.inner_text('.ex-cap')
            row = page.input_value('#f-row_1-load')
            check('Target: sets x reps at the weight the first row starts with', ('Target 3 × 10 per arm @ %s kg' % row) in cap, (cap, row))
            check('the row starts one step up: 12 kg', row == '12', row)
            check('Last time: the date and how it went', ('Last time (%s) 3 × 10 @ 10 kg' % BACK_TXT) in cap, cap)
            check('no target date and no separate Next', '(1 Jan)' not in cap and 'Next' not in cap, cap)
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors', not errs, errs)

        be = Backend(); seed(be, history=False)
        def s2(page):
            open_day(page)
            cap = page.inner_text('.ex-cap')
            check('first time: Target without a weight, Last time none yet', 'Target 3 × 10 per arm' in cap and '@' not in cap and 'Last time none yet' in cap, cap)
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (first time)', not errs, errs)

        be = Backend(); seed(be, history=False, target='14')
        def s3(page):
            open_day(page)
            cap = page.inner_text('.ex-cap')
            check('a plan target shows as the weight', 'Target 3 × 10 per arm @ 14 kg' in cap and page.input_value('#f-row_1-load') == '14', (cap, page.input_value('#f-row_1-load')))
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (target)', not errs, errs)

        be = Backend(); seed(be)
        def s4(page):
            open_day(page)
            cap = page.inner_text('.ex-cap')
            check('Dutch: Doel and Vorige keer', 'Doel' in cap and 'Vorige keer' in cap, cap)
        errs = session(pw, be, ALICE, s4, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
