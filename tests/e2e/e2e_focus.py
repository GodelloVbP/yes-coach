"""Logging on a phone shows one exercise at a time: chips with set counts, Next / Finish bar, All exercises, Last time column."""
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
BACK3 = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
PAGE = {}
def until(fn, secs=6):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn(): return True
        except Exception: pass
        PAGE['p'].wait_for_timeout(100)
    return False

def seed(be, history=True):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for ex, nm, g in (('bench', 'Bench press', 'Chest'), ('row', 'Row', 'Back'), ('curl', 'Curl', 'Arms')):
        be.docs.append({'path': 'yc/exercises/' + ex, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = lambda ex, o, n: {'ex': ex, 'order': o, 'sets': n, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [it('bench', 1, 3), it('row', 2, 2), it('curl', 3, 2)]}})
    if history:
        be.docs.append({'path': 'yc/sessions/' + BACK3, 'data': {'date': BACK3, 'template': 'push', 'sets': {
            'bench_%d' % n: {'ex': 'bench', 'n': n, 'kind': 'work', 'reps': 8, 'load': 60, 'done': True, 'at': n} for n in (1, 2, 3)}}})

def open_day(page):
    PAGE['p'] = page
    page.goto(BASE); page.wait_for_selector('#v-train', state='visible')
    page.wait_for_selector('text=Start Push day', timeout=8000)
    page.click('text=Start Push day')
    page.wait_for_selector('#sess-chips', state='attached')
    page.wait_for_timeout(300)

def vis(page, sel): return page.is_visible(sel)
def tick(page, key): page.locator('.set:has(#f-%s-load) .set-tick' % key).click()

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def phone(page):
            open_day(page)
            chips = page.locator('.fchip')
            check('one chip per exercise', chips.count() == 3, chips.count())
            check('the first open exercise is shown, the others are not', vis(page, '#f-bench_1-load') and not vis(page, '#f-row_1-load') and not vis(page, '#f-curl_1-load'))
            check('the current chip is marked', chips.nth(0).get_attribute('aria-current') == 'true' and chips.nth(1).get_attribute('aria-current') == 'false')
            check('chips show set counts', '0/3' in chips.nth(0).inner_text() and '0/2' in chips.nth(1).inner_text(), chips.nth(0).inner_text())
            check('Last time column shows last session per set', '8 @ 60' in page.locator('.set:has(#f-bench_1-load) .set-last').inner_text(), page.locator('.set:has(#f-bench_1-load) .set-last').inner_text())
            check('a set with no history shows a dash', page.locator('.set:has(#f-bench_2-load) .set-last').count() == 1)
            check('bar offers the next exercise', 'Row' in page.text_content('#focus-next'), page.text_content('#focus-next'))
            page.fill('#f-bench_1-load', '62'); page.fill('#f-bench_1-reps', '8'); tick(page, 'bench_1')
            check('ticking updates the chip count', until(lambda: '1/3' in chips.nth(0).inner_text()), chips.nth(0).inner_text())
            check('it stays on the same exercise', vis(page, '#f-bench_1-load') and not vis(page, '#f-row_1-load'))
            check('rest bar sits above the Next bar', until(lambda: page.evaluate("(() => { const r = document.querySelector('#restbar').getBoundingClientRect(), f = document.querySelector('#focusbar').getBoundingClientRect(); return !document.querySelector('#restbar').hidden && r.bottom <= f.top + 1; })()")))
            # a typed, unticked value survives switching away and back
            page.fill('#f-bench_2-reps', '7'); page.fill('#f-bench_2-load', '62.5')
            page.click('#focus-next')
            check('Next shows the next exercise', vis(page, '#f-row_1-load') and not vis(page, '#f-bench_2-load'))
            check('the chip follows', chips.nth(1).get_attribute('aria-current') == 'true')
            page.click('.fchip >> nth=0')
            check('a chip jumps back', vis(page, '#f-bench_2-load'))
            check('the draft is kept', page.input_value('#f-bench_2-load') == '62.5' and page.input_value('#f-bench_2-reps') == '7')
            page.click('.fchip >> nth=2')
            check('last exercise: the bar is Finish day', page.locator('#focus-next').count() == 0 and 'Finish' in page.text_content('#focusbar'), page.text_content('#focusbar'))
            # all exercises
            page.click('#focus-toggle')
            check('All exercises shows every card', vis(page, '#f-bench_1-load') and vis(page, '#f-row_1-load') and vis(page, '#f-curl_1-load'))
            check('and hides chips and the bar', not vis(page, '.fchip') and not vis(page, '#focusbar'))
            check('the choice is remembered on this device', page.evaluate("localStorage.getItem('yc-focus')") == '"all"')
            settled(page); page.reload()
            until(lambda: page.is_visible('#resume-btn') or page.is_visible('#f-bench_1-load'), 10)
            if page.is_visible('#resume-btn'): page.click('#resume-btn')
            page.wait_for_timeout(1500)
            page.wait_for_selector('#f-bench_1-load', state='visible')
            check('still all exercises after a reload', vis(page, '#f-row_1-load'))
            page.click('#focus-toggle')
            check('back to one at a time', not vis(page, '#f-curl_1-load') and vis(page, '.fchip'))
            check('no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, phone, width=390); check('no page errors (phone)', not errs, errs)

        be = Backend(); seed(be)
        def wide(page):
            open_day(page)
            check('wide: a list of exercises on the left, one card on the right', page.locator('.fchip').count() == 3 and vis(page, '#f-bench_1-load') and not vis(page, '#f-row_1-load'))
            check('wide: no Next bar and no toggle', not vis(page, '#focusbar') and not vis(page, '#focus-toggle'))
            check('wide: the list sits left of the card', page.evaluate("(() => { const a = document.querySelector('.fchip').getBoundingClientRect(), b = document.querySelector('#session .ex:not(.off)').getBoundingClientRect(); return a.right <= b.left + 1; })()"))
            check('wide: note and Add exercise sit under the list', page.evaluate("(() => { const a = document.querySelector('.fchip').getBoundingClientRect(), f = document.querySelector('#session .sess-foot').getBoundingClientRect(); return f.left < a.right && f.top >= a.bottom - 1; })()"))
            page.click('.fchip >> nth=1')
            check('wide: picking an exercise shows it', vis(page, '#f-row_1-load') and not vis(page, '#f-bench_1-load'))
            check('wide: no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, wide, width=1280); check('no page errors (wide)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
print('passed', passed, 'failed', failed)
raise SystemExit(1 if failed else 0)
