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

def to_preview(page):
    until(lambda: page.is_visible('#wz-go'))
    page.click('#wz-go')
    check('web: Build goes straight to the paste step', until(lambda: page.is_visible('#wz-answer'), 4))
    check('web: no "building" step on the way', page.locator('#wiz .wz-busy').count() == 0)
    page.fill('#wz-answer', json.dumps(PLAN))
    page.locator('#wiz .foot-row .skew').first.click()
    until(lambda: page.is_visible('#wz-start'))

# ---- start today
be = Backend()
def today_run(page):
    to_preview(page)
    ch = page.get_by_role('radiogroup', name='First workout')
    check('preview: First workout, Today picked', ch.get_by_role('radio', name='Today').get_attribute('aria-checked') == 'true')
    note = page.text_content('#wiz')
    check('preview: says Full A today, then the other days', 'Full A today, then Mon, Wed each week' in note, note[:400])
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
    check('preview: Full A tomorrow', 'Full A tomorrow, then Tue, Thu each week' in page.text_content('#wiz'), page.text_content('#wiz')[:400])
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

check('nothing left the machine', not EXTERNAL, EXTERNAL[:3])
pw.stop()
server.terminate()
done()
