"""Training days a week is one number. With a schedule it comes from the plan: About you shows it (not editable) and the stored profile
follows it, so the plan, About you and a connected AI never give two numbers. Without a schedule About you is the place to set it."""
import subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

ALL = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
EX = {'bench': ('Bench press', 'Chest'), 'row': ('Barbell row', 'Back')}

def seed(be, schedule, profile_days=4):
    root = {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'profile': {'experience': 'some', 'session_length': 'medium', 'days_per_week': profile_days, 'where': 'gym'}}
    if schedule: root['schedule'] = schedule
    be.docs.append({'path': 'yc', 'data': root})
    for k, (nm, g) in EX.items():
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    for i, tid in enumerate(('day-a', 'day-b')):
        be.docs.append({'path': 'yc/templates/' + tid, 'data': {'name': tid.title(), 'order': i, 'kind': 'Other', 'focus': '', 'items': [
            {'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '8 to 12', 'target': '', 'target_at': '2026-10-01', 'rest_s': 90, 'note': None}]}})

def root(be): return next(d['data'] for d in reversed(be.docs) if d['path'] == 'yc')

def about(page):
    page.goto(BASE); page.wait_for_selector('#today-card', timeout=8000)
    page.click('#tab-settings'); page.wait_for_selector('#me-days_per_week', state='attached', timeout=6000)
    if not page.locator('#me-days_per_week').is_visible():
        page.locator('#v-settings section.fold').filter(has=page.locator('#me-fields')).locator('.set-tog').click()
    page.wait_for_selector('#me-days_per_week', state='visible'); page.wait_for_timeout(300)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # 1. the schedule says 5 a week, About you said 4: both say 5 now, and About you cannot be set apart from the plan
        be = Backend(); seed(be, {'enabled': True, 'mode': 'rotation', 'days': ALL, 'per_week': 5, 'rotation': ['day-a', 'day-b']})
        def s1(page):
            about(page)
            check('About you shows the plan\'s 5, not its own 4', page.input_value('#me-days_per_week') == '5', page.input_value('#me-days_per_week'))
            check('and cannot be changed there', page.locator('#me-days_per_week').is_disabled())
            check('it says where to change it', 'Follows your plan' in page.locator('.ed-f:has(#me-days_per_week)').inner_text(), page.locator('.ed-f:has(#me-days_per_week)').inner_text())
            check('the stored profile was brought in line (an AI reads it)', until(lambda: root(be)['profile'].get('days_per_week') == 5), root(be)['profile'])
            check('the rest of the profile is kept', root(be)['profile'].get('experience') == 'some' and root(be)['profile'].get('where') == 'gym')
            # changing it in the plan moves both
            page.click('.mainnav [data-view="plan"]'); page.wait_for_selector('.pw-set', timeout=5000)
            page.click('.pw-days[aria-label="Workouts a week"] .pk-chip >> nth=2')
            check('picking 3 in Plan saves 3 in the profile as well', until(lambda: root(be)['schedule'].get('per_week') == 3 and root(be)['profile'].get('days_per_week') == 3), (root(be)['schedule'], root(be)['profile']))
            page.click('#tab-settings'); page.wait_for_timeout(400)
            check('About you follows', page.input_value('#me-days_per_week') == '3', page.input_value('#me-days_per_week'))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (schedule)', not errs, errs)

        # 2. a fixed week counts the days that have a workout
        be = Backend(); seed(be, {'enabled': True, 'mode': 'fixed', 'week': {'Mon': 'day-a', 'Wed': 'day-b', 'Fri': 'day-a', 'Tue': '', 'Thu': '', 'Sat': '', 'Sun': ''}}, profile_days=6)
        def s2(page):
            about(page)
            check('fixed week with 3 workout days: 3', page.input_value('#me-days_per_week') == '3', page.input_value('#me-days_per_week'))
            check('and the profile says 3', until(lambda: root(be)['profile'].get('days_per_week') == 3), root(be)['profile'])
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (fixed)', not errs, errs)

        # 3. no schedule: About you is where it is set, and it saves
        be = Backend(); seed(be, None)
        def s3(page):
            about(page)
            check('without a schedule the field is yours', page.locator('#me-days_per_week').is_enabled() and page.input_value('#me-days_per_week') == '4')
            page.select_option('#me-days_per_week', '5')
            check('and saves', until(lambda: root(be)['profile'].get('days_per_week') == 5), root(be)['profile'])
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (none)', not errs, errs)

        # 4. Dutch note
        be = Backend(); seed(be, {'enabled': True, 'mode': 'rotation', 'days': ALL, 'per_week': 5, 'rotation': ['day-a', 'day-b']})
        def s4(page):
            about(page)
            check('Dutch: the note is translated', 'Volgt je schema' in page.locator('.ed-f:has(#me-days_per_week)').inner_text(), page.locator('.ed-f:has(#me-days_per_week)').inner_text())
        errs = session(pw, be, ALICE, s4, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
