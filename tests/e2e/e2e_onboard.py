"""First run: the plan starts today or tomorrow, sessions a week are saved with it, the web goes straight to the copy-and-paste step,
the request is cut to where you train and asks for your language, and old schedules get their sessions a week once."""
import json, datetime, subprocess, time
from harness import *
from harness import EXTERNAL

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
pw = sync_playwright().start()

SAT = datetime.datetime(2026, 11, 7, 10, 0)  # a Saturday morning
PLAN = {"summary": "Three full-body days.", "weekdays": ["Mon", "Wed", "Fri"], "days": [
    {"name": "Full A", "kind": "Other", "focus": "squat, press", "items": [{"ex": "l42", "sets": 3, "reps": "8", "target": "", "rest_s": 150, "note": None}]},
    {"name": "Full B", "kind": "Other", "focus": "hinge, pull", "items": [{"ex": "l43", "sets": 3, "reps": "8", "target": "", "rest_s": 150, "note": None}]},
    {"name": "Full C", "kind": "Other", "focus": "lunge, row", "items": [{"ex": "l46", "sets": 3, "reps": "10", "target": "", "rest_s": 120, "note": None}]}]}

def root(be): return next(d['data'] for d in be.docs if d['path'] == 'yc')
def tpl(be, i): return next(d['data'] for d in be.docs if d['path'] == 'yc/templates/' + i)

def to_preview(page, ai=True):
    """Build in the app, then (ai=True) change it with your AI on the web: the paste step, with PLAN pasted back."""
    until(lambda: page.is_visible('#wz-go'))
    page.click('#wz-go')
    check('Build: a plan straight away, no paste step', until(lambda: page.is_visible('#wz-start'), 4) and not page.is_visible('#wz-answer'))
    if not ai: return
    page.click('.wz-aibox > summary')
    page.click('#wz-ai')
    check('web: the AI goes to the paste step', until(lambda: page.is_visible('#wz-answer'), 4))
    check('web: no "building" step on the way', page.locator('#wiz .wz-busy').count() == 0)
    page.fill('#wz-answer', json.dumps(PLAN))
    page.locator('#wiz .foot-row .skew').first.click()
    until(lambda: page.is_visible('#wz-start') and 'Full A' in page.text_content('#wiz'))

# ---- start today
be = Backend()
def today_run(page):
    to_preview(page)
    ch = page.get_by_role('radiogroup', name='First workout')
    check('preview: First workout, Today picked', ch.get_by_role('radio', name='Today').get_attribute('aria-checked') == 'true')
    note = page.text_content('#wiz')
    check('preview: says Full A today, then the other days', 'Full A today. Then every week on Sat, Mon, Wed' in note, note[:400])
    page.click('#wz-start')
    check('saved: Train opens on Full A today', until(lambda: page.is_visible('#btn-start') and 'Full A' in page.text_content('#btn-start')))
    check('saved: no rest day on day one', 'Rest day' not in page.text_content('#today-card'))
    check('saved: the start button is the primary one', 'pop' in page.get_attribute('#btn-start', 'class'))
    check('toast: up first today', 'up first today' in page.text_content('body'))
    sc = root(be)['schedule']
    check('schedule: Sat, Mon, Wed with 3 sessions a week', sorted(sc['days']) == sorted(['Sat', 'Mon', 'Wed']) and sc['per_week'] == 3, sc)
    check('schedule: days saved in week order', sc['days'] == ['Mon', 'Wed', 'Sat'], sc['days'])
    check('first day keeps today as its weekday', tpl(be, 'day-1')['weekday'] == 'Sat', tpl(be, 'day-1'))
    page.click('#wk-next'); page.wait_for_timeout(300)
    mon = page.get_attribute('#wk-rows .wk-blk[data-date="2026-11-09"]', 'aria-label') or ''
    wed = page.get_attribute('#wk-rows .wk-blk[data-date="2026-11-11"]', 'aria-label') or ''
    check('next week: Full B on Mon, Full C on Wed', 'Full B planned' in mon and 'Full C planned' in wed, mon + ' / ' + wed)
session(pw, be, ALICE, today_run, width=390, clock=SAT)

# ---- start tomorrow
be = Backend()
def tomorrow_run(page):
    to_preview(page)
    page.get_by_role('radiogroup', name='First workout').get_by_role('radio', name='Tomorrow').click()
    page.wait_for_timeout(200)
    check('preview: Tomorrow picked', page.get_by_role('radiogroup', name='First workout').get_by_role('radio', name='Tomorrow').get_attribute('aria-checked') == 'true')
    check('preview: Full A tomorrow', 'Full A tomorrow. Then every week on Sun, Tue, Thu' in page.text_content('#wiz'), page.text_content('#wiz')[:400])
    page.click('#wz-start')
    until(lambda: page.is_visible('#btn-start'))
    check('toast: up first tomorrow', 'up first tomorrow' in page.text_content('body'))
    sc = root(be)['schedule']
    check('schedule: Sun, Tue, Thu', sc['days'] == ['Tue', 'Thu', 'Sun'] and sc['per_week'] == 3, sc)
    check('first day on Sunday', tpl(be, 'day-1')['weekday'] == 'Sun')
