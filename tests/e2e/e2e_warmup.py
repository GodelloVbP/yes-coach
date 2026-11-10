"""Warm-up sets: the button, the ramp, the rows in front, the last-time column, and the automatic option."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today().isoformat()
BACK = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
def seed(be, load=100, auto=False):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    ex = {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher', 'plates': True}
    if auto: ex['warmup'] = True
    be.docs.append({'path': 'yc/exercises/bench', 'data': ex})
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [
        {'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}]}})
    be.docs.append({'path': 'yc/sessions/' + BACK, 'data': {'date': BACK, 'template': 'push', 'sets': {
        'bench_%d' % n: {'ex': 'bench', 'n': n, 'kind': 'work', 'reps': 8, 'load': load, 'done': True, 'at': n} for n in (1, 2, 3)}}})

def stored(be, key):
    d = next((d['data'] for d in be.docs if d['path'] == 'yc/sessions/' + TODAY), {})
    return (d.get('sets') or {}).get(key) or {}

def open_day(page):
    page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
    page.click('text=Start Push day')
    page.wait_for_selector('#f-bench_1-load', state='visible')
    page.wait_for_timeout(300)

val = lambda page, k: (page.input_value('#f-bench_%s' % k))
warm_btn = lambda page: page.locator('.ex:not(.off) .ex-warm')

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. the button and the ramp (100 kg last time, so 102.5 suggested)
        be = Backend(); seed(be)
        def s1(page):
            open_day(page)
            check('three working rows to begin with', page.locator('.set').count() == 3)
            check('the button is there', warm_btn(page).is_visible())
            warm_btn(page).click()
            check('four warm-up rows are added', until(lambda: page.locator('.set').count() == 7), page.locator('.set').count())
            ramp = [(val(page, '%d-load' % n), val(page, '%d-reps' % n)) for n in (1, 2, 3, 4)]
            check('the ramp: bar, then about half, 70% and 85%', ramp == [('20', '10'), ('52.5', '5'), ('72.5', '3'), ('87.5', '1')], ramp)
            check('working sets follow with the suggested weight', [val(page, '5-load'), val(page, '5-reps'), val(page, '7-load')] == ['102.5', '8', '102.5'], (val(page, '5-load'), val(page, '5-reps')))
            check('rows in front are marked warm-up', page.locator('.set-n.warmup').count() == 4, page.locator('.set-n.warmup').count())
            check('generated values look like suggestions, not typing', page.locator('.set:has(#f-bench_1-load) .fld.edited').count() == 0 and page.locator('.set:has(#f-bench_1-load) .fld.sug').count() == 2)
            page.fill('#f-bench_1-load', '25')
            check('typing over one makes it yours', until(lambda: page.locator('#f-bench_1-load').evaluate('e => e.parentElement.classList.contains("edited")')) and page.locator('#f-bench_1-reps').evaluate('e => e.parentElement.classList.contains("sug")'))
            page.fill('#f-bench_1-load', '20')
            check('a warm-up row shows no last time', page.locator('.set:has(#f-bench_1-load) .set-last').text_content() == '–')
            check('the first working row shows last time\'s first set', '100' in page.locator('.set:has(#f-bench_5-load) .set-last').text_content(), page.locator('.set:has(#f-bench_5-load) .set-last').text_content())
            check('the button now takes them away', until(lambda: warm_btn(page).is_visible() and warm_btn(page).inner_text().strip().lower() == 'remove warm-ups'), warm_btn(page).inner_text())
            page.locator('.set:has(#f-bench_1-load) .set-tick').click()
            check('a ticked warm-up is stored as a warm-up', until(lambda: stored(be, 'bench_1').get('kind') == 'warmup' and stored(be, 'bench_1').get('load') == 20), stored(be, 'bench_1'))
            page.locator('.set:has(#f-bench_5-load) .set-tick').click()
            check('with a working set done the button is gone', until(lambda: not warm_btn(page).is_visible()))
            check('a working set is stored as work', until(lambda: stored(be, 'bench_5').get('done') is True and stored(be, 'bench_5').get('kind') in (None, 'work')), stored(be, 'bench_5'))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (ramp)', not errs, errs)

        # ---- 2. under 40 kg there is nothing to warm up for
        be = Backend(); seed(be, load=30)
        def s2(page):
            open_day(page)
            check('no button under 40 kg', not warm_btn(page).is_visible())
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (light)', not errs, errs)

        # ---- 3. after a working set is done, no button
        be = Backend(); seed(be)
        def s3(page):
            open_day(page)
            page.locator('.set:has(#f-bench_1-load) .set-tick').click()
            check('once a set is done the button is gone', until(lambda: not warm_btn(page).is_visible()))
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (after work)', not errs, errs)

        # ---- 4. automatic, once
        be = Backend(); seed(be, auto=True)
        def s4(page):
            open_day(page)
            check('the ramp is there without a tap', page.locator('.set').count() == 7, page.locator('.set').count())
            page.reload()
            page.wait_for_selector('#f-bench_1-load', state='visible', timeout=10000) if page.is_visible('#f-bench_1-load') else None
            if page.is_visible('#resume-btn'): page.click('#resume-btn')
            page.wait_for_selector('#f-bench_1-load', state='visible', timeout=10000)
            check('a reload does not add it again', page.locator('.set').count() == 7, page.locator('.set').count())
        errs = session(pw, be, ALICE, s4, width=390); check('no page errors (auto)', not errs, errs)

        # ---- 5. on a big screen
        be = Backend(); seed(be)
        def s5(page):
            open_day(page)
            warm_btn(page).click()
            check('desktop: ramp added', until(lambda: page.locator('.set').count() == 7))
        errs = session(pw, be, ALICE, s5, width=1280); check('no page errors (desktop)', not errs, errs)
        # ---- 6. taking the warm-ups away again, and one row from the middle
        be = Backend(); seed(be)
        def s6(page):
            open_day(page)
            warm_btn(page).click()
            until(lambda: page.locator('.set').count() == 7)
            page.fill('#f-bench_5-load', '105')
            warm_btn(page).click()
            check('the warm-up rows are gone, the working rows stay', until(lambda: page.locator('.set').count() == 3), page.locator('.set').count())
            check('what was typed in a working row moved up with it', val(page, '1-load') == '105' and val(page, '2-load') == '102.5', (val(page, '1-load'), val(page, '2-load')))
            check('no row is marked warm-up', page.locator('.set-n.warmup').count() == 0)
            check('the button adds them again', warm_btn(page).inner_text().strip().lower() == '+ warm-up', warm_btn(page).inner_text())
            page.click('#toast-undo')
            check('Undo brings the ramp back', until(lambda: page.locator('.set').count() == 7 and val(page, '1-load') == '20' and val(page, '5-load') == '105'), (page.locator('.set').count(), val(page, '1-load')))
            # two warm-ups done, the other two not wanted
            page.locator('.set:has(#f-bench_1-load) .set-tick').click()
            page.locator('.set:has(#f-bench_2-load) .set-tick').click()
            until(lambda: stored(be, 'bench_2').get('done') is True)
            warm_btn(page).click()
            check('done warm-ups stay, the rest go', until(lambda: page.locator('.set').count() == 5 and page.locator('.set-n.warmup').count() == 2), (page.locator('.set').count(), page.locator('.set-n.warmup').count()))
            check('the working rows follow the done warm-ups', val(page, '3-load') == '105' and val(page, '4-load') == '102.5', (val(page, '3-load'), val(page, '4-load')))
            # one row from the middle, through the set menu
            page.fill('#f-bench_5-load', '110')
            page.locator('.set:has(#f-bench_4-load) .set-n').click()
            page.locator('.kmenu .kmenu-rm').click()
            check('a row in the middle can be removed', until(lambda: page.locator('.set').count() == 4 and val(page, '4-load') == '110'), (page.locator('.set').count(), val(page, '4-load')))
            page.locator('.set:has(#f-bench_4-load) .set-tick').click()
            until(lambda: stored(be, 'bench_4').get('done') is True)
            page.locator('.set:has(#f-bench_3-load) .set-n').click()
            page.locator('.kmenu .kmenu-rm').click()
            check('not while a ticked set comes after it', page.locator('.set').count() == 4 and 'untick' in page.locator('#toast-text').inner_text().lower(), page.locator('#toast-text').inner_text())
            page.locator('.set:has(#f-bench_4-load) .set-n').click()
            check('a ticked set has no remove in its menu', page.locator('.kmenu').count() == 1 and page.locator('.kmenu .kmenu-rm').count() == 0)
        errs = session(pw, be, ALICE, s6, width=390); check('no page errors (remove)', not errs, errs)

        # ---- 7. the second exercise for a body part gets the short ramp
        be = Backend(); seed(be)
        be.docs.append({'path': 'yc/exercises/incline', 'data': {'name': 'Incline press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher', 'plates': True}})
        next(d for d in be.docs if d['path'] == 'yc/templates/push')['data']['items'].append({'ex': 'incline', 'order': 2, 'sets': 3, 'reps': '8', 'target': '80', 'target_at': TODAY, 'rest_s': 90, 'note': None})
        def s7(page):
            open_day(page)
            page.locator('.ex-warm').nth(1).dispatch_event('click')  # the second card is folded until its turn
            check('two warm-up rows for the second chest exercise', until(lambda: page.locator('.set-n.warmup').count() == 2), page.locator('.set-n.warmup').count())
            ramp = [(page.input_value('#f-incline_%d-load' % n), page.input_value('#f-incline_%d-reps' % n)) for n in (1, 2)]
            check('60% for 5 and 80% for 2, no empty bar', ramp == [('47.5', '5'), ('65', '2')], ramp)
        errs = session(pw, be, ALICE, s7, width=1280); check('no page errors (short ramp)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
