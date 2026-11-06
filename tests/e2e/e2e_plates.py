"""The plate calculator: a Plates button on barbell exercises, the plates for a load, the nearest loads, the bar, and the settings."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today().isoformat()
def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.docs.append({'path': 'yc/exercises/row', 'data': {'name': 'Barbell row', 'library_id': 'l092', 'group': 'Back', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/exercises/crl', 'data': {'name': 'My own curl', 'group': 'Arms', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = lambda ex, o: {'ex': ex, 'order': o, 'sets': 2, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    be.docs.append({'path': 'yc/templates/pull', 'data': {'name': 'Pull day', 'order': 1, 'kind': 'Pull', 'focus': 'Back', 'weekday': wd, 'items': [it('row', 1), it('crl', 2)]}})

def root(be): return next(d['data'] for d in be.docs if d['path'] == 'yc')

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            page.goto(BASE); page.wait_for_selector('text=Start Pull day', timeout=8000); page.click('text=Start Pull day')
            page.wait_for_selector('#f-row_1-load', state='visible')
            check('a barbell exercise has a Plates button', page.locator('.ex:not(.off) .ex-plates').count() == 1)
            page.fill('#f-row_1-load', '100')
            page.click('.ex-plates')
            check('the panel opens with the typed load', page.is_visible('#plates-row') and page.input_value('#pl-total-row') == '100', page.input_value('#pl-total-row'))
            sides = lambda: [t.strip() for t in page.locator('#plates-row .pl-p').all_text_contents()]
            check('100 kg on the 20 kg bar: 25 and 15 a side', sides() == ['25', '15'], sides())
            check('it states the sum', '100 kg' in page.text_content('#plates-row'), page.text_content('#plates-row'))
            page.fill('#pl-total-row', '61')
            check('61 kg cannot be built and says so', until(lambda: 'Cannot build' in page.text_content('#plates-row')), page.text_content('#plates-row'))
            check('it offers the nearest loads', page.locator('#plates-row .pl-near button').count() == 2)
            page.click('#plates-row .pl-near button >> nth=0')
            check('Use sets the load on the set', page.input_value('#f-row_1-load') == '60', page.input_value('#f-row_1-load'))
            check('and the panel shows the plates for it', sides() == ['20'], sides())
            page.click('#plates-row .pl-bars button >> text=15 kg')
            check('a lighter bar changes the plates', until(lambda: sides() == ['20', '2.5']) and '15 kg bar' in page.text_content('#plates-row'), sides())
            page.fill('#pl-total-row', '10')
            check('lighter than the bar is said', until(lambda: 'lighter than' in page.text_content('#plates-row')), page.text_content('#plates-row'))
            # the other exercise is not a barbell
            page.click('.fchip >> nth=1')
            check('an exercise that is not a barbell has no button', page.locator('#plates-crl').count() == 0)
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (plates)', not errs, errs)

        be = Backend(); seed(be)
        def s2(page):
            page.goto(BASE); page.wait_for_selector('#tab-settings'); page.click('#tab-settings')
            page.wait_for_selector('#h-pref'); 
            if page.get_attribute('#h-pref ~ * , #h-pref', 'aria-expanded') is None: pass
            sec = page.locator('section:has(#h-pref) .set-tog')
            if sec.get_attribute('aria-expanded') != 'true': sec.click()
            page.wait_for_selector('#set-bar', state='visible')
            check('settings list the seven plates', page.locator('#set-plates input[type=checkbox]').count() == 7)
            check('all are on by default', page.locator('#set-plates input:checked').count() == 7)
            page.select_option('#set-bar', '15')
            check('the bar is saved', until(lambda: (root(be).get('settings') or {}).get('plate_bar') == 15), root(be))
            page.uncheck('#set-plates input[value="25"]')
            check('plates are saved', until(lambda: (root(be).get('settings') or {}).get('plates') == [20, 15, 10, 5, 2.5, 1.25]), root(be))
            page.click('#tab-train'); page.wait_for_selector('text=Start Pull day'); page.click('text=Start Pull day')
            page.wait_for_selector('#f-row_1-load', state='visible')
            page.fill('#f-row_1-load', '95'); page.click('.ex-plates')
            sides = [t.strip() for t in page.locator('#plates-row .pl-p').all_text_contents()]
            check('settings drive the calculator: 95 kg, 15 kg bar, no 25s', sides == ['20', '20'], sides)
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (settings)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