session(pw, be, ALICE, tomorrow_run, width=390, clock=SAT)

# ---- the request: home exercises only, and the answer in Dutch
be = Backend()
def request_run(page):
    until(lambda: page.is_visible('#wz-go'))
    page.locator('#wiz .wz-q').nth(0).locator('[role=radio]').nth(0).click()  # 2 days a week: picks something so the profile line is not empty
    page.locator('#wiz .wz-q').nth(2).locator('[role=radio]').nth(1).click()  # where: home with dumbbells
    page.click('#wz-go')
    until(lambda: page.is_visible('#wz-start'))
    page.click('.wz-aibox > summary'); page.click('#wz-ai')
    until(lambda: page.is_visible('#wz-answer'))
    page.locator('#wiz .ex-acts .skew').first.click(); page.wait_for_timeout(300)
    req = page.evaluate('navigator.clipboard.readText()')
    lines = [l for l in req.split('\n') if l.startswith('l') and ' | ' in l]
    check('request: still lists exercises', len(lines) > 30, len(lines))
    check('request: no barbell bench press at home', not any(l.startswith('l04 |') for l in lines))
    check('request: no machine-only exercises at home', not any(l.split(' | ')[3] in ('Machine', 'Cable stack', 'Leg press') for l in lines))
    check('request: dumbbell work stays', any('Dumbbell' in l for l in lines))
    check('request: much smaller than the full list', len(lines) < 200, len(lines))
    check('request: answer in Dutch', 'in Dutch' in req)
session(pw, be, ALICE, request_run, width=390, clock=SAT, lang='nl')

# ---- old schedules get their sessions a week once, from the profile
be = Backend()
ALL = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'profile': {'days_per_week': 4}, 'schedule': {'enabled': True, 'mode': 'rotation', 'days': ALL, 'rotation': ['a', 'b']}}})
for k in ('a', 'b'): be.docs.append({'path': 'yc/templates/' + k, 'data': {'name': k.upper(), 'order': 1, 'kind': 'Other', 'items': []}})
def migrate_run(page):
    check('migration: per_week copied from the profile', until(lambda: root(be)['schedule'].get('per_week') == 4), root(be))
    check('migration: marked done', root(be).get('settings', {}).get('sched_v') == 2)
session(pw, be, ALICE, migrate_run, clock=SAT)
root(be)['profile']['days_per_week'] = 2  # About you changed later, and a connector set the schedule without per_week
root(be)['schedule'] = {'enabled': True, 'mode': 'rotation', 'days': ALL, 'rotation': ['a', 'b']}
def again_run(page):
    page.wait_for_timeout(1500)
    check('migration: runs once, so a schedule without per_week means every day given', 'per_week' not in root(be)['schedule'], root(be)['schedule'])
    page.click('#tab-plan'); page.wait_for_timeout(600)
    check('Plan: no sessions-a-week chip picked from the profile', page.locator('.pw-days[aria-label="Sessions a week"] [aria-pressed=true]').count() == 0)
session(pw, be, ALICE, again_run, clock=SAT)

be = Backend()
be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'profile': {'days_per_week': 4}, 'schedule': {'enabled': True, 'mode': 'rotation', 'days': ['Mon', 'Wed', 'Fri'], 'rotation': ['a']}}})
be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'A', 'order': 1, 'kind': 'Other', 'items': []}})
def nochange_run(page):
    until(lambda: root(be).get('settings', {}).get('sched_v') == 2)
    check('migration: more sessions than days changes nothing', 'per_week' not in root(be)['schedule'], root(be)['schedule'])
session(pw, be, ALICE, nochange_run, clock=SAT)


