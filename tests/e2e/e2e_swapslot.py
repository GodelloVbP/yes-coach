"""Changing a place in the rotation to another workout, and spreading a workout that now comes twice in a row. Removing a workout takes it out of the week."""
import subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

EX = {'squat': ('Squat', 'Legs'), 'bench': ('Bench press', 'Chest')}

def seed(be, order=('legs', 'upper', 'legs')):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'schedule': {'enabled': True, 'mode': 'rotation', 'days': ['Mon', 'Wed', 'Fri'], 'per_week': 3, 'rotation': list(order)}}})
    for k, (nm, g) in EX.items():
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    for i, (tid, nm, ex) in enumerate((('legs', 'Legs', 'squat'), ('upper', 'Upper', 'bench'), ('core', 'Core', 'bench'))):
        be.docs.append({'path': 'yc/templates/' + tid, 'data': {'name': nm, 'order': i, 'kind': 'Other', 'focus': '', 'items': [
            {'ex': ex, 'order': 1, 'sets': 3, 'reps': '8 to 12', 'target': '', 'target_at': '2026-10-01', 'rest_s': 90, 'note': None}]}})

def sched(be): return next(d['data'] for d in reversed(be.docs) if d['path'] == 'yc')['schedule']

def plan(page):
    page.goto(BASE); page.wait_for_selector('#today-card', timeout=8000)
    page.click('.mainnav [data-view="plan"]'); page.wait_for_selector('.pw-board .pw-card', timeout=6000); page.wait_for_timeout(300)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            plan(page)
            check('Legs, Upper, Legs: nothing to spread', page.locator('#pw-repeat').count() == 0)
            page.select_option('select[aria-label="Change number 1 in your order to another day"]', 'upper')
            check('the first place is now Upper', until(lambda: sched(be)['rotation'] == ['upper', 'upper', 'legs']), sched(be))
            check('3 a week and the days are kept', sched(be)['per_week'] == 3 and sched(be)['days'] == ['Mon', 'Wed', 'Fri'])
            check('it says Upper comes twice in a row', until(lambda: page.locator('#pw-repeat').count() == 1 and 'Upper comes twice in a row' in page.inner_text('#pw-repeat')), page.locator('#pw-repeat').count())
            page.click('#pw-repeat button')
            check('one tap spreads them: Upper, Legs, Upper', until(lambda: sched(be)['rotation'] == ['upper', 'legs', 'upper']), sched(be))
            check('the note is gone', until(lambda: page.locator('#pw-repeat').count() == 0))
            check('and it can be undone from the message', page.is_visible('#toast-undo') and 'Order is now Upper, Legs, Upper' in page.text_content('#toast-text'), page.text_content('#toast-text'))
            page.click('#toast-undo')
            check('undo puts the order back', until(lambda: sched(be)['rotation'] == ['upper', 'upper', 'legs']), sched(be))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (swap)', not errs, errs)

        be = Backend(); seed(be, order=('legs', 'legs', 'upper', 'upper'))
        def s2(page):
            plan(page)
            check('two pairs: both named', 'Legs and Upper come twice in a row' in page.inner_text('#pw-repeat'), page.inner_text('#pw-repeat'))
            page.click('#pw-repeat button')
            check('legs, upper, legs, upper', until(lambda: sched(be)['rotation'] == ['legs', 'upper', 'legs', 'upper']), sched(be))
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (pairs)', not errs, errs)

        be = Backend(); seed(be, order=('legs', 'legs'))
        def s3(page):
            plan(page)
            check('nothing to spread with one workout: no note', page.locator('#pw-repeat').count() == 0)
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (single)', not errs, errs)

        be = Backend(); seed(be)
        def s4(page):
            plan(page)
            page.click('button[aria-label="Edit Upper"]'); page.wait_for_selector('#ed-delete', timeout=5000)
            page.click('#ed-delete'); page.wait_for_selector('#ed-delete.pop'); page.click('#ed-delete')
            check('deleting a workout takes it out of the order', until(lambda: sched(be)['rotation'] == ['legs', 'legs']), sched(be))
        errs = session(pw, be, ALICE, s4, width=390); check('no page errors (delete)', not errs, errs)

        be = Backend(); seed(be, order=('upper', 'upper', 'legs'))
        def s5(page):
            plan(page)
            note = page.inner_text('#pw-repeat')
            check('Dutch: the note is translated', 'twee keer achter elkaar' in note and 'Spreid ze' in note, note)
            check('Dutch: the change select is translated', 'Wijzig naar' in page.locator('.pw-board select').first.inner_text(), page.locator('.pw-board select').first.inner_text())
        errs = session(pw, be, ALICE, s5, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
