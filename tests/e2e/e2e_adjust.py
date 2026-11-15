"""Fix my plan through Adjust my plan: the request says the real schedule (a rotation with repeats, sessions a week) and asks for
only the listed changes with the targets kept; applying keeps the rotation's repeats and the date of every target that did not change."""
import re, json, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
TODAY = TD.isoformat()
OLD = '2026-10-01'
EX = {'bench': ('Barbell bench press', 'Chest'), 'row': ('Seated cable row', 'Back'), 'squat': ('Squat', 'Legs'), 'curl': ('Alternating dumbbell curl', 'Arms')}
DAYS = {'day-a': ('Day A', [('bench', '60'), ('row', '50')]), 'day-b': ('Day B', [('squat', '80')]), 'day-c': ('Day C', [('curl', '10'), ('row', '50')])}

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'profile': {'experience': 'some', 'session_length': 'medium', 'days_per_week': 4, 'where': 'gym'},
                                           'schedule': {'enabled': True, 'mode': 'rotation', 'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], 'per_week': 3, 'rotation': ['day-a', 'day-b', 'day-a', 'day-c']}}})
    for k, (nm, g) in EX.items():
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    for i, (tid, (nm, items)) in enumerate(DAYS.items()):
        be.docs.append({'path': 'yc/templates/' + tid, 'data': {'name': nm, 'order': i, 'kind': 'Other', 'focus': '', 'items': [
            {'ex': ex, 'order': j + 1, 'sets': 3, 'reps': '8 to 12', 'target': t, 'target_at': OLD, 'rest_s': 120, 'note': None} for j, (ex, t) in enumerate(items)]}})

ANSWER = {'summary': 'Adds a hinge to Day B.', 'weekdays': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], 'days': [
    {'name': 'Day A', 'kind': 'Other', 'focus': '', 'items': [{'ex': 'l04', 'sets': 3, 'reps': '8 to 12', 'target': '60', 'rest_s': 120, 'note': None}, {'ex': 'l14', 'sets': 3, 'reps': '8 to 12', 'target': '50', 'rest_s': 120, 'note': None}]},
    {'name': 'Day B', 'kind': 'Legs', 'focus': '', 'items': [{'ex': 'l42', 'sets': 3, 'reps': '8 to 12', 'target': '85', 'rest_s': 150, 'note': None}, {'ex': 'l50', 'sets': 3, 'reps': '8 to 12', 'target': '', 'rest_s': 120, 'note': None}]},
    {'name': 'Day C', 'kind': 'Other', 'focus': '', 'items': [{'ex': 'l30', 'sets': 3, 'reps': '8 to 12', 'target': '10', 'rest_s': 120, 'note': None}, {'ex': 'l14', 'sets': 3, 'reps': '8 to 12', 'target': '50', 'rest_s': 120, 'note': None}]}]}

def doc(be, path): return next((d['data'] for d in reversed(be.docs) if d['path'] == path), None)
def item(be, tid, ex): return next((it for it in (doc(be, 'yc/templates/' + tid) or {}).get('items', []) if it['ex'] == ex), {})

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            page.route('**/config.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=re.sub(r"planCheckOnly: \[[^\]]*\]", "planCheckOnly: ['alice@example.com']", r.fetch().text(), count=1)))
            page.goto(BASE); page.wait_for_selector('#today-card', timeout=8000)
            page.click('#tab-plan'); page.wait_for_selector('#plan-check', timeout=8000)
            card = page.locator('#plan-check').inner_text()
            check('the check counts Day A twice in 4 slots at 3 a week: chest 4.5 sets', 'No hinge' in card, card)
            page.click('#pc-mus-tog'); page.wait_for_timeout(200)
            chest = page.locator('#plan-check .pc-mus li', has_text='Chest').locator('b').inner_text()
            check('chest: 3 sets x 2 of 4 slots x 3 a week = 4.5', chest == '4.5', chest)
            page.click('#pc-fix'); page.wait_for_selector('#wz-adjust', timeout=5000)
            page.click('#wz-go')
            check('web: the paste step', until(lambda: page.is_visible('#wz-answer'), 5))
            page.locator('#wiz .ex-acts .skew').first.click(); page.wait_for_timeout(300)
            req = page.evaluate('navigator.clipboard.readText()')
            check('request: the rotation with its repeats', 'then start again: Day A, Day B, Day A, Day C. About 3 sessions a week' in req, req[:1500])
            check('request: sessions a week from the schedule, the profile number named', 'Sessions a week: 3 in their schedule (their profile says 4)' in req)
            check('request: only the listed changes, targets kept', 'Change only what the list under' in req and 'copy its current target as it is' in req)
            check('request: no split rule, no coach line, no mapping', 'Split for' not in req and 'Coach me' not in req and '"mapping"' not in req)
            page.fill('#wz-answer', json.dumps(ANSWER))
            page.locator('#wiz .foot-row .skew').first.click()
            check('preview', until(lambda: page.is_visible('#wz-start'), 5))
            page.click('#wz-start')
            root = lambda: doc(be, 'yc') or {}
            check('applied', until(lambda: str(item(be, 'day-b', 'squat').get('target')) == '85' and root().get('schedule_before'), 8))
            check('applied: the rotation keeps Day A twice', root()['schedule'].get('rotation') == ['day-a', 'day-b', 'day-a', 'day-c'], root()['schedule'].get('rotation'))
            check('applied: 3 a week kept', root()['schedule'].get('per_week') == 3, root()['schedule'])
            check('an unchanged target keeps its date', item(be, 'day-a', 'bench').get('target_at') == OLD, item(be, 'day-a', 'bench'))
            check('a changed target gets today', item(be, 'day-b', 'squat').get('target_at') == TODAY and str(item(be, 'day-b', 'squat').get('target')) == '85', item(be, 'day-b', 'squat'))
            check('the new hinge is in Day B', any(it['ex'] not in EX for it in doc(be, 'yc/templates/day-b')['items']), doc(be, 'yc/templates/day-b')['items'])
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors', not errs, errs)
finally:
    server.terminate()
done()
