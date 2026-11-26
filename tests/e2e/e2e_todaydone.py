"""Today's finished workout lives in one place: the Today card, with its four buttons two by two. The week panel below does not repeat it for
today, but still has Look back or correct and Delete for an earlier day."""
import datetime, subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today(); TODAY = TD.isoformat()
GRANT = [{'client': {'id': 'c-claude', 'name': 'Claude', 'uri': 'https://claude.ai'}, 'scopes': ['openid'], 'granted_at': now()}]

def seed(be, yesterday=False):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.docs.append({'path': 'yc/exercises/sq', 'data': {'name': 'Squat', 'group': 'Legs', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/legs', 'data': {'name': 'Legs B', 'order': 1, 'kind': 'Legs', 'focus': '', 'items': [{'ex': 'sq', 'order': 1, 'sets': 3, 'reps': '8', 'target': '', 'target_at': '2026-10-01', 'rest_s': 90, 'note': None}]}})
    days = [TODAY] + ([(TD - datetime.timedelta(days=1)).isoformat()] if yesterday else [])
    for d in days:
        be.docs.append({'path': 'yc/sessions/' + d, 'data': {'date': d, 'template': 'legs', 'split': 'Legs', 'label': 'Legs B', 'finished_at': 1, 'sets': {'sq_%d' % i: {'ex': 'sq', 'n': i, 'order': 1, 'kind': 'work', 'reps': 8, 'load': 60, 'done': True, 'at': i} for i in (1, 2, 3)}}})

BOX = "(sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width) }; }"

server = serve()
try:
    with sync_playwright() as pw:
        # with Claude connected: four buttons, two by two
        be = Backend(); be.grants = GRANT; seed(be, yesterday=TD.weekday() > 0)
        def s1(page):
            page.set_viewport_size({'width': 390, 'height': 844})
            page.wait_for_selector('#today-card .t-head', timeout=8000)
            until(lambda: page.is_visible('#btn-claude-day'))
            head = page.text_content('#today-card .t-head')
            check('the card says which workout, with a tick and no "Done:"', '✓' in head and 'Legs B' in head and 'Done' not in head, head)
            check('it still says how many sets', '3 sets logged' in page.text_content('#today-card'))
            ids = ['#btn-look', '#btn-claude-day', '#btn-swap', '#btn-delete-day']
            b = {i: page.evaluate(BOX, '#today-card ' + i) for i in ids}
            check('Look back or correct and Send to Claude share the first row', b['#btn-look']['y'] == b['#btn-claude-day']['y'] and b['#btn-look']['x'] < b['#btn-claude-day']['x'], b)
            check('Train another workout and Delete workout share the second row', b['#btn-swap']['y'] == b['#btn-delete-day']['y'] and b['#btn-swap']['x'] < b['#btn-delete-day']['x'] and b['#btn-swap']['y'] > b['#btn-look']['y'], b)
            check('all four are the same width: a 2 by 2 grid', len({v['w'] for v in b.values()}) == 1 or max(v['w'] for v in b.values()) - min(v['w'] for v in b.values()) <= 2, b)
            check('the labels', [page.inner_text('#today-card ' + i).strip().lower() for i in ids] == ['look back or correct', 'send to claude', 'train another workout', 'delete workout'], [page.inner_text('#today-card ' + i) for i in ids])
            # the week panel does not say it again
            sheet = page.inner_text('#wk-sheet')
            check('the panel for today points to the card and repeats nothing', 'card at the top' in sheet and 'sets logged' not in sheet and page.locator('#wk-sheet .wk-del').count() == 0 and page.locator('#wk-sheet .wk-open').count() == 0, sheet)
            # the buttons work
            page.click('#today-card #btn-swap')
            check('Train another workout opens its list under the buttons', until(lambda: page.locator('#today-card .swap').is_visible()))
            page.click('#today-card #btn-swap')
            page.click('#today-card #btn-delete-day')
            check('Delete workout asks first', until(lambda: page.locator('#delete-day-go').is_visible()))
            page.keyboard.press('Escape')
            page.evaluate("() => { const e = document.querySelector('#delete-day-go'); const d = e && e.closest('[role=alertdialog], .ydlg, .confirm'); const k = d && d.querySelector('.confirm-keep, button:not(#delete-day-go)'); if (k) k.click(); }"); page.wait_for_timeout(300)
            page.click('#today-card #btn-look')
            check('Look back or correct opens the workout', until(lambda: page.is_visible('#sb-day')))
            if TD.weekday() > 0:
                page.click('#sb-back'); page.wait_for_selector('#today-card .t-head')
                page.click('#wk-rows .wk-blk >> nth=%d' % (TD.weekday() - 1))
                check('an earlier day in the week still has Look back or correct and Delete', until(lambda: page.locator('#wk-sheet .wk-open').count() == 1 and page.locator('#wk-sheet .wk-del').count() == 1), page.inner_text('#wk-sheet'))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors', not errs, errs)

        # without Claude: three buttons, the last one across
        be = Backend(); seed(be)
        def s2(page):
            page.set_viewport_size({'width': 390, 'height': 844})
            page.wait_for_selector('#today-card .t-head', timeout=8000); page.wait_for_timeout(500)
            check('no Claude button without a connected app', page.locator('#btn-claude-day').count() == 0)
            a, d = page.evaluate(BOX, '#today-card #btn-look'), page.evaluate(BOX, '#today-card #btn-delete-day')
            check('three buttons: the odd one takes the whole row', d['w'] > a['w'] * 1.8 and d['y'] > a['y'], (a, d))
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (no Claude)', not errs, errs)
finally:
    server.terminate()
done()
