"""The workout card: your own note stays open under the exercise, the columns are named once above the sets, last time sits in each row."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TODAY = datetime.date.today()
T = TODAY.isoformat()
PAST = (TODAY - datetime.timedelta(days=6)).isoformat()
def doc(be, path): return next((d['data'] for d in be.docs if d['path'] == path), None)

def seed(be, note=None):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {}}})
    be.docs.append({'path': 'yc/exercises/legext', 'data': dict({'name': 'Leg extension', 'group': 'Legs', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}, **({'my_note': note} if note else {}))})
    be.docs.append({'path': 'yc/exercises/pullup', 'data': {'name': 'Pull-up', 'group': 'Back', 'category': 'strength', 'unit': 'bw', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/legs', 'data': {'name': 'Legs', 'order': 1, 'kind': 'Legs', 'focus': '', 'weekday': TODAY.strftime('%a'), 'items': [
        {'ex': 'legext', 'order': 1, 'sets': 3, 'reps': '10', 'target': '', 'target_at': T, 'rest_s': 90, 'note': 'Look at the angle'},
        {'ex': 'pullup', 'order': 2, 'sets': 3, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None}]}})
    sets = {'legext_%d' % i: {'ex': 'legext', 'n': i, 'order': i, 'kind': 'work', 'reps': 10, 'load': 25, 'done': True, 'at': 0, 'unit': 'kg:total'} for i in (1, 2, 3)}
    be.docs.append({'path': 'yc/sessions/' + PAST, 'data': {'date': PAST, 'template': 'legs', 'split': 'Legs', 'label': 'Legs', 'finished_at': 1, 'sets': sets}})

def start(page):
    page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start')
    page.wait_for_selector('.set', timeout=8000); page.wait_for_timeout(500)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. a note you wrote is open under the exercise, no toggle in the way
        be = Backend(); seed(be, note='Seat on 4. Knee in line with the pivot.')
        def s1(page):
            start(page)
            check('no folded Target · Last time row any more', page.locator('.ex-dtog').count() == 0)
            ta = page.locator('#stick-legext')
            check('your note is visible without a tap', ta.is_visible() and 'Seat on 4' in ta.input_value())
            check('the note box is big enough to write in (at least 80 px)', ta.bounding_box()['height'] >= 80, ta.bounding_box())
            check('the plan cue is shown too, plainly', 'Look at the angle' in page.inner_text('.ex-tip'))
            # edit it: saved to the exercise, not to the day
            ta.fill('Seat on 4. Knee in line with the pivot. Slow down.'); page.wait_for_timeout(1200)
            check('the edit is saved on the exercise', (doc(be, 'yc/exercises/legext') or {}).get('my_note') == 'Seat on 4. Knee in line with the pivot. Slow down.', doc(be, 'yc/exercises/legext'))
            # the other exercise has none: it offers to add one, closed
            page.locator('.fchip', has_text='Pull-up').click(); page.wait_for_timeout(300)
            check('an exercise without a note offers to add one, closed', page.locator('#stick-pullup').is_hidden() and page.is_visible('#stick-add-pullup'))
            page.click('#stick-add-pullup'); page.fill('#stick-pullup', 'Full hang, chin over the bar'); page.locator('#stick-pullup').blur(); page.wait_for_timeout(600)
            check('a new note is saved on blur', (doc(be, 'yc/exercises/pullup') or {}).get('my_note') == 'Full hang, chin over the bar')
            # emptying it removes it
            page.locator('.fchip', has_text='Leg extension').click(); page.wait_for_timeout(300)
            ta.fill(''); ta.blur(); page.wait_for_timeout(600)
            check('an emptied note is cleared', (doc(be, 'yc/exercises/legext') or {}).get('my_note') in (None, ''))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (notes)', not errs, errs)

        # ---- 2. it is still there the next time, on another day
        be = Backend(); seed(be, note='Back pad on 3')
        def s2(page):
            start(page)
            check('the note is there at the next workout', 'Back pad on 3' in page.locator('#stick-legext').input_value())
            page.reload(); page.wait_for_selector('.set', timeout=8000); page.wait_for_timeout(500)
            check('and after a reload', 'Back pad on 3' in page.locator('#stick-legext').input_value())
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (kept)', not errs, errs)

        # ---- 3. columns named once, last time in the row
        be = Backend(); seed(be)
        def s3(page):
            start(page)
            heads = page.evaluate("[...document.querySelectorAll('.ex')].map((e) => [...e.querySelectorAll('.set-head span')].map((s) => s.textContent).filter(Boolean))")
            check('a kg exercise has Set, Last, Reps and kg above its rows', heads[0] == ['Set', 'Last', 'Reps', 'kg'], heads)
            check('a bodyweight exercise has no weight column', heads[1] == ['Set', 'Last', 'Reps'], heads)
            check('last time is in the row without opening anything', '10 @ 25' in page.locator('.set:has(#f-legext_1-load) .set-last').inner_text() and page.locator('.set:has(#f-legext_1-load) .set-last').is_visible())
            check('the rows no longer repeat the unit next to every field', page.evaluate("getComputedStyle(document.querySelector('.set:not(.set-head) .fld small')).fontSize") == '0px')
            check('the old Last line is gone from the caption', 'Last' not in page.inner_text('.ex-cap').replace('Last none yet', ''), page.inner_text('.ex-cap'))
            check('nothing scrolls sideways', not page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
        errs = session(pw, be, ALICE, s3, width=360); check('no page errors (headers)', not errs, errs)

        # ---- 4. the note to Claude is a bigger box
        be = Backend(); seed(be)
        def s4(page):
            start(page)
            page.locator('.ex').first.get_by_role('button', name='Note about Leg extension').click()
            page.wait_for_selector('.nt-text', state='visible'); page.wait_for_timeout(300)
            h = page.locator('.nt-text').first.bounding_box()['height']
            check('the session note box is at least 100 px tall', h >= 100, h)
        errs = session(pw, be, ALICE, s4, width=390); check('no page errors (session note)', not errs, errs)

        # ---- 5. the weight step is on the suggestion, and changing it changes the suggestion
        be = Backend(); seed(be)
        def s5(page):
            start(page)
            check('the suggestion shows its step', page.inner_text('.ex-sug-step').replace('\n', ' ').strip().lower() == 'step 2.5 kg', page.inner_text('.ex-sug-step'))
            check('it starts at the usual jump', '+2.5' in page.inner_text('.ex-sug-why'), page.inner_text('.ex-sug-why'))
            page.click('.ex-sug-step'); page.fill('#step-legext', '2.3'); page.click('.ex-stepbox button')
            check('the step is saved on the exercise', until(lambda: (doc(be, 'yc/exercises/legext') or {}).get('inc') == 2.3), doc(be, 'yc/exercises/legext'))
            check('the suggestion goes up by it', until(lambda: '+2.3' in page.inner_text('.ex-sug-why')), page.inner_text('.ex-sug-why'))
            check('the next weight is last weight plus the step', '27.3' in page.inner_text('.ex-cap'), page.inner_text('.ex-cap'))
            check('the editor closes', page.locator('.ex-stepbox').first.is_hidden())
        errs = session(pw, be, ALICE, s5, width=390); check('no page errors (step)', not errs, errs)

        # ---- 6. a new exercise can start with its own step
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        def s6(page):
            page.evaluate("document.querySelector('#tab-exercises').click()"); page.wait_for_selector('#xl-new', timeout=8000)
            page.click('#xl-new'); page.fill('#xl-f-name', 'Hack squat sled'); page.select_option('#xl-f-unit', 'kg'); page.fill('#xl-f-inc', '2.3')
            page.click('#xl-form button[type=submit]')
            check('the step is saved with the new exercise', until(lambda: any(d['path'].startswith('yc/exercises/') and d['data'].get('inc') == 2.3 for d in be.docs)), [d['data'] for d in be.docs if d['path'].startswith('yc/exercises/')])
        errs = session(pw, be, ALICE, s6, width=390); check('no page errors (new exercise step)', not errs, errs)

        # ---- 7. in German: columns, step and the note prompt are translated
        be = Backend(); seed(be)
        def s7(page):
            start(page)
            heads = page.evaluate("[...document.querySelector('.set-head').querySelectorAll('span')].map((s) => s.textContent).filter(Boolean)")
            check('German: Satz, Zuletzt, Wdh., kg', heads == ['Satz', 'Zuletzt', 'Wdh.', 'kg'], heads)
            check('German: the step reads Schritt', page.inner_text('.ex-sug-step').strip().lower().startswith('schritt 2.5'), page.inner_text('.ex-sug-step'))
            page.locator('.fchip').nth(1).click(); page.wait_for_timeout(300)
            check('German: the add-note link is translated', 'Notiz für Pull-up' in page.inner_text('#stick-add-pullup'), page.inner_text('#stick-add-pullup'))
        errs = session(pw, be, ALICE, s7, width=390, lang='de'); check('no page errors (German)', not errs, errs)
finally:
    server.terminate()
done()
