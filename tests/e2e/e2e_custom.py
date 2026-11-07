"""Custom workout, run tracking, the month schedule, your own foods, and the desktop top padding."""
import subprocess, time, datetime, calendar
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today()
T = TODAY.isoformat()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TODAY.weekday()]

def seed(be, show_cal=True):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': show_cal}}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = {'ex': 'bench', 'order': 1, 'sets': 2, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None}
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': WD, 'items': [it]}})

def doc(be, path): return next((d['data'] for d in be.docs if d['path'] == path), None)
def docs_under(be, prefix): return [d for d in be.docs if d['path'].startswith(prefix)]

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. a custom workout with a run
        be = Backend(); seed(be)
        def s1(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('#btn-swap')
            check('the change panel offers a custom workout', page.is_visible('#swap-custom') and 'Starts blank' in page.inner_text('#swap-custom'))
            page.click('#swap-custom')
            check('it asks for a name', page.is_visible('#custom-name') and page.is_visible('#custom-go'))
            page.fill('#custom-name', '8k run'); page.click('#custom-go')
            page.wait_for_selector('#sb-day', state='visible')
            check('the session opens under that name, blank', page.text_content('#sb-day') == '8k run' and page.locator('#session .ex').count() == 0, page.text_content('#sb-day'))
            tpl = doc(be, 'yc/templates/custom-' + T)
            check('a hidden day is saved behind it', tpl is not None and tpl.get('adhoc') is True and tpl['name'] == '8k run' and tpl['items'] == [], tpl)
            page.click('text=+ Add exercise'); page.fill('.pk-search', 'outdoor run')
            page.locator('.pk-item:has-text("Outdoor run") .pk-go').first.click()
            page.wait_for_selector('#f-outdoor-run_1-minutes', state='visible')
            check('a run asks for minutes, distance and altitude', all(page.is_visible('#f-outdoor-run_1-' + f) for f in ('minutes', 'km', 'elev')))
            check('outside is the default for an outdoor run', page.get_attribute('.run-where button[data-w="outdoor"]', 'aria-pressed') == 'true')
            page.fill('#f-outdoor-run_1-minutes', '40'); page.fill('#f-outdoor-run_1-km', '8'); page.fill('#f-outdoor-run_1-elev', '120')
            check('the pace is worked out: 40 min over 8 km is 5:00 /km', until(lambda: '5:00 /km' in page.inner_text('.run-pace')), page.inner_text('.run-pace'))
            page.fill('#f-outdoor-run_1-km', '8,5')
            check('a decimal comma works', until(lambda: '4:42 /km' in page.inner_text('.run-pace')), page.inner_text('.run-pace'))
            page.fill('#f-outdoor-run_1-km', '8')
            page.click('.run-where button[data-w="treadmill"]')
            check('treadmill can be picked', page.get_attribute('.run-where button[data-w="treadmill"]', 'aria-pressed') == 'true' and page.get_attribute('.run-where button[data-w="outdoor"]', 'aria-pressed') == 'false')
            page.locator('.set .set-tick').first.click()
            sess = lambda: (doc(be, 'yc/sessions/' + T) or {}).get('sets', {}).get('outdoor-run_1')
            check('the set is saved with distance, altitude and where', until(lambda: (sess() or {}).get('km') == 8), sess())
            st = sess() or {}
            check('minutes 40, altitude 120, treadmill', st.get('minutes') == 40 and st.get('elev') == 120 and st.get('where') == 'treadmill' and st.get('done') is True, st)
            check('the session belongs to the custom day', (doc(be, 'yc/sessions/' + T) or {}).get('template') == 'custom-' + T)
            # correct the distance after the tick
            page.fill('#f-outdoor-run_1-km', '10')
            check('a done set can be corrected', until(lambda: (sess() or {}).get('km') == 10), sess())
            page.click('.run-where button[data-w="outdoor"]')
            check('and where it was changed', until(lambda: (sess() or {}).get('where') == 'outdoor'), sess())
            page.click('#sb-back'); page.wait_for_selector('#pickday', state='visible')
            check('the custom day is done today', 'Done: 8k run' in page.text_content('#today-card'), page.text_content('#today-card'))
            page.click('.mainnav [data-view="plan"]')
            page.wait_for_timeout(500)
            check('and it is not a training day in the plan', '8k run' not in page.inner_text('#v-plan'))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (custom workout)', not errs, errs)

        # ---- 1b. last time's distance comes back, finish ends on Train
        be = Backend(); seed(be)
        be.docs.append({'path': 'yc/exercises/treadmill-run', 'data': {'name': 'Treadmill run', 'group': 'Other', 'category': 'cardio', 'unit': 'min', 'better': 'higher', 'library_id': 'l289'}})
        past = (TODAY - datetime.timedelta(days=3)).isoformat()
        be.docs.append({'path': 'yc/sessions/' + past, 'data': {'date': past, 'template': 'push', 'sets': {'treadmill-run_1': {'ex': 'treadmill-run', 'n': 1, 'kind': 'work', 'minutes': 30, 'km': 5, 'elev': 20, 'where': 'treadmill', 'done': True, 'at': 1}}}})
        def s1b(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('#btn-swap'); page.click('#swap-custom'); page.click('#custom-go')
            page.wait_for_selector('#sb-day', state='visible')
            check('a blank name falls back to Custom workout', page.text_content('#sb-day') == 'Custom workout', page.text_content('#sb-day'))
            page.click('text=+ Add exercise'); page.fill('.pk-search', 'treadmill run'); page.locator('.pk-item:has-text("Treadmill run") .pk-go').first.click()
            page.wait_for_selector('#f-treadmill-run_1-km', state='visible')
            check('last time fills distance and minutes', page.input_value('#f-treadmill-run_1-km') == '5' and page.input_value('#f-treadmill-run_1-minutes') == '30' and page.input_value('#f-treadmill-run_1-elev') == '20', [page.input_value('#f-treadmill-run_1-' + f) for f in ('minutes', 'km', 'elev')])
            check('and the treadmill stays picked', page.get_attribute('.run-where button[data-w="treadmill"]', 'aria-pressed') == 'true')
            page.locator('.set .set-tick').first.click(); page.wait_for_timeout(300)
            page.locator('button.skew:visible', has_text='Finish day').first.click()
            page.wait_for_selector('.fin', timeout=5000)
            page.click('#fin-done')
            check('finishing lands on the Train screen', until(lambda: page.is_visible('#pickday') and page.locator('.fin').count() == 0))
        errs = session(pw, be, ALICE, s1b, width=390); check('no page errors (run again)', not errs, errs)

        # ---- 2. the month schedule and the calendar button
        be = Backend(); seed(be)
        def s2(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            days = calendar.monthrange(TODAY.year, TODAY.month)[1]
            check('the month shows below the calendar button', page.is_visible('#month') and page.locator('#mo-grid .mo-blk').count() == days, page.locator('#mo-grid .mo-blk').count())
            order = page.evaluate("(() => { const a = document.querySelector('#btn-cal').getBoundingClientRect().top, m = document.querySelector('#month').getBoundingClientRect().top; return a < m; })()")
            check('Add to calendar sits above it as the main button', order and 'pop' in page.get_attribute('#btn-cal', 'class') and 'big' in page.get_attribute('#btn-cal', 'class'))
            check('today is marked and planned', page.locator('#mo-grid .mo-blk.is-today').count() == 1 and '•' in page.inner_text('#mo-grid .mo-blk.is-today'))
            check('a planned weekday repeats through the month', page.locator('#mo-grid .mo-blk:has-text("•")').count() >= days // 7, page.locator('#mo-grid .mo-blk:has-text("•")').count())
            title = page.inner_text('#h-month')
            page.click('#mo-next')
            ny, nm = (TODAY.year + (TODAY.month == 12), TODAY.month % 12 + 1)
            check('next month changes the grid', page.inner_text('#h-month') != title and page.locator('#mo-grid .mo-blk').count() == calendar.monthrange(ny, nm)[1])
            page.click('#mo-prev'); page.click('#mo-prev')
            check('and back', page.locator('#mo-grid .mo-blk').count() == calendar.monthrange(TODAY.year - (TODAY.month == 1), (TODAY.month - 2) % 12 + 1)[1])
            page.click('#mo-next')
            first = page.locator('#mo-grid .mo-blk').first
            first.click()
            check('a day in the month opens its week above', until(lambda: page.get_attribute('#wk-rows .wk-blk[aria-pressed="true"]', 'data-date') == TODAY.replace(day=1).isoformat()), page.get_attribute('#wk-rows .wk-blk[aria-pressed="true"]', 'data-date'))
            page.click('#btn-cal')
            check('the calendar panel opens', page.is_visible('#cal-panel') and page.get_attribute('#btn-cal', 'aria-expanded') == 'true')
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (month)', not errs, errs)

        # ---- 3. your own foods
        be = Backend(); seed(be)
        be.docs.append({'path': 'yc/myfoods/own-bad', 'data': {'food': 'own:bad', 'name': 'Broken thing', 'own': 'nope'}})
        def s3(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-body', state='visible', timeout=8000)
            page.click('#fd-custom')
            check('the create card opens, per 100', page.is_visible('#fd-own-name') and page.is_visible('#fd-unit') and 'per 100 g' in page.inner_text('#fd-per'))
            page.fill('#fd-own-name', 'Oat drink'); page.select_option('#fd-unit', 'ml')
            check('the unit changes the note', 'per 100 ml' in page.inner_text('#fd-per'))
            page.fill('#fd-kcal', '46'); page.fill('#fd-p', '60'); page.fill('#fd-c', '40'); page.fill('#fd-f', '30'); page.click('#fd-add')
            check('numbers that cannot be right are refused', 'cannot be more than 100' in page.inner_text('#fd-msg'), page.inner_text('#fd-msg'))
            page.fill('#fd-p', ''); page.click('#fd-add')
            check('a missing number is refused', 'protein' in page.inner_text('#fd-msg'), page.inner_text('#fd-msg'))
            page.fill('#fd-p', '1'); page.fill('#fd-c', '6.7'); page.fill('#fd-f', '1.5'); page.click('#fd-add')
            check('saved, and on to how much', until(lambda: doc(be, 'yc/myfoods/own-oat-drink') is not None and page.is_visible('#fd-g')), doc(be, 'yc/myfoods/own-oat-drink'))
            d = doc(be, 'yc/myfoods/own-oat-drink')
            check('stored per 100 ml with its key', d['food'] == 'own:oat-drink' and d['own'] == {'kcal': 46, 'p': 1, 'c': 6.7, 'f': 1.5, 'u': 'ml'} and d['name'] == 'Oat drink', d)
            page.fill('#fd-g', '250')
            check('the numbers follow the amount', until(lambda: page.input_value('#fd-kcal') == '115'), page.input_value('#fd-kcal'))
            page.click('#fd-add')
            entry = lambda: next((e for e in ((doc(be, 'yc/food/' + T) or {}).get('entries') or {}).values() if e and e.get('name') == 'Oat drink'), None)
            check('logged with its own numbers', until(lambda: entry() is not None), entry())
            e = entry() or {}
            check('as an own food, in ml', e.get('src') == 'own' and e.get('ref') == 'oat-drink' and e.get('g') == 250 and e.get('u') == 'ml' and e.get('kcal') == 115 and e.get('p') == 2.5 and e.get('c') == 16.8 and e.get('f') == 3.8, e)
            # found again by search, first, marked yours
            page.fill('#fd-name', 'oat'); until(lambda: page.locator('#fd-hits .fd-hit').count() > 0)
            first = page.locator('#fd-hits .fd-hit').first
            check('search lists it first, as yours', 'Oat drink' in first.inner_text() and 'Yours' in first.inner_text(), first.inner_text())
            check('a broken saved food is skipped', 'Broken thing' not in page.inner_text('#fd-hits'))
            check('the line shows its per-portion numbers, no per-100 text', 'per 100' not in first.inner_text())
            check('searching offers to save a new food', 'as a food to use again' in page.inner_text('#fd-hits'))
            first.click()
            page.wait_for_selector('#fd-g', state='visible')
            check('a drink starts at a glass and offers drink sizes, no guessed food sizes', page.input_value('#fd-g') == '200' and 'GLASS' in page.inner_text('#fd-amount').upper() and 'SMALL' not in page.inner_text('#fd-amount').upper(), page.inner_text('#fd-amount'))
            check('credit line says it is your own', 'Your own food' in page.inner_text('#fd-src'))
            # edit the numbers
            page.click('text=Edit this food')
            check('edit opens with the saved numbers', page.input_value('#fd-own-name') == 'Oat drink' and page.input_value('#fd-kcal') == '46' and page.input_value('#fd-unit') == 'ml')
            page.fill('#fd-kcal', '50'); page.click('#fd-add')
            check('the numbers are replaced, the name stays', until(lambda: (doc(be, 'yc/myfoods/own-oat-drink') or {}).get('own', {}).get('kcal') == 50), doc(be, 'yc/myfoods/own-oat-drink'))
            check('the old entry keeps the numbers it was logged with', (entry() or {}).get('kcal') == 115)
            page.click('text=Forget this food')
            check('forgetting marks it gone', until(lambda: (doc(be, 'yc/myfoods/own-oat-drink') or {}).get('gone') is True), doc(be, 'yc/myfoods/own-oat-drink'))
            check('the entry already logged stays', entry() is not None)
            # the new-food shortcut from a search keeps what was typed
            page.fill('#fd-name', 'grandmas soup'); until(lambda: page.locator('#fd-hits .fd-new').count() > 0)
            page.locator('#fd-hits .fd-new', has_text='as a food to use again').click()
            check('the shortcut fills in the name', page.input_value('#fd-own-name') == 'grandmas soup')
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (own food)', not errs, errs)

        # ---- 4. desktop: room at the top for the toast and the save bar
        be = Backend(); seed(be)
        def s4(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            pt = page.evaluate("parseFloat(getComputedStyle(document.querySelector('main')).paddingTop)")
            check('desktop: the page starts below the notification strip', pt >= 56, pt)
            left = page.evaluate("parseFloat(getComputedStyle(document.querySelector('#toast')).left)")
            check('desktop: the toast starts beside the sidebar, not under it', left >= 200, left)
        errs = session(pw, be, ALICE, s4, width=1280); check('no page errors (desktop)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
