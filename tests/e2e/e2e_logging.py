"""End-to-end check of logging a workout: tick, untick, correct a done set, a save that fails and is retried, and a draft that survives a reload."""
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

class Flaky(Backend):
    """A backend whose session writes can be switched off, like a phone that lost signal."""
    down = False
    def handle(self, route):
        if self.down and route.request.url.split('?')[0].endswith('/rest/v1/rpc/yc_update'): return route.abort('internetdisconnected')
        return Backend.handle(self, route)

def seed(be, sets=3):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/exercises/row', 'data': {'name': 'Row', 'group': 'Back', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'items': [
        {'ex': 'bench', 'order': 1, 'sets': sets, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None},
        {'ex': 'row', 'order': 2, 'sets': 2, 'reps': '10', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}]}})

def doc(be, path):
    d = next((d for d in be.docs if d['path'] == path), None)
    return d['data'] if d else {}

def stored(be, key):
    return (doc(be, 'yc/sessions/' + TODAY).get('sets') or {}).get(key) or {}

PAGE = {}  # the page being driven: waiting must go through Playwright, or its route handlers (the fake server) never run
def until(fn, secs=6):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn(): return True
        except Exception: pass
        PAGE['p'].wait_for_timeout(100)
    return False

def start_day(page):
    PAGE['p'] = page
    page.wait_for_selector('text=Start Push day', timeout=8000)
    page.click('text=Start Push day')
    page.wait_for_selector('#f-bench_1-load', state='visible')

def tick(page, key):
    page.locator('.set:has(#f-%s-load) .set-tick' % key).click()

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. tick, untick, correct
        be = Flaky(); seed(be)
        def s1(page):
            start_day(page)
            check('three bench rows and two row rows', page.locator('.set').count() == 5, page.locator('.set').count())
            page.fill('#f-bench_1-load', '60'); page.fill('#f-bench_1-reps', '8')
            check('not ticked yet', page.get_attribute('.set:has(#f-bench_1-load) .set-tick', 'aria-pressed') == 'false')
            tick(page, 'bench_1')
            check('tick is saved as done with the typed values', until(lambda: stored(be, 'bench_1').get('done') is True and stored(be, 'bench_1').get('load') == 60 and stored(be, 'bench_1').get('reps') == 8), stored(be, 'bench_1'))
            check('tick shows pressed', page.get_attribute('.set:has(#f-bench_1-load) .set-tick', 'aria-pressed') == 'true')
            check('rest timer starts', until(lambda: page.get_attribute('#restbar', 'hidden') is None and 'Rest' in page.inner_text('#restbar')), page.inner_html('#restbar')[:200])
            tick(page, 'bench_1')
            check('untick keeps the values and drops done', until(lambda: stored(be, 'bench_1').get('done') is False and stored(be, 'bench_1').get('load') == 60), stored(be, 'bench_1'))
            tick(page, 'bench_1')
            until(lambda: stored(be, 'bench_1').get('done') is True)
            page.fill('#f-bench_1-load', '62.5')
            check('correcting a done set rewrites its load', until(lambda: stored(be, 'bench_1').get('load') == 62.5 and stored(be, 'bench_1').get('done') is True, 8), stored(be, 'bench_1'))
            page.fill('#f-bench_2-reps', '7'); page.fill('#f-bench_2-load', '62.5'); tick(page, 'bench_2')
            check('second set saved with its own key', until(lambda: stored(be, 'bench_2').get('reps') == 7), stored(be, 'bench_2'))
            check('both sets counted', page.locator('.set-tick[aria-pressed=true]').count() == 2)
        errs = session(pw, be, ALICE, s1)
        check('no page errors (tick)', not errs, errs)

        # ---- 2. the save fails, the screen keeps working, the set lands when the connection returns
        be = Flaky(); seed(be)
        def s2(page):
            start_day(page)
            be.down = True
            page.fill('#f-bench_1-load', '55'); page.fill('#f-bench_1-reps', '9')
            tick(page, 'bench_1')
            check('screen shows the set as done while offline', until(lambda: page.get_attribute('.set:has(#f-bench_1-load) .set-tick', 'aria-pressed') == 'true'))
            check('nothing reached the server yet', not stored(be, 'bench_1'))
            be.down = False
            check('the queued set is saved once the connection is back', until(lambda: stored(be, 'bench_1').get('done') is True and stored(be, 'bench_1').get('load') == 55, 25), stored(be, 'bench_1'))
        errs = session(pw, be, ALICE, s2)
        check('no page errors (offline)', not errs, errs)

        # ---- 3. a typed value that was not ticked survives a reload
        be = Flaky(); seed(be)
        def s3(page):
            start_day(page)
            page.fill('#f-bench_2-reps', '6'); page.fill('#f-bench_2-load', '47.5')
            page.wait_for_timeout(700)
            settled(page); page.reload()
            until(lambda: page.is_visible('#resume-btn') or page.is_visible('#f-bench_2-load'), 10)
            if page.is_visible('#resume-btn'): page.click('#resume-btn')
            page.wait_for_selector('#f-bench_2-load', state='visible', timeout=10000)
            check('draft load is still there', page.input_value('#f-bench_2-load') == '47.5', page.input_value('#f-bench_2-load'))
            check('draft reps is still there', page.input_value('#f-bench_2-reps') == '6', page.input_value('#f-bench_2-reps'))
            check('draft is not a saved set', not stored(be, 'bench_2').get('done'))
        errs = session(pw, be, ALICE, s3)
        check('no page errors (draft)', not errs, errs)

        # ---- 4. nothing left the machine
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
print('passed', passed, 'failed', failed)
raise SystemExit(1 if failed else 0)
