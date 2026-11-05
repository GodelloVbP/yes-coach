"""The suggested next weight: the prefilled value, the line that says why, the way back to last time, the switch, and what a ticked set remembers."""
import time, datetime
from playwright.sync_api import sync_playwright
from harness import *

passed = failed = 0
def check(name, cond, extra=''):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print('FAIL', name, extra)

TODAY = datetime.date.today().isoformat()
BACK = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
OLD = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
PAGE = {}
def until(fn, secs=6):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn(): return True
        except Exception: pass
        PAGE['p'].wait_for_timeout(100)
    return False

def seed(be, reps=(8, 8, 8), loads=(60, 60, 60), target='', target_at=TODAY, settings=None, inc=None, last=BACK, plan_reps='8'):
    root = {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}
    if settings: root['settings'] = settings
    be.docs.append({'path': 'yc', 'data': root})
    ex = {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}
    if inc: ex['inc'] = inc
    be.docs.append({'path': 'yc/exercises/bench', 'data': ex})
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [
        {'ex': 'bench', 'order': 1, 'sets': 3, 'reps': plan_reps, 'target': target, 'target_at': target_at, 'rest_s': 90, 'note': None}]}})
    if last:
        be.docs.append({'path': 'yc/sessions/' + last, 'data': {'date': last, 'template': 'push', 'sets': {
            'bench_%d' % (i + 1): {'ex': 'bench', 'n': i + 1, 'kind': 'work', 'reps': reps[i], 'load': loads[i], 'done': True, 'at': i + 1} for i in range(3)}}})

def root(be): return next(d['data'] for d in be.docs if d['path'] == 'yc')
def stored(be, key):
    d = next((d['data'] for d in be.docs if d['path'] == 'yc/sessions/' + TODAY), {})
    return (d.get('sets') or {}).get(key) or {}

def open_day(page):
    PAGE['p'] = page
    page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
    page.click('text=Start Push day')
    page.wait_for_selector('#f-bench_1-load', state='visible')
    page.wait_for_timeout(300)

def sug_text(page):
    loc = page.locator('.ex:not(.off) .ex-sug')
    return (loc.first.text_content() or '').strip() if loc.count() and loc.first.is_visible() else ''

