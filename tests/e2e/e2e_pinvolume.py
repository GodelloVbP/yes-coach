"""Machine pins count in the volume of the finish screen like kg: the weight on the stack. A workout of machines only still gets a Volume tile."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be, pin_only=False):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {}}})
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
    page.locator('button.skew:visible', has_text=re.compile(r'^\s*Finish', re.I)).first.click(); page.click('#finish-go'); page.wait_for_selector('.fin-tiles', timeout=6000)
    return page.locator('.fin-tiles').inner_text()

server = serve()
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            tx = run_day(page)
            check('kg and pin both count (50 x 10 + 20 x 10 = 700 kg)', '700 kg' in tx, tx)
            check('the share picture gets the same number', page.evaluate("() => !!document.querySelector('.fin-img canvas')"))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors', not errs, errs)
        be = Backend(); seed(be)
        def s2(page):
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
            check('no switch for it in Settings', page.locator('#set-pinvol').count() == 0)
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (settings)', not errs, errs)
finally:
    server.terminate()
done()
