"""The rest timer takes you back to the exercise it was started on: from another exercise, another tab, or after stepping out of the day."""
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

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for ex, nm, g in (('bench', 'Bench press', 'Chest'), ('row', 'Row', 'Back'), ('curl', 'Curl', 'Arms')):
        be.docs.append({'path': 'yc/exercises/' + ex, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = lambda ex, o, n: {'ex': ex, 'order': o, 'sets': n, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [it('bench', 1, 3), it('row', 2, 2), it('curl', 3, 2)]}})

def vis(page, sel): return page.is_visible(sel)
def tick(page, key): page.locator('.set:has(#f-%s-load) .set-tick' % key).click()

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def phone(page):
            PAGE['p'] = page
            page.goto(BASE); page.wait_for_selector('#v-train', state='visible')
            page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('text=Start Push day')
            page.wait_for_selector('#sess-chips', state='attached')
            page.wait_for_timeout(300)
            page.fill('#f-bench_1-load', '60'); page.fill('#f-bench_1-reps', '8'); tick(page, 'bench_1')
            check('ticking a set starts the rest bar', until(lambda: vis(page, '#restbar')))
            check('the bar is a button', page.evaluate("document.querySelector('#rest-go').tagName") == 'BUTTON')

            # 1. from another exercise
            page.click('#focus-next')
            check('moved on to the next exercise', vis(page, '#f-row_1-load') and not vis(page, '#f-bench_2-load'))
            page.click('#rest-go')
            check('tapping the timer returns to the exercise it was for', until(lambda: vis(page, '#f-bench_2-load') and not vis(page, '#f-row_1-load')))
            check('the chip follows', page.locator('.fchip >> nth=0').get_attribute('aria-current') == 'true')
            check('the timer keeps running', vis(page, '#restbar'))

            # 2. from another tab
            page.click('.fchip >> nth=1')
            page.click('#sb-back')
            page.click('#tabs-nav [data-view="plan"]')
            check('on the Plan tab the timer is still there', until(lambda: vis(page, '#restbar') and not vis(page, '#f-bench_2-load')))
            page.click('#rest-go')
            check('from another tab: back on the day, on that exercise', until(lambda: vis(page, '#f-bench_2-load') and not vis(page, '#f-row_1-load')))

            # 3. after stepping out of the day with Back
            page.click('#sb-back')
            check('after Back the Resume pill and the timer show', until(lambda: vis(page, '#resume-btn') and vis(page, '#restbar')))
            page.click('#rest-go')
            check('from the pill screen: back on the exercise', until(lambda: vis(page, '#f-bench_2-load') and not vis(page, '#resume-btn')))

            # 4. survives a reload
            settled(page); page.reload()
            until(lambda: page.is_visible('#resume-btn') or page.is_visible('#f-bench_1-load'), 10)
            check('the timer is restored after a reload', until(lambda: vis(page, '#restbar'), 10))
            if page.is_visible('#resume-btn'):
                page.click('#rest-go')
                check('after a reload it still knows the exercise', until(lambda: vis(page, '#f-bench_2-load'), 10))
            check('no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, phone, width=390); check('no page errors (phone)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
print('passed', passed, 'failed', failed)
raise SystemExit(1 if failed else 0)
