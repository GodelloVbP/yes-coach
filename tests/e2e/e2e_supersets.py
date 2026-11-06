"""Supersets: the plan editor toggle, the chip on the card, no rest inside a round, rest after it."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today().isoformat()
def seed(be, group=None):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for k, n, g in (('bench', 'Bench press', 'Chest'), ('row', 'Row', 'Back'), ('squat', 'Squat', 'Legs')):
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': n, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    items = [{'ex': k, 'order': i + 1, 'sets': 2, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None} for i, k in enumerate(('bench', 'row', 'squat'))]
    if group:
        items[0]['group'] = group; items[1]['group'] = group
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': items}})

def open_more(page, i):
    # the checkbox lives in the exercise's "more" details; open the exercise, then the details
    page.wait_for_selector('#ed-ss-%d' % i, state='attached')
    page.evaluate("i => { const d = document.getElementById('ed-ss-' + i).closest('details'); if (d) d.open = true; }", i)

def plan(be):
    return next(d['data'] for d in be.docs if d['path'] == 'yc/templates/push')

def start_day(page):
    page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
    page.click('text=Start Push day')
    page.wait_for_selector('#f-bench_1-load', state='visible')
    page.wait_for_timeout(300)

rest_shown = lambda page: page.get_attribute('#restbar', 'hidden') is None
server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. the plan editor
        be = Backend(); seed(be)
        def s1(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('#tab-plan'); page.wait_for_selector('#v-plan', state='visible')
            page.click('text=Edit day'); page.wait_for_selector('.pw-tap', timeout=6000)
            page.locator('.pw-tap').nth(0).click()
            open_more(page, 0)
            check('the first exercise offers a superset with the next', not page.locator('#ed-ss-0').is_disabled())
            page.locator('.pw-tap').nth(2).click()
            open_more(page, 2)
            check('the last exercise has nothing to pair with', page.locator('#ed-ss-2').is_disabled())
            page.locator('.pw-tap').nth(0).click()
            open_more(page, 0)
            page.locator('#ed-ss-0').check()
            check('ticking pairs the two and saves', until(lambda: plan(be)['items'][0].get('group') and plan(be)['items'][0].get('group') == plan(be)['items'][1].get('group') and not plan(be)['items'][2].get('group')), plan(be)['items'])
            check('the list says superset', 'superset' in page.locator('.pw-idesc').nth(0).text_content() and 'superset' in page.locator('.pw-idesc').nth(1).text_content() and 'superset' not in page.locator('.pw-idesc').nth(2).text_content())
            page.locator('.pw-tap').nth(1).click()
            open_more(page, 1)
            page.locator('#ed-ss-1').check()
            g = lambda: [i.get('group') for i in plan(be)['items']]
            check('chaining the second to the third makes one group of three', until(lambda: g()[0] and g()[0] == g()[1] == g()[2]), g())
            page.locator('#ed-ss-1').uncheck()
            check('splitting leaves a lone exercise without a group', until(lambda: g()[0] and g()[0] == g()[1] and not g()[2]), g())
            page.locator('.pw-tap').nth(0).click()
            open_more(page, 0)
            page.locator('#ed-ss-0').uncheck()
            check('splitting the last pair clears the group', until(lambda: not any(g())), g())
        errs = session(pw, be, ALICE, s1, 1000)
        check('no page errors (editor)', not errs, errs)

        # ---- 2. logging on a phone: bench and row are a superset, squat is not
        be = Backend(); seed(be, 's1')
        def s2(page):
            start_day(page)
            check('bench shows the superset chip', 'Superset with Row' in page.locator('.chip.ss').first.text_content(), page.locator('.chip.ss').count())
            check('only the two paired exercises have it', page.locator('.chip.ss').count() == 2, page.locator('.chip.ss').count())
            page.locator('.set:has(#f-bench_1-load) .set-tick').click()
            check('ticking bench set 1 jumps to the row', until(lambda: page.locator('#f-row_1-load').is_visible()))
            page.wait_for_timeout(300)
            check('no rest inside the round', not rest_shown(page))
            page.locator('.set:has(#f-row_1-load) .set-tick').click()
            check('the rest starts after the last exercise of the round', until(lambda: rest_shown(page)), page.inner_html('#restbar')[:120])
            check('then it goes back to bench for set 2', until(lambda: page.locator('#f-bench_2-load').is_visible()))
        errs = session(pw, be, ALICE, s2, 390)
        check('no page errors (phone)', not errs, errs)

        # ---- 3. the same on a wide screen
        be = Backend(); seed(be, 's1')
        def s3(page):
            start_day(page)
            page.locator('.set:has(#f-bench_1-load) .set-tick').click()
            check('desktop: jumps to the row', until(lambda: page.locator('#f-row_1-load').is_visible()))
            check('desktop: no rest inside the round', not rest_shown(page))
            page.locator('.set:has(#f-row_1-load) .set-tick').click()
            check('desktop: rest after the round', until(lambda: rest_shown(page)))
        errs = session(pw, be, ALICE, s3, 1280)
        check('no page errors (desktop)', not errs, errs)

        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
