"""Quieter Food trends, shorter Progress notes, honest suggestions, and a workout that shows one Finish button."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today()
iso = lambda n: (TODAY - datetime.timedelta(days=n)).isoformat()
T, BACK3 = iso(0), iso(3)

def doc(be, path): return next((d['data'] for d in be.docs if d['path'] == path), None)

def seed(be, show_cal=True, history=True):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': show_cal}}})
    for ex, nm, g in (('bench', 'Bench press', 'Chest'), ('row', 'Row', 'Back'), ('curl', 'Curl', 'Arms')):
        be.docs.append({'path': 'yc/exercises/' + ex, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = lambda ex, o, n: {'ex': ex, 'order': o, 'sets': n, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None}
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TODAY.weekday()]
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [it('bench', 1, 3), it('row', 2, 2), it('curl', 3, 2)]}})
    if history:
        for k in (3, 10, 17):
            d = iso(k)
            be.docs.append({'path': 'yc/sessions/' + d, 'data': {'date': d, 'template': 'push', 'sets': {'bench_%d' % n: {'ex': 'bench', 'n': n, 'kind': 'work', 'reps': 8, 'load': 60 + k, 'done': True, 'at': n} for n in (1, 2, 3)}}})

def food_on(be, days_ago, **e):
    d = iso(days_ago)
    be.docs.append({'path': 'yc/food/' + d, 'data': {'date': d, 'entries': {'a': dict({'name': 'Rice', 'at': 1}, **e)}}})

TRENDS = "(() => { const v = (s) => { const e = document.querySelector(s); return !!e && !e.hidden && e.getClientRects().length > 0; }; const sec = document.querySelector('#fd-range').closest('section'); return { range: v('#fd-range'), sum: v('#fd-sum'), metric: v('#fd-metric'), note: v('#fd-chart-note'), chart: v('#fd-chart'), take: document.querySelector('#fd-take').hidden ? '' : document.querySelector('#fd-take').textContent, height: Math.round(sec.getBoundingClientRect().height) }; })()"

def add_food(page):
    page.click('#fd-own-new'); page.fill('#fd-own-name', 'Rice'); page.fill('#fd-kcal', '130'); page.fill('#fd-p', '3'); page.fill('#fd-c', '28'); page.fill('#fd-f', '0.3'); page.click('#fd-add')
    until(lambda: page.is_visible('#fd-g')); page.fill('#fd-g', '200'); page.click('#fd-add')

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 6. Food trends
        be = Backend(); seed(be, history=False)
        def f1(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-body:not([hidden])', timeout=8000); page.wait_for_timeout(400)
            r = page.evaluate(TRENDS)
            check('no food at all: one note, nothing else', r['take'] == 'Log food to see your trends.' and not (r['range'] or r['sum'] or r['metric'] or r['note'] or r['chart']), r)
            check('and no blank chart-sized region', r['height'] < 120, r)
            add_food(page)
            check('after logging food the chart is back', until(lambda: page.evaluate(TRENDS)['chart']), page.evaluate(TRENDS))
            r = page.evaluate(TRENDS)
            check('with its period control, summary and note, and no leftover message', r['range'] and r['sum'] and r['note'] and r['take'] == '', r)
        errs = session(pw, be, ALICE, f1, width=390); check('no page errors (food, empty)', not errs, errs)

        be = Backend(); seed(be, history=False); food_on(be, 150, kcal=200, p=10, c=20, f=5)
        def f2(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-body:not([hidden])', timeout=8000); page.wait_for_timeout(400)
            r = page.evaluate(TRENDS)
            check('food only outside this period: says so and keeps the period control', r['take'] == 'No food logged in this period.' and r['range'] and not (r['sum'] or r['chart'] or r['note'] or r['metric']), r)
            page.locator('#fd-range .seg-b', has_text='All').click()
            check('a longer period brings the chart back', until(lambda: page.evaluate(TRENDS)['chart']) and page.evaluate(TRENDS)['take'] == '', page.evaluate(TRENDS))
            page.locator('#fd-range .seg-b', has_text='1M').click()
            r = page.evaluate(TRENDS)
            check('and back to the short period hides it again, without stale pieces', r['take'] == 'No food logged in this period.' and not (r['sum'] or r['chart'] or r['note']), r)
        errs = session(pw, be, ALICE, f2, width=390); check('no page errors (food, other period)', not errs, errs)

        be = Backend(); seed(be, history=False); food_on(be, 2, p=20)
        def f3(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-body:not([hidden])', timeout=8000); page.wait_for_timeout(400)
            r = page.evaluate(TRENDS)
            check('calories on but food without them: says so and keeps the period control', r['take'] == 'No nutrient values available for this period.' and r['range'] and not (r['sum'] or r['chart']), r)
            page.click('#tab-settings'); page.wait_for_selector('#set-cal', state='attached'); page.evaluate("(() => { const c = document.querySelector('#set-cal'); c.checked = false; c.dispatchEvent(new Event('change', { bubbles: true })); })()"); page.wait_for_timeout(300)
            page.click('#tab-food'); page.wait_for_timeout(400)
            r = page.evaluate(TRENDS)
            check('calories off: the protein shows and the message is gone', r['chart'] and r['sum'] and r['take'] == '', r)
            page.click('#tab-settings'); page.evaluate("(() => { const c = document.querySelector('#set-cal'); c.checked = true; c.dispatchEvent(new Event('change', { bubbles: true })); })()"); page.wait_for_timeout(300)
            page.click('#tab-food'); page.wait_for_timeout(400)
            check('calories on again: the message returns, nothing stale', page.evaluate(TRENDS)['take'] == 'No nutrient values available for this period.' and not page.evaluate(TRENDS)['chart'], page.evaluate(TRENDS))
        errs = session(pw, be, ALICE, f3, width=390); check('no page errors (food, calorie mode)', not errs, errs)

        # ---- 7. Progress notes
        be = Backend(); seed(be)
        def p1(page):
            page.click('#tab-progress'); page.wait_for_selector('#plist .prow', timeout=8000); page.wait_for_timeout(500)
            check('lift list note', page.inner_text('#plist-note').startswith('Best set per workout. Tap a lift for details.'), page.inner_text('#plist-note'))
            check('training days note, without the orange border line', 'training day' in page.inner_text('#days-note') and 'orange' not in page.inner_text('#days-note') and page.inner_text('#days-note').endswith('.'), page.inner_text('#days-note'))
            check('the legend is still there', page.locator('#days-legend').count() == 1 and page.inner_text('#days-legend').strip() != '', page.inner_text('#days-legend'))
            w = page.inner_text('#weekly-note')
            check('volume note names the unit once, and says how to see sessions', w.startswith('Working sets by body part, ') and ('Sessions per ' in w or 'Tap a bar for sessions.' in w) and len(w.split('. ')) <= 2, w)
        errs = session(pw, be, ALICE, p1, width=390); check('no page errors (progress)', not errs, errs)
        def p2(page):
            page.click('#tab-progress'); page.wait_for_selector('#plist .prow', timeout=8000); page.wait_for_timeout(500)
            check('German: lift list note', page.inner_text('#plist-note').startswith('Bester Satz pro Training. Tippe auf eine Übung für Details.'), page.inner_text('#plist-note'))
            check('German: volume note', page.inner_text('#weekly-note').startswith('Arbeitssätze nach Körperpartie, '), page.inner_text('#weekly-note'))
            check('German: training days note', 'Trainingstag' in page.inner_text('#days-note'), page.inner_text('#days-note'))
        errs = session(pw, be, ALICE, p2, width=390, lang='de'); check('no page errors (progress, German)', not errs, errs)

        # ---- 8. suggestions
        be = Backend(); be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        def r1(page):
            page.evaluate("document.querySelector('#tab-exercises').click()"); page.wait_for_selector('#xr-note', state='attached'); page.wait_for_timeout(400)
            check('no basis: says when suggestions appear', page.text_content('#xr-note') == 'Suggestions appear after you log workouts or create a plan.', page.text_content('#xr-note'))
        errs = session(pw, be, ALICE, r1, width=390); check('no page errors (suggestions, no basis)', not errs, errs)
        be = Backend(); seed(be)
        def r2(page):
            page.evaluate("document.querySelector('#tab-exercises').click()"); page.wait_for_selector('#xr-note', state='attached'); page.wait_for_timeout(500)
            note = page.text_content('#xr-note')
            check('with a basis: one plain line', note in ('Suggestions based on your last 4 weeks.', 'Suggestions based on your plan.', 'No suggestions based on your last 4 weeks.', 'No suggestions based on your plan.'), note)
            body = page.text_content('#v-exercises')
            for bad in ('you know your body best', 'Nice.', 'You like', 'might like'):
                check('gone: ' + bad, bad not in body, body[:200])
            whys = page.locator('.xr-why').all_text_contents()
            check('reasons are factual', whys and all(w.startswith(('No ', 'Little ', 'Alternative to ')) for w in whys), whys)
        errs = session(pw, be, ALICE, r2, width=390); check('no page errors (suggestions)', not errs, errs)

        # ---- 9. the workout
        def day(page):
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start'); page.wait_for_selector('#sess-chips', state='attached'); page.wait_for_timeout(400)
        be = Backend(); seed(be)
        def w1(page):
            day(page)
            check('phone, one at a time: the bar has Finish', page.is_visible('#focusbar') and page.is_visible('#focus-finish'))
            check('and the footer does not repeat it, nor its note', page.locator('.sess-foot .fin-row').is_hidden())
            check('the next button says Next exercise, not a long name', page.text_content('#focus-next').strip() == 'Next exercise')
            check('the destination is in the tab strip', 'Row' in page.locator('.fchip').nth(1).text_content())
            page.click('#focus-toggle')
            check('all exercises: no bar, and the footer has Finish and its note', page.is_hidden('#focusbar') and page.locator('.sess-foot .fin-row').is_visible() and 'Ticked sets are already saved' in page.inner_text('.sess-foot .fin-row') and page.locator('.sess-foot .fin-row button').inner_text().strip().lower() == 'finish day')
            page.click('#focus-toggle')
            check('back to one at a time: the footer Finish hides again', page.locator('.sess-foot .fin-row').is_hidden())
            check('the workout note and Copy workout are named plainly', 'Workout note' in page.text_content('.sess-foot') and page.locator('.sess-foot button', has_text='Copy workout').count() == 1 and 'Copy day' not in page.text_content('.sess-foot') and 'Session note for Coach' not in page.text_content('.sess-foot'))
            check('no sentence on who to paste it to', 'trainer' not in page.text_content('.sess-foot') and page.locator('.sess-foot .copy-msg, .sess-foot [aria-live="polite"]').count() >= 1)
            page.locator('.sess-foot button', has_text='Copy workout').click()
            check('copying still reports in the same live status', until(lambda: page.evaluate("[...document.querySelectorAll('.sess-foot [aria-live=polite]')].some(e => e.textContent.trim().length > 0)")), page.inner_text('.sess-foot'))
        errs = session(pw, be, ALICE, w1, width=390); check('no page errors (workout, phone)', not errs, errs)
        def w2(page):
            day(page)
            check('desktop: no focus bar, the footer has Finish', page.is_hidden('#focusbar') and page.locator('.sess-foot .fin-row').is_visible())
        errs = session(pw, be, ALICE, w2, width=1280); check('no page errors (workout, desktop)', not errs, errs)
        def w3(page):
            day(page)
            check('German: the next button is one complete accessible name', page.get_attribute('#focus-next', 'aria-label') == 'Nächste Übung: Row' and page.text_content('#focus-next').strip() == 'Nächste Übung', page.get_attribute('#focus-next', 'aria-label'))
            check('German: the button text fits its box', page.evaluate("(() => { const b = document.querySelector('#focus-next'); const s = b.querySelector('span'); return s.scrollWidth <= s.clientWidth + 1; })()"))
        errs = session(pw, be, ALICE, w3, width=360, lang='de'); check('no page errors (workout, German)', not errs, errs)
finally:
    server.terminate()
done()
