"""Machine pins in the volume of the finish screen: left out by default (a pin is a place in a weight stack, not kg), counted as kg when
the setting is on."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be, settings=None):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': settings or {}}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/exercises/fp', 'data': {'name': 'Face pull', 'group': 'Shoulders', 'category': 'strength', 'unit': 'stack', 'better': 'higher'}})
    it = lambda ex, o: {'ex': ex, 'order': o, 'sets': 1, 'reps': '10', 'target': '', 'target_at': '2026-01-01', 'rest_s': 60, 'note': None}
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [it('bench', 1), it('fp', 2)]}})

def run_day(page):
    page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start')
    page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(300)
    page.fill('#f-bench_1-load', '50'); page.fill('#f-bench_1-reps', '10'); page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_timeout(300)
    page.get_by_role('button', name=re.compile('Next exercise', re.I)).first.click(); page.wait_for_selector('#f-fp_1-load', state='visible'); page.wait_for_timeout(300)
    page.fill('#f-fp_1-load', '20'); page.fill('#f-fp_1-reps', '10'); page.locator('.set:has(#f-fp_1-load) .set-tick').click(); page.wait_for_timeout(900)
    page.locator('button.skew:visible', has_text=re.compile(r'^\s*Finish', re.I)).first.click(); page.wait_for_selector('.fin-tiles', timeout=6000)
    return page.locator('.fin-tiles').inner_text()

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            tx = run_day(page)
            check('default: only the kg set counts (50 x 10 = 500 kg)', '500 kg' in tx and '700' not in tx, tx)
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (default)', not errs, errs)

        be = Backend(); seed(be, {'pin_volume': True})
        def s2(page):
            tx = run_day(page)
            check('on: the pin set counts as kg too (500 + 20 x 10 = 700 kg)', '700 kg' in tx, tx)
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (on)', not errs, errs)

        be = Backend(); seed(be)
        def s3(page):
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
            page.locator('#v-settings section.fold').filter(has=page.locator('#set-pinvol')).locator('.set-tog').click() if page.locator('#set-pinvol').is_hidden() else None
            page.wait_for_selector('#set-pinvol', state='visible')
            check('the switch is off to begin with', not page.is_checked('#set-pinvol'))
            page.check('#set-pinvol'); page.wait_for_timeout(500)
            root = next(d['data'] for d in reversed(be.docs) if d['path'] == 'yc')
            check('and saves in the settings', (root.get('settings') or {}).get('pin_volume') is True, root)
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (switch)', not errs, errs)
finally:
    server.terminate()
done()