# ---- the plan made in the app: defaults, places, lengths
be = Backend()
def local_run(page):
    to_preview(page, ai=False)
    txt = page.text_content('#wiz')
    check('local: three full-body days by default', all(('Full body ' + x) in txt for x in 'ABC'), txt[:300])
    check('local: says the first week finds the weights', 'first week is for finding your weights' in txt)
    check('local: the AI is offered, folded away', page.is_visible('.wz-aibox > summary') and not page.is_visible('#wz-ai'))
    check('local: Start training is the main button', 'Start training' in page.text_content('#wz-start') and 'pop' in page.get_attribute('#wz-start', 'class'))
    page.click('#wz-start')
    check('local: Train opens on Full body A today', until(lambda: page.is_visible('#btn-start') and 'Full body A' in page.text_content('#btn-start')))
    t = tpl(be, 'day-1')
    check('local: about 60 minutes is 5 exercises', len(t['items']) == 5, len(t['items']))
    check('local: a calibration cue on the first loaded lift', bool(t['items'][0].get('note')), t['items'][0])
    check('local: exercises created for the plan', sum(1 for d in be.docs if d['path'].startswith('yc/exercises/')) >= 10)
    check('local: 3 sessions a week', root(be)['schedule']['per_week'] == 3)
session(pw, be, ALICE, local_run, width=390, clock=SAT)

be = Backend()
def home4_run(page):
    until(lambda: page.is_visible('#wz-go'))
    q = page.locator('#wiz .wz-q')
    q.nth(0).locator('[role=radio]').nth(2).click()   # 4 days
    q.nth(1).locator('[role=radio]').nth(0).click()   # 45 min
    q.nth(2).locator('[role=radio]').nth(1).click()   # home with dumbbells
    to_preview(page, ai=False)
    txt = page.text_content('#wiz')
    check('local: 4 days is upper and lower body', all(x in txt for x in ('Upper A', 'Lower A', 'Upper B', 'Lower B')), txt[:300])
    check('local: home has no machines or barbells', not any(w in txt for w in ('Machine', 'Leg press', 'Barbell', 'Cable', 'pulldown')), txt)
    page.click('#wz-start'); until(lambda: page.is_visible('#btn-start'))
    check('local: 45 minutes is 4 exercises', len(tpl(be, 'day-1')['items']) == 4)
    check('local: 4 sessions a week', root(be)['schedule']['per_week'] == 4 and len(root(be)['schedule']['days']) == 4)
session(pw, be, ALICE, home4_run, width=390, clock=SAT)

# ---- a Hevy export: history without any AI
HEAD = '"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"'
rows = [HEAD]
for i, day in enumerate(['5', '8', '12', '15', '19', '22']):
    when = '"%s Oct 2026, 18:00"' % day
    for k in range(3):
        rows.append(','.join(['"Push"', when, when, '""', '"Bench Press (Barbell)"', '""', '""', str(k), '"normal"', '80', '5', '""', '""', '""']))
        rows.append(','.join(['"Push"', when, when, '""', '"Squat (Barbell)"', '""', '""', str(k), '"normal"', '100', '5', '""', '""', '""']))
CSV = '\n'.join(rows)
def pick_hevy(page):
    until(lambda: page.is_visible('#wz-go'))
    page.get_by_role('radiogroup', name='Coming from').get_by_role('radio', name='Hevy').click()
    page.set_input_files('#wz-file', files=[{'name': 'workouts.csv', 'mimeType': 'text/csv', 'buffer': CSV.encode()}])
    until(lambda: 'workouts.csv' in page.text_content('#wiz'))

be = Backend()
def hevy_only(page):
    pick_hevy(page)
    check('import: Only import my history is offered', page.is_visible('#wz-history'))
    page.click('#wz-history')
    check('import: done without any AI', until(lambda: 'Imported 6 sessions' in page.text_content('body'), 6))
    ses = [d for d in be.docs if d['path'].startswith('yc/sessions/')]
    check('import: six sessions written', len(ses) == 6 and all(d['data']['source'] == 'import' for d in ses), len(ses))
    check('import: no schedule made', not (root(be).get('schedule') or {}).get('enabled'))
    check('import: setup does not come back', until(lambda: page.is_visible('#pickday')))
session(pw, be, ALICE, hevy_only, width=390, clock=SAT)

be = Backend()
def hevy_plan(page):
    pick_hevy(page)
    page.click('#wz-go')
    check('import + plan: a plan straight away', until(lambda: page.is_visible('#wz-start'), 6))
    txt = page.text_content('#wiz')
    check('import + plan: weights from the history', 'from your history' in txt, txt[:300])
    check('import + plan: bench at about 90% of the recent best', '@ 72.5 kg' in txt, txt)
    check('import + plan: says the history comes along', 'Also imports 6 sessions' in txt)
    page.click('#wz-start')
    until(lambda: page.is_visible('#btn-start'))
    check('import + plan: sessions written', until(lambda: sum(1 for d in be.docs if d['path'].startswith('yc/sessions/')) == 6))
session(pw, be, ALICE, hevy_plan, width=390, clock=SAT)

check('nothing left the machine', not EXTERNAL, EXTERNAL[:3])
pw.stop()
server.terminate()
done()
