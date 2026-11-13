"""Fixes from the code review: Back from a workout stays put, a failed history import retries the import, a file that cannot be read is not dropped, forgotten foods do not fill the list."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today()
T = TODAY.isoformat()
SAT = datetime.datetime(2026, 11, 7, 10, 0)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- Back from a workout is a choice: coming back to the app does not undo it
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TODAY.weekday()]
        be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [{'ex': 'bench', 'order': 1, 'sets': 2, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None}]}})
        def away(page):
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start'); page.wait_for_selector('#session:not([hidden])')
            page.click('#sb-back'); page.wait_for_selector('#session', state='hidden')
            page.evaluate("Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true }); document.dispatchEvent(new Event('visibilitychange'))")
            page.wait_for_timeout(500)
            check('back from the workout, then returning to the app: still on the week', page.is_hidden('#session') and page.is_visible('#today-card'))
            check('and the workout can be resumed', page.locator('#resume-fin, #btn-continue, .resume').count() >= 1 or page.is_visible('#btn-start'))
        errs = session(pw, be, ALICE, away, width=390); check('no page errors (away)', not errs, errs)

        # ---- a history import that stops part way retries the import, not a new plan
        rows = ['"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"']
        for day in ('5', '8', '12'):
            when = '"%s Oct 2026, 18:00"' % day
            for k in range(2):
                rows.append(','.join(['"Push"', when, when, '""', '"Bench Press (Barbell)"', '""', '""', str(k), '"normal"', '80', '5', '""', '""', '""']))
        CSV = '\n'.join(rows)
        be = Backend()
        def retry(page):
            until(lambda: page.is_visible('#wz-import')); page.click('#wz-import')
            page.get_by_role('radiogroup', name='Coming from').get_by_role('radio', name='Hevy').click()
            page.set_input_files('#wz-file', files=[{'name': 'workouts.csv', 'mimeType': 'text/csv', 'buffer': CSV.encode()}])
            until(lambda: 'workouts.csv' in page.text_content('#wiz'))
            block = {'on': True}
            page.route('**/rest/v1/**', lambda r: r.abort() if block['on'] and r.request.method != 'GET' and 'yc/sessions' in (r.request.post_data or '') + r.request.url else r.fallback())
            page.click('#wz-history')
            check('a failed import lands on the error step with Try again', until(lambda: page.get_by_role('button', name='Try again').count() == 1, 8) and page.locator('#wz-start').count() == 0, page.text_content('#wiz')[:200])
            block['on'] = False
            page.get_by_role('button', name='Try again').click()
            check('Try again finishes the import', until(lambda: 'Imported' in page.text_content('body'), 10), page.text_content('body')[:200])
            check('and does not start a plan the person skipped', page.locator('#wz-start').count() == 0)
        errs = session(pw, be, ALICE, retry, width=390, clock=SAT); check('no page errors (retry)', not errs, errs)

        # ---- a file from another app cannot be read here: it is said, not dropped
        be = Backend()
        def other(page):
            until(lambda: page.is_visible('#wz-import')); page.click('#wz-import')
            page.get_by_role('radiogroup', name='Coming from').get_by_role('radio', name='Another app').click()
            page.set_input_files('#wz-file', files=[{'name': 'x.csv', 'mimeType': 'text/csv', 'buffer': b'a,b\n1,2\n'}])
            until(lambda: 'x.csv' in page.text_content('#wiz'))
            page.click('#wz-go')
            check('Another app on the web: says it needs an AI instead of building a plan without the file', until(lambda: 'needs an AI to read it' in page.text_content('#wiz'), 6) and page.locator('#wz-start').count() == 0, page.text_content('#wiz')[:200])
        errs = session(pw, be, ALICE, other, width=390, clock=SAT); check('no page errors (other app)', not errs, errs)

        # ---- forgotten foods do not count towards the 500
        def foods(n_live, n_gone):
            be = Backend()
            be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': True}}})
            for i in range(n_live): be.docs.append({'path': 'yc/myfoods/own-f%d' % i, 'data': {'food': 'own:f%d' % i, 'name': 'Food %d' % i, 'aka': {}, 'n': 0, 'last': 0, 'portions': {}, 'own': {'kcal': 100, 'p': 5, 'c': 10, 'f': 2, 'u': 'g'}}})
            for i in range(n_gone): be.docs.append({'path': 'yc/myfoods/own-g%d' % i, 'data': {'food': 'own:g%d' % i, 'name': 'Gone %d' % i, 'gone': True}})
            return be
        def create(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-body:not([hidden])', timeout=8000)
            page.click('#fd-ownfoods > summary'); page.click('#fd-own-new'); page.fill('#fd-own-name', 'Brand new'); page.fill('#fd-kcal', '100'); page.fill('#fd-p', '5'); page.fill('#fd-c', '10'); page.fill('#fd-f', '2'); page.click('#fd-add'); page.wait_for_timeout(500)
            return page.inner_text('#fd-msg')
        res = {}
        errs = session(pw, foods(100, 450), ALICE, lambda p: res.update(a=create(p)), width=390)
        check('100 kept and 450 forgotten: a new food is allowed', 'full' not in res['a'], res['a'])
        errs = session(pw, foods(500, 0), ALICE, lambda p: res.update(b=create(p)), width=390)
        check('500 kept: the list is full', 'full' in res['b'], res['b'])
finally:
    server.terminate()
done()
