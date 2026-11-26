"""The effort tap after the last set (only when every set reached the top of the reps) and the easier week: offered on the week view,
started with one tap, half the sets at the same weight, and left out of the next-weight rule."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
TODAY = TD.isoformat()
def ago(n): return (TD - datetime.timedelta(days=n)).isoformat()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be, root_extra=None, history=(), sets=3, today_sets=None):
    root = {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}
    root.update(root_extra or {})
    be.docs.append({'path': 'yc', 'data': root})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': WD, 'items': [
        {'ex': 'bench', 'order': 1, 'sets': sets, 'reps': '8 to 12', 'target': '', 'target_at': ago(400), 'rest_s': 90, 'note': None}]}})
    for date, load, reps in history:
        be.docs.append({'path': 'yc/sessions/' + date, 'data': {'date': date, 'template': 'push', 'sets': {
            'bench_%d' % (i + 1): {'ex': 'bench', 'n': i + 1, 'kind': 'work', 'reps': reps, 'load': load, 'done': True, 'at': i + 1} for i in range(sets)}}})

def stored(be, key):
    d = next((d['data'] for d in be.docs if d['path'] == 'yc/sessions/' + TODAY), {})
    return (d.get('sets') or {}).get(key) or {}

def only(page, who):
    def cfg(r):
        r.fulfill(status=200, content_type='application/javascript', body=re.sub(r"planCheckOnly: \[[^\]]*\]", 'planCheckOnly: [%s]' % who, r.fetch().text(), count=1))
    page.route('**/config.js', cfg)

def open_day(page):
    page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
    page.click('text=Start Push day')
    page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(300)

def tick_all(page, n, reps, start=1):
    for i in range(start, n + 1):
        page.fill('#f-bench_%d-reps' % i, str(reps))
        page.locator('.set:has(#f-bench_%d-load) .set-tick' % i).click(); page.wait_for_timeout(150)

ME = "'alice@example.com'"
server = subprocess.Popen(['python3', '-m', 'http.server', str(PORT), '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. every set at the top of the range: asked, Hard is stored on the last set, and tapping again clears it
        be = Backend(); seed(be, history=[(ago(4), 60, 10)])
        def s1(page):
            only(page, ME); open_day(page)
            eff = page.locator('.ex-effort')
            check('not asked before the sets are done', eff.is_hidden())
            tick_all(page, 2, 12)
            check('not asked with a set to go', eff.is_hidden())
            tick_all(page, 3, 12, start=3)
            check('asked when every set reached 12', until(lambda: eff.is_visible()))
            page.click('.ex-effort button.eff:has-text("Hard")')
            check('Hard is stored as 0 in reserve on the last set', until(lambda: stored(be, 'bench_3').get('rir') == 0), stored(be, 'bench_3'))
            check('the other sets keep no effort', stored(be, 'bench_1').get('rir') is None)
            check('Hard shows as picked', page.locator('.ex-effort button.eff[aria-pressed="true"]').inner_text().strip().lower() == 'hard')
            page.click('.ex-effort button.eff:has-text("Hard")')
            check('a second tap clears it', until(lambda: stored(be, 'bench_3').get('rir', 'x') is None), stored(be, 'bench_3'))
            page.click('.ex-effort button.eff:has-text("Right")')
            check('Right is 1 in reserve', until(lambda: stored(be, 'bench_3').get('rir') == 1))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (effort)', not errs, errs)

        # ---- 2. not asked when a set fell short, when the RIR column is on, or for someone not on the list
        for label, kw, reps, who in (('a set short of the top', {}, 11, ME), ('RIR column on', {'settings': {'show_rir': True}}, 12, ME), ('not on the list', {}, 12, None)):
            be = Backend(); seed(be, root_extra=kw, history=[(ago(4), 60, 10)])
            def s2(page, reps=reps, who=who, label=label):
                if who: only(page, who)
                open_day(page)
                tick_all(page, 3, reps); page.wait_for_timeout(300)
                check('not asked: ' + label, page.locator('.ex-effort').is_hidden())
            errs = session(pw, be, ALICE, s2, width=390); check('no page errors (%s)' % label, not errs, errs)

        # ---- 3. six weeks of training: the week view offers an easier week; Start makes today half the sets at the same weight
        hist = [(ago(d), 60 + d // 7 * 0, 10) for d in range(2, 46, 3)]
        be = Backend(); seed(be, history=hist, sets=4)
        def s3(page):
            only(page, ME); page.goto(BASE); page.wait_for_selector('#wk-rows .wk-blk', timeout=8000); page.wait_for_timeout(300)
            card = page.locator('#easy-card')
            check('the card is offered', card.is_visible() and 'easier week' in card.inner_text().lower(), card.inner_text() if card.count() else '')
            check('it says why', re.search(r'\d+ weeks of training without an easier week', card.inner_text()) is not None, card.inner_text())
            page.click('#easy-start')
            root = lambda: next(d['data'] for d in be.docs if d['path'] == 'yc')
            check('the week is stored, 7 days from today', until(lambda: (root().get('easy') or {}).get('from') == TODAY and root()['easy'].get('to') == ago(-6)), root().get('easy'))
            check('the card now says it is on', until(lambda: 'end the easier week' in page.locator('#easy-card').inner_text().lower()))
            page.click('text=Start Push day'); page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(300)
            check('half the sets: 2 of 4', page.locator('[id^="f-bench_"][id$="-load"]').count() == 2, page.locator('[id^="f-bench_"][id$="-load"]').count())
            check('same weight as last time', page.input_value('#f-bench_1-load') == '60', page.input_value('#f-bench_1-load'))
            check('the reason says easier week', 'Easier week' in page.locator('.ex-sug').first.text_content(), page.locator('.ex-sug').first.text_content())
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (easy week)', not errs, errs)

        # ---- 4. Not now hides it for two weeks; a fresh start of training has no offer
        be = Backend(); seed(be, history=hist, sets=4)
        def s4(page):
            only(page, ME); page.goto(BASE); page.wait_for_selector('#wk-rows .wk-blk', timeout=8000); page.wait_for_timeout(300)
            page.click('#easy-skip')
            check('Not now hides it', until(lambda: page.locator('#easy-card').is_hidden()))
            root = next(d['data'] for d in be.docs if d['path'] == 'yc')
            check('and remembers the day', until(lambda: next(d['data'] for d in be.docs if d['path'] == 'yc').get('easy_skip') == TODAY))
        errs = session(pw, be, ALICE, s4, width=390); check('no page errors (not now)', not errs, errs)
        be = Backend(); seed(be, history=[(ago(3), 60, 10), (ago(6), 60, 10)])
        def s5(page):
            only(page, ME); page.goto(BASE); page.wait_for_selector('#wk-rows .wk-blk', timeout=8000); page.wait_for_timeout(300)
            check('one week in: no offer', page.locator('#easy-card').is_hidden())
        errs = session(pw, be, ALICE, s5, width=390); check('no page errors (new)', not errs, errs)

        # ---- 5. after the easier week, its sessions do not count: the next weight comes from the week before
        be = Backend(); seed(be, root_extra={'easy': {'from': ago(7), 'to': ago(1)}}, history=[(ago(3), 50, 8), (ago(10), 60, 12)])
        def s6(page):
            only(page, ME); open_day(page)
            check('next weight from before the easier week: 60 + 2.5', page.input_value('#f-bench_1-load') == '62.5', page.input_value('#f-bench_1-load'))
        errs = session(pw, be, ALICE, s6, width=390); check('no page errors (after)', not errs, errs)
finally:
    server.terminate()
done()
