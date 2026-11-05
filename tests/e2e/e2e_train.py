"""The Train page: the week as seven blocks, the day sheet under them (start, move, remove, add a day to a rest day)."""
import time, datetime
from playwright.sync_api import sync_playwright
from harness import *

passed = failed = 0
def check(name, cond, extra=''):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print('FAIL', name, extra)

TODAY = datetime.date.today()
ISO = TODAY.isoformat()
DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
MONDAY = TODAY - datetime.timedelta(days=TODAY.weekday())
def date_at(i): return (MONDAY + datetime.timedelta(days=i)).isoformat()
T = TODAY.weekday()                 # index of today in the week
N = (T + 1) % 7                     # the day after (the Pull day), may wrap into the same week from Monday
FREE = next(i for i in range(7) if i not in (T, N))  # an empty day in the week

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = lambda ex: {'ex': ex, 'order': 1, 'sets': 3, 'reps': '8', 'target': '', 'target_at': ISO, 'rest_s': 90, 'note': None}
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': DOW[T], 'items': [it('bench')]}})
    be.docs.append({'path': 'yc/templates/legs', 'data': {'name': 'Legs day', 'order': 2, 'kind': 'Legs', 'focus': 'Legs', 'weekday': DOW[FREE] if False else DOW[N], 'items': [it('bench')]}})

def week_doc(be):
    d = next((d for d in be.docs if d['path'] == 'yc/weeks/' + MONDAY.isoformat()), None)
    return d['data'] if d else {}

PAGE = {}
def until(fn, secs=6):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn(): return True
        except Exception: pass
        PAGE['p'].wait_for_timeout(100)
    return False

def blk(page, i): return page.locator('.wk-blk[data-date="%s"]' % date_at(i))
def planned(page, i): return 'drag' in (blk(page, i).get_attribute('class') or '')

server = serve()
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            PAGE['p'] = page
            page.wait_for_selector('#wk-rows .wk-blk', timeout=8000)
            check('seven blocks', page.locator('.wk-blk').count() == 7, page.locator('.wk-blk').count())
            check('today is selected and its sheet names the day', blk(page, T).get_attribute('aria-pressed') == 'true' and 'Push day' in page.text_content('#wk-sheet'), page.text_content('#wk-sheet'))
            check('planned days are marked', planned(page, T) and planned(page, N) and not planned(page, FREE))
            check('a block says what is on it', 'Push day planned' in (blk(page, T).get_attribute('aria-label') or ''), blk(page, T).get_attribute('aria-label'))
            blk(page, N).click()
            check('tapping a day shows its sheet', blk(page, N).get_attribute('aria-pressed') == 'true' and 'Legs day' in page.text_content('#wk-sheet') and 'Push day' not in page.text_content('#wk-sheet'))
            # move
            page.select_option('#wk-sheet select', date_at(FREE))
            check('moving puts the day on the new date', until(lambda: planned(page, FREE) and not planned(page, N)))
            check('the move is saved in the week', until(lambda: (week_doc(be).get('moves') or {}).get('legs@' + DOW[N]) == date_at(FREE) or date_at(FREE) in (week_doc(be).get('moves') or {}).values()), week_doc(be))
            # remove, with a confirm
            blk(page, FREE).click(); page.click('#wk-sheet .wk-remove')
            check('removing asks first', page.is_visible('#wk-sheet .confirm'))
            page.click('#wk-sheet .confirm >> text=Keep')
            check('keeping leaves the day', planned(page, FREE))
            page.click('#wk-sheet .wk-remove'); page.click('#wk-sheet .confirm button.danger')
            check('confirming removes it from the week', until(lambda: not planned(page, FREE)))
            # a rest day takes a training day
            blk(page, FREE).click()
            check('a rest day says so', 'Rest' in page.text_content('#wk-sheet'))
            page.select_option('#wk-sheet select', 'push')
            check('adding puts a day on the empty date', until(lambda: planned(page, FREE)) and 'Push day' in page.text_content('#wk-sheet'))
            # start from the sheet
            page.click('#wk-sheet .wk-start')
            page.wait_for_selector('#f-bench_1-load', state='visible', timeout=6000)
            check('Start day opens the session', page.is_visible('#sbar'))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (train, phone)', not errs, errs)

        be = Backend(); seed(be)
        def s2(page):
            PAGE['p'] = page
            page.wait_for_selector('#wk-rows .wk-blk', timeout=8000)
            page.click('#wk-next'); page.wait_for_timeout(300)
            check('next week: no block marked today and a sheet shows', page.locator('.wk-blk[aria-pressed=true]').count() == 1 and page.locator('.wk-day.is-today').count() == 0)
            page.click('#wk-prev'); page.wait_for_timeout(300)
            check('back: today is selected again', blk(page, T).get_attribute('aria-pressed') == 'true')
            check('wide: no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            check('blocks are tap-sized', page.evaluate("[...document.querySelectorAll('.wk-blk')].every(b => b.getBoundingClientRect().height >= 44)"))
        errs = session(pw, be, ALICE, s2, width=1280); check('no page errors (train, wide)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.shutdown()
print('passed', passed, 'failed', failed)
raise SystemExit(1 if failed else 0)
