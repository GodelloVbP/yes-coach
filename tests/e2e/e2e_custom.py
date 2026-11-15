"""Custom workout, run tracking, the month schedule, your own foods, and the desktop top padding."""
import re
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
            check('the change panel offers a custom workout', page.is_visible('#swap-custom') and 'off your plan' in page.inner_text('#swap-custom'))
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
            page.click('.run-unit button[data-u="speed"]')
            check('the pace can be shown as km/h: 8 km in 40 min is 12.0 km/h', until(lambda: 'Speed 12.0 km/h' in page.inner_text('.run-pace')), page.inner_text('.run-pace'))
            check('and the choice is saved', until(lambda: ((doc(be, 'yc') or {}).get('settings') or {}).get('run_unit') == 'speed'), doc(be, 'yc'))
            page.click('.run-unit button[data-u="pace"]')
            check('and back to min/km', until(lambda: '5:00 /km' in page.inner_text('.run-pace')), page.inner_text('.run-pace'))
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
            page.click('text=+ Add exercise'); page.wait_for_timeout(200)
            check('after adding, the search starts empty again with every exercise listed', page.input_value('.pk-search') == '' and page.locator('.pk-item:visible').count() > 20, page.input_value('.pk-search'))
            check('rows take turns in each group: white, then cream', page.evaluate("(() => { const out = []; let cur = null; [...document.querySelectorAll('.pk-list > *')].forEach((e) => { if (e.classList.contains('pk-gh')) { cur = []; out.push(cur); } else if (cur && e.classList.contains('pk-item') && !e.hidden) cur.push(e.classList.contains('alt')); }); const g = out.find((x) => x.length >= 3); return !!g && g[0] === false && g[1] === true && g[2] === false; })()"))
            page.click('.pk-top .link')
            page.locator('.set .set-tick').first.click(); page.wait_for_timeout(300)
            page.wait_for_timeout(900); page.locator('button.skew:visible', has_text=re.compile(r'^\s*Finish', re.I)).first.click()
            page.wait_for_selector('.fin', timeout=5000)
            page.click('#fin-done')
            check('finishing lands on the Train screen', until(lambda: page.is_visible('#pickday') and page.locator('.fin').count() == 0))
        errs = session(pw, be, ALICE, s1b, width=390); check('no page errors (run again)', not errs, errs)

        # ---- 1c. every custom workout is new; a started one shows in the week and can be continued or deleted
        be = Backend(); seed(be)
        def s1c(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('#btn-swap'); page.click('#swap-custom'); page.fill('#custom-name', 'First'); page.click('#custom-go')
            page.wait_for_selector('#sb-day', state='visible')
            check('the day record exists from the start', until(lambda: (doc(be, 'yc/sessions/' + T) or {}).get('template') == 'custom-' + T), doc(be, 'yc/sessions/' + T))
            page.click('#sb-back'); page.wait_for_selector('#pickday', state='visible')
            check('the Today card offers to continue it', page.is_visible('#btn-continue') and 'First' in page.text_content('#btn-continue'))
            blk = page.locator('#wk-rows .wk-blk.is-today')
            check('it shows in the week as in progress', '…' in blk.inner_text() and 'in progress' in blk.get_attribute('aria-label'), blk.get_attribute('aria-label'))
            check('and in the month', '…' in page.inner_text('#mo-grid .mo-blk.is-today'))
            check('the day sheet has Continue and Delete workout', page.locator('#wk-sheet .wk-open:has-text("Continue")').count() == 1 and page.locator('#wk-sheet .wk-del').count() == 1)
            page.click('#wk-sheet .wk-open:has-text("Continue")'); page.wait_for_selector('#sb-day', state='visible')
            check('Continue goes back into that workout', page.text_content('#sb-day') == 'First')
            page.click('#sb-back'); page.wait_for_selector('#pickday', state='visible')
            # a second custom workout is a new one
            page.click('#btn-swap'); page.click('#swap-custom'); page.fill('#custom-name', 'Second'); page.click('#custom-go')
            page.wait_for_selector('#sb-day', state='visible')
            check('a second custom workout is a new one, not the first again', page.text_content('#sb-day') == 'Second' and (doc(be, 'yc/templates/custom-' + T + '-2') or {}).get('name') == 'Second' and doc(be, 'yc/templates/custom-' + T)['name'] == 'First', [d['path'] for d in be.docs if 'custom' in d['path']])
            check('with its own day record', until(lambda: (doc(be, 'yc/sessions/' + T + '~custom-' + T + '-2') or {}).get('template') == 'custom-' + T + '-2'), [d['path'] for d in be.docs if 'sessions' in d['path']])
            # delete it from the session menu
            page.click('#sb-more'); page.click('#m-delete')
            check('deleting asks first', page.is_visible('#delete-day-go') and 'Delete Second' in page.inner_text('.ydlg'), page.inner_text('.ydlg'))
            page.click('.ydlg >> text=Keep')
            check('Keep leaves it alone', page.locator('.ydlg').count() == 0 and doc(be, 'yc/templates/custom-' + T + '-2') is not None)
            page.click('#sb-more'); page.click('#m-delete'); page.click('#delete-day-go')
            check('it lands on Train', until(lambda: page.is_visible('#pickday')))
            check('the day and its hidden template are gone', until(lambda: doc(be, 'yc/templates/custom-' + T + '-2') is None and doc(be, 'yc/sessions/' + T + '~custom-' + T + '-2') is None), [d['path'] for d in be.docs if 'custom' in d['path']])
            check('the first one is untouched', doc(be, 'yc/templates/custom-' + T) is not None and doc(be, 'yc/sessions/' + T) is not None)
            check('a toast says so, with Undo', until(lambda: 'Second deleted' in page.text_content('#toast-text') and page.is_visible('#toast-undo')))
            page.click('#toast-undo')
            check('Undo brings it back', until(lambda: doc(be, 'yc/templates/custom-' + T + '-2') is not None and doc(be, 'yc/sessions/' + T + '~custom-' + T + '-2') is not None), [d['path'] for d in be.docs if 'custom' in d['path']])
            # delete the first from the week
            page.click('#wk-rows .wk-blk.is-today'); page.click('#wk-sheet .wk-del >> nth=0'); page.click('#delete-day-go')
            check('deleting from the week works too', until(lambda: doc(be, 'yc/templates/custom-' + T) is None and doc(be, 'yc/sessions/' + T) is None), [d['path'] for d in be.docs if 'custom' in d['path']])
        errs = session(pw, be, ALICE, s1c, width=390); check('no page errors (custom days)', not errs, errs)

        # ---- 2. the month schedule and the calendar button
        be = Backend(); seed(be)
        def s2(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            days = calendar.monthrange(TODAY.year, TODAY.month)[1]
            check('the month shows below the calendar button', page.is_visible('#month') and page.locator('#mo-grid .mo-blk').count() == days, page.locator('#mo-grid .mo-blk').count())
            order = page.evaluate("(() => { const a = document.querySelector('#btn-cal').getBoundingClientRect().top, m = document.querySelector('#month').getBoundingClientRect().top; return a < m; })()")
            check('Add to calendar sits above it as a big outlined button', order and 'pop' not in page.get_attribute('#btn-cal', 'class') and 'big' in page.get_attribute('#btn-cal', 'class'))
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
            check('Your own foods starts folded, with only its heading showing', page.is_visible('#h-fd-own') and not page.is_visible('#fd-own-new') and page.get_attribute('#fd-ownfoods', 'open') is None)
            page.click('#fd-ownfoods > summary')
            check('the Food page has a Your own foods section with a Create button', page.is_visible('#fd-ownfoods') and page.is_visible('#fd-own-new') and 'Nothing saved yet' in page.inner_text('#fd-own-list'))
            check('and no Claude button while Claude is not connected', not page.is_visible('#fd-own-claude'))
            page.click('#fd-own-new')
            check('the create card opens, per 100', page.is_visible('#fd-own-name') and page.is_visible('#fd-unit') and 'per 100 g' in page.inner_text('#fd-per'))
            page.fill('#fd-own-name', 'Oat drink'); page.select_option('#fd-unit', 'ml')
            check('the unit changes the note', 'per 100 ml' in page.inner_text('#fd-per'))
            check('and every number says what it is per', 'Calories (kcal) per 100 ml' in page.text_content('label:has(#fd-kcal)') and 'Protein (g) per 100 ml' in page.text_content('label:has(#fd-p)'), page.text_content('label:has(#fd-kcal)'))
            page.fill('#fd-kcal', '46'); page.fill('#fd-p', '60'); page.fill('#fd-c', '40'); page.fill('#fd-f', '30'); page.click('#fd-add')
            check('numbers that cannot be right are refused', 'cannot be more than 100' in page.inner_text('#fd-msg'), page.inner_text('#fd-msg'))
            page.fill('#fd-p', ''); page.click('#fd-add')
            check('a missing number is refused', 'protein' in page.inner_text('#fd-msg'), page.inner_text('#fd-msg'))
            page.fill('#fd-p', '1'); page.fill('#fd-c', '6.7'); page.fill('#fd-f', '1.5'); page.click('#fd-add')
            check('saved, and on to how much', until(lambda: doc(be, 'yc/myfoods/own-oat-drink') is not None and page.is_visible('#fd-g')), doc(be, 'yc/myfoods/own-oat-drink'))
            check('the card says it is saved and what to do next', 'Saved' in page.text_content('#fd-card-title') and 'Cancel' in page.text_content('#fd-card-title'), page.text_content('#fd-card-title'))
            check('it is listed under Your own foods', until(lambda: 'Oat drink' in page.inner_text('#fd-own-list')) and 'per 100 ml' in page.inner_text('#fd-own-list'), page.inner_text('#fd-own-list'))
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
            check('searching offers to save a new food, and to log one once', 'as your own food' in page.inner_text('#fd-hits') and 'once' in page.inner_text('#fd-hits'))
            check('the two say what they do', 'Not saved.' in page.inner_text('#fd-hits') and 'Saved for next time.' in page.inner_text('#fd-hits'))
            first.click()
            page.wait_for_selector('#fd-g', state='visible')
            check('a drink starts at a glass and offers drink sizes, no guessed food sizes', page.input_value('#fd-g') == '200' and 'GLASS' in page.inner_text('#fd-amount').upper() and 'SMALL' not in page.inner_text('#fd-amount').upper(), page.inner_text('#fd-amount'))
            check('credit line says it is your own', 'Your own food' in page.inner_text('#fd-src'))
            # the list under Your own foods
            page.click('#fd-cancel'); page.wait_for_timeout(300)
            page.click('#fd-own-list .fd-own-row >> text=Log it')
            check('Log it in the list opens the amount', until(lambda: page.is_visible('#fd-g')) and 'Oat drink' in page.text_content('#fd-card-title'))
            page.click('#fd-cancel'); page.wait_for_timeout(300)
            page.fill('#fd-name', 'oat'); until(lambda: page.locator('#fd-hits .fd-hit').count() > 0)
            page.locator('#fd-hits .fd-hit').first.click(); page.wait_for_selector('#fd-g', state='visible')
            # edit the numbers
            page.click('text=Edit this food')
            check('edit opens with the saved numbers', page.input_value('#fd-own-name') == 'Oat drink' and page.input_value('#fd-kcal') == '46' and page.input_value('#fd-unit') == 'ml')
            page.fill('#fd-kcal', '50'); page.click('#fd-add')
            check('the numbers are replaced, the name stays', until(lambda: (doc(be, 'yc/myfoods/own-oat-drink') or {}).get('own', {}).get('kcal') == 50), doc(be, 'yc/myfoods/own-oat-drink'))
            check('the old entry keeps the numbers it was logged with', (entry() or {}).get('kcal') == 115)
            page.click('#fd-cancel'); page.wait_for_timeout(300)
            page.click('#fd-own-list .fd-own-row >> text=Delete')
            check('forgetting marks it gone', until(lambda: (doc(be, 'yc/myfoods/own-oat-drink') or {}).get('gone') is True), doc(be, 'yc/myfoods/own-oat-drink'))
            check('and takes it off the list', until(lambda: 'Oat drink' not in page.inner_text('#fd-own-list')), page.inner_text('#fd-own-list'))
            page.click('#toast-undo')
            check('Undo puts it back', until(lambda: (doc(be, 'yc/myfoods/own-oat-drink') or {}).get('gone') is None and 'Oat drink' in page.inner_text('#fd-own-list')))
            check('the entry already logged stays', entry() is not None)
            # the new-food shortcut from a search keeps what was typed
            page.fill('#fd-name', 'grandmas soup'); until(lambda: page.locator('#fd-hits .fd-save').count() > 0)
            page.locator('#fd-hits .fd-save').click()
            check('the shortcut fills in the name', page.input_value('#fd-own-name') == 'grandmas soup')
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (own food)', not errs, errs)

        # ---- 3a. a food Claude looked up shows where its numbers came from
        be = Backend(); seed(be)
        be.docs.append({'path': 'yc/myfoods/own-skyr', 'data': {'food': 'own:skyr', 'name': 'Skyr vanille', 'aka': {}, 'n': 0, 'last': 0, 'portions': {}, 'own': {'kcal': 63, 'p': 11, 'c': 4, 'f': 0.2, 'u': 'g'}, 'source': 'https://www.example.nl/producten/skyr'}})
        be.docs.append({'path': 'yc/myfoods/own-pasta', 'data': {'food': 'own:pasta', 'name': 'Pasta sauce', 'aka': {}, 'n': 0, 'last': 0, 'portions': {}, 'own': {'kcal': 60, 'p': 1.5, 'c': 9, 'f': 2, 'u': 'g'}, 'source': 'javascript:alert(1)'}})
        def s3a(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-own-list .fd-own-row', state='attached', timeout=8000)
            check('the folded heading counts your foods', page.inner_text('#fd-own-count') == '2', page.inner_text('#fd-own-count'))
            page.click('#fd-ownfoods > summary')
            row = page.locator('#fd-own-list .fd-own-row', has_text='Skyr vanille')
            a = row.locator('a')
            check('the source is a link to the page', a.count() == 1 and a.get_attribute('href') == 'https://www.example.nl/producten/skyr' and a.text_content() == 'example.nl', a.count())
            check('it opens in a new tab without handing over the page', a.get_attribute('target') == '_blank' and 'noopener' in a.get_attribute('rel') and 'noreferrer' in a.get_attribute('rel'))
            check('the row says Source', 'Source: example.nl' in row.text_content(), row.text_content())
            odd = page.locator('#fd-own-list .fd-own-row', has_text='Pasta sauce')
            check('a source that is not a web address is shown as text, never a link', odd.locator('a').count() == 0 and 'javascript:alert(1)' in odd.text_content(), odd.text_content())
            row.get_by_text('Edit').click()
            check('edit opens', until(lambda: page.input_value('#fd-own-name') == 'Skyr vanille'))
            page.click('#fd-add'); page.wait_for_timeout(500)
            check('saving with the same numbers keeps the source', (doc(be, 'yc/myfoods/own-skyr') or {}).get('source') == 'https://www.example.nl/producten/skyr', doc(be, 'yc/myfoods/own-skyr'))
            page.click('#fd-cancel'); page.wait_for_timeout(300)
            page.locator('#fd-own-list .fd-own-row', has_text='Skyr vanille').get_by_text('Edit').click()
            until(lambda: page.input_value('#fd-own-name') == 'Skyr vanille')
            page.fill('#fd-kcal', '70'); page.click('#fd-add')
            check('new numbers typed by hand drop the old source', until(lambda: (doc(be, 'yc/myfoods/own-skyr') or {}).get('own', {}).get('kcal') == 70 and 'source' not in (doc(be, 'yc/myfoods/own-skyr') or {})), doc(be, 'yc/myfoods/own-skyr'))
        errs = session(pw, be, ALICE, s3a, width=390); check('no page errors (source)', not errs, errs)

        # ---- 3b. with Claude connected, a food can be added by asking it
        be = Backend(); seed(be); be.grants = [{'client': {'id': 'c-claude', 'name': 'Claude', 'uri': 'https://claude.ai'}, 'scopes': [], 'granted_at': now()}]
        def s3b(page):
            page.evaluate("window.__opened = []; window.__oc = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { if (/claude\\.ai/.test(this.href)) { window.__opened.push(this.href); return; } return window.__oc.call(this); }; 0")
            page.click('#tab-food'); page.wait_for_selector('#fd-body', state='visible', timeout=8000)
            page.click('#fd-ownfoods > summary')
            check('Add with Claude shows once Claude is connected', until(lambda: page.is_visible('#fd-own-claude')))
            page.click('#fd-own-claude'); page.wait_for_timeout(400)
            u = page.evaluate('window.__opened[0]') or ''
            import urllib.parse
            q = urllib.parse.unquote(u)
            check('it opens Claude with a request that asks for the numbers per 100 g or ml', u.startswith('https://claude.ai/new?q=') and 'per 100 g or per 100 ml' in q and 'connector' in q, u)
            check('the request lets Claude look the product up and name the page', 'Look up' in q and 'tell me where you found them' in q and 'source' in q and 'ask me for the ones on the package' in q, q)
        errs = session(pw, be, ALICE, s3b, width=390, home=True); check('no page errors (ask Claude)', not errs, errs)

        # ---- 5. the schedule: ticked weekdays are days you CAN train; sessions a week decides how many are used
        ALL = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'profile': {'days_per_week': 4}, 'schedule': {'enabled': True, 'mode': 'rotation', 'days': ALL, 'rotation': ['a', 'b', 'c', 'd']}}})
        for i, n in enumerate('abcd'):
            be.docs.append({'path': 'yc/templates/' + n, 'data': {'name': 'Day ' + n.upper(), 'order': i + 1, 'kind': 'Other', 'focus': '', 'items': []}})
        def s5(page):
            page.goto(BASE); page.wait_for_selector('#wk-rows .wk-blk', timeout=8000)
            def planned_next(k=1):
                for _ in range(k): page.click('#wk-next')
                page.wait_for_timeout(200)
                n = page.locator('#wk-rows .wk-blk:has-text("•")').count()
                for _ in range(k): page.click('#wk-prev')
                return n
            check('all seven days ticked, 4 sessions a week from the set-up: next week has 4 training days, not 7', planned_next(1) == 4, planned_next(1))
            check('and the week after that too', planned_next(2) == 4, planned_next(2))
            page.click('#wk-next'); names = [page.get_attribute('#wk-rows .wk-blk >> nth=%d' % i, 'aria-label') for i in range(7)]; page.click('#wk-prev')
            used = [n for n in names if 'planned' in n]
            check('the days used are spread out, not a block of four in a row', all(not ('planned' in names[i] and 'planned' in names[i + 1] and 'planned' in names[i + 2]) for i in range(5)), names)
            check('the four days are used in order', len(set(n.split(', ')[-1] for n in used)) == 4, used)
            page.click('.mainnav [data-view="plan"]'); page.wait_for_selector('.pw-set', timeout=5000)
            check('Plan says Days you can train and has Workouts a week', 'Days you can train' in page.text_content('.pw-set') and 'Workouts a week' in page.text_content('.pw-set'))
            chips = page.locator('.pw-days[aria-label="Workouts a week"] .pk-chip')
            check('the set-up value is selected', chips.count() == 7 and page.get_attribute('.pw-days[aria-label="Workouts a week"] .pk-chip >> nth=3', 'aria-pressed') == 'true')
            check('and it explains the spread', 'spread over your 7 days' in page.text_content('.pw-per-note'), page.text_content('.pw-per-note'))
            page.click('.pw-days[aria-label="Workouts a week"] .pk-chip >> nth=4')
            check('picking 5 saves it', until(lambda: ((doc(be, 'yc') or {}).get('schedule') or {}).get('per_week') == 5), (doc(be, 'yc') or {}).get('schedule'))
            check('the days you can train stay as they were', ((doc(be, 'yc') or {}).get('schedule') or {}).get('days') == ALL)
            page.click('.mainnav [data-view="train"]'); page.wait_for_selector('#wk-rows .wk-blk')
            check('next week now has 5', planned_next(1) == 5, planned_next(1))
            page.click('.mainnav [data-view="plan"]'); page.wait_for_selector('.pw-set')
            page.click('.pw-days[aria-label="Workouts a week"] .pk-chip >> nth=6')
            page.click('.mainnav [data-view="train"]'); page.wait_for_selector('#wk-rows .wk-blk')
            check('7 sessions a week uses every day', planned_next(1) == 7, planned_next(1))
            # fewer days than sessions is said, not guessed
            page.click('.mainnav [data-view="plan"]'); page.wait_for_selector('.pw-set')
            for w in ('Sat', 'Sun', 'Fri'): page.click('.pw-days[aria-label="Days you train"] .pk-chip:has-text("%s")' % w)
            check('too few days for the sessions: it says so', 'Pick more days or fewer workouts' in page.text_content('.pw-per-note'), page.text_content('.pw-per-note'))
        errs = session(pw, be, ALICE, s5, width=390); check('no page errors (schedule)', not errs, errs)

        # ---- 6. switching tabs must not move or resize the page: one content column, and a fade instead of a slide
        COL = "() => { const v = document.querySelector('.view:not([hidden])'); const e = [...v.querySelectorAll('.in')].find((n) => n.getBoundingClientRect().width > 0 && !n.closest('[hidden]')); const r = e.getBoundingClientRect(); return { left: Math.round(r.left), width: Math.round(r.width), dx: v.style.getPropertyValue('--dx'), dy: v.style.getPropertyValue('--dy') }; }"
        for width in (390, 768, 1000, 1280):
            be = Backend(); seed(be)
            def s6(page, width=width):
                page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
                cols = {}
                for v in ('plan', 'progress', 'food', 'settings', 'train'):  # Train last: its first load plays its own entrance once
                    page.click(('.mainnav [data-view="%s"]' if width < 1024 else '#tab-%s') % v); page.wait_for_timeout(350)
                    cols[v] = page.evaluate(COL)
                if width < 1024:
                    check('%d: every tab has the same content column' % width, len({(c['left'], c['width']) for c in cols.values()}) == 1, cols)
                else:
                    ref = {(cols[v]['left'], cols[v]['width']) for v in ('train', 'plan', 'food', 'settings')}
                    check('%d: the tabs beside the sidebar share one column; Progress may be wider but starts further left, never right' % width, len(ref) == 1 and cols['progress']['left'] <= cols['train']['left'], cols)
                check('%d: a tab switch is a fade, not a slide' % width, all(c['dx'] in ('0px', '') and c['dy'] in ('0px', '') for c in cols.values()), cols)
                check('%d: no sideways overflow on any tab' % width, page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
            errs = session(pw, be, ALICE, s6, width=width); check('no page errors (tabs %d)' % width, not errs, errs)

        # ---- 4. the message bar never covers the page: it is a row of the top bar at every width, and its X closes it
        SHOW = "document.getElementById('toast-text').textContent = 'Saved.'; document.getElementById('toast').hidden = false; 0"
        MEASURE = "(() => { const t = document.getElementById('toast').getBoundingClientRect(); const c = document.querySelector('#today-card').getBoundingClientRect(); return { tb: t.bottom, tl: t.left, ct: c.top, pos: getComputedStyle(document.getElementById('toast')).position }; })()"
        for width, name in ((1280, 'desktop'), (900, 'tablet'), (390, 'phone')):
            be = Backend(); seed(be)
            def s4(page, name=name):
                page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
                before = page.evaluate("document.querySelector('#today-card').getBoundingClientRect().top")
                page.evaluate(SHOW); page.wait_for_timeout(200)
                r = page.evaluate(MEASURE)
                h = page.evaluate("document.getElementById('toast').getBoundingClientRect().height")
                check(name + ': the message bar is part of the page, not over it', r['pos'] == 'static' and r['ct'] >= r['tb'], r)
                check(name + ': the page moves down by the bar, nothing is covered', abs((r['ct'] - before) - h) < 3, (before, h, r))
                if name == 'desktop': check('desktop: it starts beside the sidebar, not under it', r['tl'] >= 200, r)
                page.click('#toast-x'); page.wait_for_timeout(100)
                check(name + ': the X closes the message', page.is_hidden('#toast'))
                # a real message while scrolled (a workout taken off the week): the page moves down by the bar instead of going under it
                page.click('#wk-sheet .wk-remove'); page.wait_for_timeout(150)
                page.evaluate("document.body.append(Object.assign(document.createElement('div'), { style: 'height: 3000px' })); window.scrollTo(0, 300)"); page.wait_for_timeout(150)
                page.evaluate("[...document.querySelectorAll('#wk-sheet button')].find((b) => b.textContent.trim() === 'Remove').click()"); page.wait_for_timeout(250)
                sy = page.evaluate("window.scrollY")
                check(name + ': a message while scrolled moves the page down by the bar (the scroll does not grow)', page.is_visible('#toast') and sy <= 302, sy)  # without the fix the scroll grows by the bar's height
            errs = session(pw, be, ALICE, s4, width=width); check('no page errors (' + name + ')', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
