"""A finished workout can be sent to Claude any time, the question after a workout can be switched off, and exercises explain themselves."""
import subprocess, time, datetime, urllib.parse
from playwright.sync_api import sync_playwright
from harness import *

TODAY = datetime.date.today()
T = TODAY.isoformat()
def doc(be, path): return next((d['data'] for d in be.docs if d['path'] == path), None)

def seed(be, settings=None, done=True):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': settings or {}}})
    be.docs.append({'path': 'yc/exercises/legext', 'data': {'name': 'Leg extension', 'group': 'Legs', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/exercises/mine', 'data': {'name': 'My odd lift', 'group': 'Other', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/legs', 'data': {'name': 'Legs', 'order': 1, 'kind': 'Legs', 'focus': '', 'weekday': TODAY.strftime('%a'), 'items': [
        {'ex': 'legext', 'order': 1, 'sets': 3, 'reps': '10', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None},
        {'ex': 'mine', 'order': 2, 'sets': 3, 'reps': '10', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None}]}})
    if done:
        be.docs.append({'path': 'yc/sessions/' + T, 'data': {'date': T, 'template': 'legs', 'split': 'Legs', 'label': 'Legs', 'finished_at': 1, 'sets': {'legext_1': {'ex': 'legext', 'n': 1, 'order': 1, 'kind': 'work', 'reps': 10, 'load': 25, 'done': True, 'at': 1, 'unit': 'kg:total'}}}})

GRANT = [{'client': {'id': 'c-claude', 'name': 'Claude', 'uri': 'https://claude.ai'}, 'scopes': ['openid'], 'granted_at': now()}]
CATCH = "window.__opened = []; if (!window.__oc) { window.__oc = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { if (/claude\\.ai/.test(this.href)) { window.__opened.push(this.href); return; } return window.__oc.call(this); }; } 0"

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. after the question was dismissed, Send to Claude is still on the Today card and on the day
        be = Backend(); be.grants = GRANT; seed(be)
        def s1(page):
            page.wait_for_selector('#today-card .t-head', timeout=8000)
            check('the card says the day is done', 'Done' in page.text_content('#today-card .t-head'))
            check('and offers Send to Claude', until(lambda: page.is_visible('#btn-claude-day')))
            page.evaluate(CATCH); page.click('#btn-claude-day'); page.wait_for_timeout(400)
            u = page.evaluate('window.__opened[0]') or ''
            check('it opens Claude with this workout', u.startswith('https://claude.ai/new?q=') and 'Legs' in urllib.parse.unquote(u) and T in urllib.parse.unquote(u), u)
            q = urllib.parse.unquote(u.split('q=', 1)[1]) if 'q=' in u else ''
            check('the request says what to read, how to judge, how the weight moves and what to change', all(x in q for x in ('get_sessions', 'get_plan', 'get_exercise_history', 'get_notes', 'weight_step', 'save_training_day', 'answer_note', 'Do not add or remove logged sets')), q[:300])
            check('it is not asked in another language when the app is in English', 'Reply in' not in q and len(u) < 6000, len(u))
            page.click('#wk-rows .wk-blk.is-today')
            check('the same button is on that day in the week', until(lambda: page.locator('#wk-sheet .cl-day').count() == 1), page.inner_text('#wk-sheet'))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (button)', not errs, errs)

        # ---- 1b. in another language the reply is asked for in it
        be = Backend(); be.grants = GRANT; seed(be)
        def s1b(page):
            page.wait_for_selector('#today-card .t-head', timeout=8000)
            until(lambda: page.is_visible('#btn-claude-day'))
            page.evaluate(CATCH); page.click('#btn-claude-day'); page.wait_for_timeout(400)
            u = page.evaluate('window.__opened[0]') or ''
            check('Dutch: the reply is asked for in Dutch', 'Reply in Dutch.' in urllib.parse.unquote(u), urllib.parse.unquote(u)[-200:])
        errs = session(pw, be, ALICE, s1b, width=390, lang='nl'); check('no page errors (Dutch request)', not errs, errs)

        # ---- 2. no connected app, no button
        be = Backend(); be.grants = []; seed(be)
        def s2(page):
            page.wait_for_selector('#today-card .t-head', timeout=8000); page.wait_for_timeout(600)
            check('without a connected app there is no button', page.locator('#btn-claude-day').count() == 0)
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (no app)', not errs, errs)

        # ---- 3. the setting switches the question off
        be = Backend(); be.grants = GRANT; seed(be, done=False)
        def s3(page):
            page.click('#tab-settings'); page.wait_for_selector('#conn:not([hidden])', timeout=8000)
            page.locator('#v-settings section.fold').filter(has_text='Connected AI apps').locator('.set-tog').click() if page.locator('#set-claude-ask').is_hidden() else None
            check('the switch is there and on by default', until(lambda: page.is_visible('#set-claude-ask')) and page.is_checked('#set-claude-ask'))
            page.uncheck('#set-claude-ask')
            check('it is saved', until(lambda: (doc(be, 'yc') or {}).get('settings', {}).get('claude_ask') is False), doc(be, 'yc'))
            # finish a workout: no question
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: '%s', tpl: 'legs'}))" % T); page.reload(); page.wait_for_selector('#resume-fin', state='visible')
            page.click('#resume-fin')
            page.wait_for_timeout(1200)
            check('finishing an empty day asks nothing', page.locator('#claude-review-go').count() == 0)
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (setting)', not errs, errs)

        # ---- 4. an exercise explains itself, one tap away; your own exercise has nothing to explain
        be = Backend(); seed(be, done=False)
        def s4(page):
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start'); page.wait_for_selector('.set', timeout=8000); page.wait_for_timeout(400)
            check('the library exercise has How to do it, closed', page.locator('#how-legext').count() == 1 and page.get_attribute('#how-legext', 'open') is None)
            page.click('#how-legext summary')
            txt = page.inner_text('#how-legext')
            check('opening shows what it is and the muscles', 'Main' in txt and len(txt) > 60, txt)
            page.locator('.fchip', has_text='My odd lift').click(); page.wait_for_timeout(300)
            check('an exercise of your own has no How to do it', page.locator('#how-mine').count() == 0)
        errs = session(pw, be, ALICE, s4, width=390); check('no page errors (how to)', not errs, errs)
finally:
    server.terminate()
done()