server = serve()
try:
    with sync_playwright() as pw:
        # ---- 1. every set reached the reps: one step up, with the reason, and a way back
        be = Backend(); seed(be)
        def s1(page):
            open_day(page)
            check('load is last time plus one step', page.input_value('#f-bench_1-load') == '62.5', page.input_value('#f-bench_1-load'))
            check('every set gets it', page.input_value('#f-bench_3-load') == '62.5')
            check('reps stay at the plan', page.input_value('#f-bench_1-reps') == '8')
            check('the line says why', '+2.5 kg: all 3 sets reached 8 last time' in sug_text(page), sug_text(page))
            check('the value is marked as suggested', page.locator('#f-bench_1-load').evaluate('e => e.parentElement.classList.contains("sug")'))
            page.click('.ex:not(.off) .ex-sug-undo')
            check('Use last time shows last time', until(lambda: page.input_value('#f-bench_1-load') == '60'), page.input_value('#f-bench_1-load'))
            check('and the button offers the suggestion again', 'Use the suggestion' in sug_text(page), sug_text(page))
            page.click('.ex:not(.off) .ex-sug-undo')
            check('the suggestion comes back', until(lambda: page.input_value('#f-bench_1-load') == '62.5'))
            page.locator('.set:has(#f-bench_1-load) .set-tick').click()
            check('a ticked set keeps what was suggested', until(lambda: stored(be, 'bench_1').get('sug') == {'load': 62.5, 'reps': 8}), stored(be, 'bench_1'))
            check('and what was done', stored(be, 'bench_1').get('load') == 62.5)
            page.fill('#f-bench_2-load', '60')
            page.locator('.set:has(#f-bench_2-load) .set-tick').click()
            check('a changed load is stored as typed, with the suggestion beside it', until(lambda: stored(be, 'bench_2').get('load') == 60 and (stored(be, 'bench_2').get('sug') or {}).get('load') == 62.5), stored(be, 'bench_2'))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (up)', not errs, errs)

        # ---- 2. a set fell short: same weight, and it says so
        be = Backend(); seed(be, reps=(8, 8, 6))
        def s2(page):
            open_day(page)
            check('short set: same weight', page.input_value('#f-bench_1-load') == '60', page.input_value('#f-bench_1-load'))
            check('and the reason', 'not every set reached 8' in sug_text(page), sug_text(page))
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (short)', not errs, errs)

        # ---- 3. a plan target set after the last session wins
        be = Backend(); seed(be, target='70', target_at=TODAY)
        def s3(page):
            open_day(page)
            check('the plan target is used', page.input_value('#f-bench_1-load') == '70', page.input_value('#f-bench_1-load'))
            check('and there is no suggestion line', sug_text(page) == '', sug_text(page))
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (target)', not errs, errs)

        # ---- 4. switched off
        be = Backend(); seed(be, settings={'progress_suggest': False})
        def s4(page):
            open_day(page)
            check('off: last time as before', page.input_value('#f-bench_1-load') == '60', page.input_value('#f-bench_1-load'))
            check('off: no line', sug_text(page) == '')
        errs = session(pw, be, ALICE, s4, width=390); check('no page errors (off)', not errs, errs)

        # ---- 5. the exercise's own step, a range, a long break
        be = Backend(); seed(be, inc=5)
        def s5(page):
            open_day(page)
            check('own step of 5', page.input_value('#f-bench_1-load') == '65', page.input_value('#f-bench_1-load'))
        errs = session(pw, be, ALICE, s5, width=390); check('no page errors (step)', not errs, errs)

        be = Backend(); seed(be, plan_reps='8-12', reps=(12, 10, 9))
        def s6(page):
            open_day(page)
            got = [page.input_value('#f-bench_%d-reps' % n) for n in (1, 2, 3)]
            check('range: one more rep per set, at the same weight', got == ['12', '11', '10'] and page.input_value('#f-bench_1-load') == '60', got)
        errs = session(pw, be, ALICE, s6, width=390); check('no page errors (range)', not errs, errs)

        be = Backend(); seed(be, last=OLD)
        def s7(page):
            open_day(page)
            check('long break: ten percent down', page.input_value('#f-bench_1-load') == '53.75', page.input_value('#f-bench_1-load'))
            check('and it says why', 'days since your last session' in sug_text(page), sug_text(page))
        errs = session(pw, be, ALICE, s7, width=390); check('no page errors (break)', not errs, errs)

        # ---- 8. no history: nothing changes
        be = Backend(); seed(be, last=None)
        def s8(page):
            open_day(page)
            check('no history: empty load and no line', page.input_value('#f-bench_1-load') == '' and sug_text(page) == '')
        errs = session(pw, be, ALICE, s8, width=390); check('no page errors (new)', not errs, errs)

        # ---- 9. the switch in Settings
        be = Backend(); seed(be)
        def s9(page):
            PAGE['p'] = page
            page.goto(BASE + '#more'); page.wait_for_selector('#tab-settings', state='attached')
            page.evaluate("document.querySelector('#tab-settings').click()")
            page.wait_for_selector('#set-prog', state='attached')
            sec = page.locator('section:has(#set-prog) .set-tog')
            if sec.get_attribute('aria-expanded') != 'true': sec.click()
            page.wait_for_selector('#set-prog', state='visible')
            check('the switch is on by default', page.is_checked('#set-prog'))
            page.uncheck('#set-prog')
            check('turning it off is saved', until(lambda: (root(be).get('settings') or {}).get('progress_suggest') is False), root(be))
        errs = session(pw, be, ALICE, s9, width=390); check('no page errors (settings)', not errs, errs)

        # ---- 10. on a big screen
        be = Backend(); seed(be)
        def s10(page):
            open_day(page)
            check('desktop: suggestion and line', page.input_value('#f-bench_1-load') == '62.5' and 'reached 8' in sug_text(page), sug_text(page))
        errs = session(pw, be, ALICE, s10, width=1280); check('no page errors (desktop)', not errs, errs)

        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.shutdown()
print('passed', passed, 'failed', failed)
raise SystemExit(1 if failed else 0)
