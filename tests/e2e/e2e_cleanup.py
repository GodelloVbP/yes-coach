"""The design clean-up: no wallpaper, shorter Train copy with calmer buttons, and Food with the log ahead of the setup."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today()
T = TODAY.isoformat()
DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
WD, OTHER = DAYS[TODAY.weekday()], DAYS[(TODAY.weekday() + 3) % 7]

def seed(be, root=None, weekday=None):
    be.docs.append({'path': 'yc', 'data': dict({'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_calories': True}}, **(root or {}))})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = {'ex': 'bench', 'order': 1, 'sets': 2, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None}
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': weekday or WD, 'items': [it]}})

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. Train
        be = Backend(); seed(be)
        def s1(page):
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            check('no wallpaper behind the pages', page.evaluate("getComputedStyle(document.body, '::after').content") == 'none')
            check('the week hint is one short line', page.inner_text('#wk-hint') == 'Tap a day for details. Drag to reschedule.', page.inner_text('#wk-hint'))
            check('Add to calendar is outlined, not the main button', 'pop' not in page.get_attribute('#btn-cal', 'class'))
            check('today keeps the one coral action', 'pop' in page.get_attribute('#btn-start', 'class'))
            page.click('#wk-rows .wk-blk.is-today')
            check('the day sheet still starts the day', page.locator('#wk-sheet .wk-start').count() == 1)
            check('the sheet button is outlined', 'pop' not in page.get_attribute('#wk-sheet .wk-start', 'class'))
            check('Move to and Remove session are still there', page.locator('#wk-sheet .wk-mv').count() == 1 and page.locator('#wk-sheet .wk-remove').count() == 1)
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (train)', not errs, errs)

        be = Backend(); seed(be, weekday=OTHER)
        def s1b(page):
            page.goto(BASE); page.wait_for_selector('#today-card .t-head', timeout=8000)
            card = page.text_content('#today-card')
            check('a rest day says so in two short lines', 'Rest day' in card and 'No workout planned today.' in card and 'Train anyway' not in card and 'Pick any day below' not in card, card)
            check('the next workout can still be started', page.locator('#btn-start').count() == 1)
        errs = session(pw, be, ALICE, s1b, width=390); check('no page errors (rest day)', not errs, errs)

        # ---- 2. the plan preview, in German
        be = Backend()
        def s2(page):
            until(lambda: page.is_visible('#wz-go'))
            for i in range(3):
                until(lambda: page.is_visible('#wz-go')); page.click('#wz-go'); page.wait_for_timeout(150)
            until(lambda: page.is_visible('#wz-start'))
            t = page.inner_text('#wiz')
            check('preview, German: first workout and training days', 'Erstes Training:' in t and 'Trainingstage:' in t, t[:300])
            check('preview, German: missed workouts line', 'Verpasste Trainings rücken auf deinen nächsten Trainingstag.' in t)
        errs = session(pw, be, ALICE, s2, width=390, lang='de'); check('no page errors (preview)', not errs, errs)

        # ---- 3. Food, nothing set up yet, on a phone
        be = Backend(); seed(be, root={'ask_cal': True, 'settings': {}})
        def s3(page):
            page.set_viewport_size({'width': 390, 'height': 844})
            page.click('#tab-food'); page.wait_for_selector('#fd-body:not([hidden])', timeout=8000); page.wait_for_timeout(500)
            r = page.evaluate("""() => {
              const q = (s) => document.querySelector(s), top = (s) => q(s).getBoundingClientRect().top, bottom = (s) => q(s).getBoundingClientRect().bottom;
              return { search: [Math.round(top('#fd-name')), Math.round(bottom('#fd-name'))], nav: Math.round(top('.mainnav')), eaten: top('#fd-list'), own: top('#fd-ownfoods'), targets: top('#fd-targets'), trends: top('#fd-range') > 0 ? top('#fd-range') : 0, sugTop: !!q('#fd-sug-top') };
            }""")
            check('Add food search is on screen at 390 x 844, calorie question and all', r['search'][1] < r['nav'], r)
            check('the calorie question is still asked', page.is_visible('#fd-askcal'))
            check('Eaten comes before Your own foods', r['eaten'] < r['own'], r)
            check('Your own foods comes before Daily targets', r['own'] < r['targets'], r)
            check('the suggestion above the day is gone', not r['sugTop'])
            order = page.evaluate("[...document.querySelectorAll('#fd-list, #fd-ownfoods')].map((e) => e.id)")
            check('keyboard order follows: Eaten, then Your own foods', order == ['fd-list', 'fd-ownfoods'], order)
            check('own foods: one short line under the heading', page.inner_text('#fd-ownfoods > .note') == 'Save a food using the nutrition values on its label.', page.inner_text('#fd-ownfoods > .note'))
            check('Create a food is outlined', 'pop' not in page.get_attribute('#fd-own-new', 'class'))
            check('the suggestion lives inside Daily targets', page.locator('#fd-targets #fd-sug').count() == 1)
            check('Daily targets is not opened for you', page.get_attribute('#fd-targets', 'open') is None)
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (food)', not errs, errs)

        # ---- 4. calories hidden: the note sits in Daily targets and still leads to Settings
        be = Backend(); seed(be, root={'settings': {'show_calories': False}})
        def s4(page):
            page.click('#tab-food'); page.wait_for_selector('#fd-body:not([hidden])', timeout=8000)
            check('the note is not in the main flow', page.locator('#fd-body > #fd-off').count() == 0 and page.locator('#fd-targets #fd-off').count() == 1)
            page.click('#fd-targets > summary')
            check('it says calories are hidden', until(lambda: page.is_visible('#fd-off')) and 'Calories are hidden.' in page.inner_text('#fd-off'), page.inner_text('#fd-off'))
            check('the link is Show calories', page.inner_text('#fd-off-go').strip().lower() == 'show calories', page.inner_text('#fd-off-go'))
            page.click('#fd-off-go')
            check('it goes to Settings and does not switch calories on by itself', until(lambda: page.is_visible('#v-settings')) and page.evaluate("document.querySelector('#fd-off') && !document.querySelector('#fd-off').hidden"), page.evaluate("location.hash"))
        errs = session(pw, be, ALICE, s4, width=390); check('no page errors (calories hidden)', not errs, errs)
        # ---- 5. Settings: a section's hover and press cover the whole bar, not a box round the text
        be = Backend(); seed(be)
        def s5(page):
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
            geo = page.evaluate("""() => [...document.querySelectorAll('#v-settings section.fold')].filter((s) => s.getClientRects().length).map((s) => { const a = s.getBoundingClientRect(), b = s.querySelector('.set-tog').getBoundingClientRect(); return [Math.round(a.left - b.left), Math.round(a.right - b.right), Math.round(b.height)]; })""")
            check('there are sections to check', len(geo) >= 3, geo)
            check('each toggle spans its whole bar, edge to edge', all(g[0] == 0 and g[1] == 0 for g in geo), geo)
            check('and is at least 44 px tall', all(g[2] >= 44 for g in geo), geo)
            tog = page.locator('#v-settings section.fold .set-tog').first
            tog.hover(); page.wait_for_timeout(500)
            bg_tog = tog.evaluate("e => getComputedStyle(e).backgroundColor")
            bg_sec = tog.evaluate("e => getComputedStyle(e.closest('section')).backgroundColor")
            check('hovering colours the toggle, which is the whole bar', bg_tog not in ('rgba(0, 0, 0, 0)', 'transparent') and bg_tog != bg_sec, (bg_tog, bg_sec))
            tog.click(); page.wait_for_timeout(300)
            check('and a click opens it', tog.get_attribute('aria-expanded') == 'true')
        errs = session(pw, be, ALICE, s5, width=390); check('no page errors (settings bars)', not errs, errs)
finally:
    server.terminate()
done()
