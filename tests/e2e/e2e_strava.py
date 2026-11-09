"""Strava: connect once, then finished workouts are posted as a Weight Training activity with the sets in the description."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TODAY = datetime.date.today()
T = TODAY.isoformat()
def doc(be, path): return next((d['data'] for d in be.docs if d['path'] == path), None)

def seed(be, finished=True, settings=None):
    now_ms = int(time.time() * 1000)
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': settings or {}}})
    be.docs.append({'path': 'yc/exercises/legext', 'data': {'name': 'Leg extension', 'group': 'Legs', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/exercises/squat', 'data': {'name': 'Squat', 'group': 'Legs', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/legs', 'data': {'name': 'Legs', 'order': 1, 'kind': 'Legs', 'focus': '', 'weekday': TODAY.strftime('%a'), 'items': [
        {'ex': 'legext', 'order': 1, 'sets': 3, 'reps': '10', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None},
        {'ex': 'squat', 'order': 2, 'sets': 3, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None}]}})
    sets = {}
    for i in (1, 2, 3): sets['legext_%d' % i] = {'ex': 'legext', 'n': i, 'order': i, 'kind': 'work', 'reps': 10, 'load': 25, 'done': True, 'at': now_ms - 1800000 + i * 60000, 'ticked_at': now_ms - 1800000 + i * 60000, 'unit': 'kg:total'}
    sets['squat_1'] = {'ex': 'squat', 'n': 1, 'order': 10, 'kind': 'work', 'reps': 8, 'load': 65, 'done': True, 'at': now_ms - 600000, 'ticked_at': now_ms - 600000, 'unit': 'kg:total'}
    sets['squat_0'] = {'ex': 'squat', 'n': 0, 'order': 9, 'kind': 'warmup', 'reps': 10, 'load': 20, 'done': True, 'at': now_ms - 700000, 'ticked_at': now_ms - 700000, 'unit': 'kg:total'}
    if finished is None: return  # no workout yet today
    be.docs.append({'path': 'yc/sessions/' + T, 'data': dict({'date': T, 'template': 'legs', 'split': 'Legs', 'label': 'Legs', 'started_at': now_ms - 1900000, 'sets': sets}, **({'finished_at': now_ms - 500000} if finished else {}))})

def with_strava(page, on=True, only="'alice@example.com'"):
    def cfg(r):
        t = re.sub(r"strava: (true|false)", 'strava: %s' % ('true' if on else 'false'), r.fetch().text(), count=1)
        t = re.sub(r"stravaOnly: \[[^\]]*\]", 'stravaOnly: [%s]' % only, t, count=1)
        r.fulfill(status=200, content_type='application/javascript', body=t)
    page.route('**/config.js', cfg)

def open_row(page):
    page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
    page.locator('#v-settings section.fold').filter(has=page.locator('#strava-row')).locator('.set-tog').click() if page.locator('#strava-row').is_hidden() else None

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. not on the list (the shipped config names only the owner), or switched off: nothing shows, and no button on a finished day
        be = Backend(); seed(be); be.strava_connected = True
        def s1(page):
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible'); page.wait_for_timeout(300)
            check('not on the owner list: no Strava block', page.locator('#strava-row').is_hidden())
            page.click('#tab-train'); page.wait_for_selector('#today-card .t-head'); page.wait_for_timeout(500)
            check('and no Post to Strava button', page.locator('.st-day').count() == 0 and not be.strava_calls, be.strava_calls)
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (off)', not errs, errs)
        for label, kw in (('switched off', dict(on=False)), ('on for someone else only', dict(only="'someone@else.com'"))):
            be = Backend(); seed(be); be.strava_connected = True
            def s1b(page, kw=kw, label=label):
                with_strava(page, **kw); page.goto(BASE); page.wait_for_selector('#today-card .t-head', timeout=8000); page.wait_for_timeout(500)
                page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible'); page.wait_for_timeout(300)
                check(label + ': no Strava block, no button', page.locator('#strava-row').is_hidden() and page.locator('.st-day').count() == 0 and not be.strava_calls, be.strava_calls)
            errs = session(pw, be, ALICE, s1b, width=390); check('no page errors (%s)' % label, not errs, errs)

        # ---- 2. connecting: Settings shows it, the button goes to Strava
        be = Backend(); seed(be, finished=None)
        def s2(page):
            with_strava(page); page.route('https://www.strava.com/**', lambda r: r.fulfill(status=200, content_type='text/html', body='<title>Strava</title>')); page.goto(BASE); page.wait_for_selector('#today-card .t-head', timeout=8000)
            open_row(page)
            check('Settings: not connected, with a Connect button', until(lambda: page.is_visible('#strava-connect')) and 'Not connected' in page.text_content('#strava-state') and page.locator('#strava-auto-row').is_hidden(), page.text_content('#strava-state'))
            page.click('#strava-connect')
            check('Connect goes to Strava, asking for activity:write', until(lambda: page.url.startswith('https://www.strava.com/oauth/authorize') and 'activity%3Awrite' in page.url), page.url)
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (connect)', not errs, errs)

        # ---- 3. back from Strava
        be = Backend(); seed(be, finished=None); be.strava_connected = True
        def s3(page):
            with_strava(page); page.goto(BASE + '?strava=ok#settings'); page.wait_for_selector('#v-settings', state='visible', timeout=8000)
            check('back from Strava: it says connected', until(lambda: 'Connected to Strava.' in (page.text_content('#toast') or page.text_content('body'))), '')
            check('the address is cleaned up', 'strava=' not in page.url, page.url)
            open_row(page)
            check('Settings: connected, with Disconnect and the automatic switch', until(lambda: page.is_visible('#strava-off') and page.is_visible('#set-strava-auto')) and page.locator('#strava-connect').is_hidden())
            page.check('#set-strava-auto')
            check('the switch is saved', until(lambda: (doc(be, 'yc') or {}).get('settings', {}).get('strava_auto') is True), doc(be, 'yc'))
            page.click('#strava-off')
            check('Disconnect tells the function and shows Connect again', until(lambda: any(c.get('action') == 'disconnect' for c in be.strava_calls)) and until(lambda: page.is_visible('#strava-connect')))
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (back)', not errs, errs)

        for r, msg in (('denied', 'Strava was not connected.'), ('scope', 'Allow Yes Coach! to add activities'), ('error', 'Could not connect Strava')):
            be = Backend(); seed(be, finished=None)
            def sx(page, r=r, msg=msg):
                with_strava(page); page.goto(BASE + '?strava=%s#settings' % r); page.wait_for_selector('#v-settings', state='visible', timeout=8000)
                check('back from Strava, %s: %s' % (r, msg), until(lambda: msg in page.text_content('body')), '')
            errs = session(pw, be, ALICE, sx, width=390); check('no page errors (%s)' % r, not errs, errs)

        # an error with a reason shows it, and the address is cleaned up
        for lang, msg in (('en', 'Could not connect Strava (Strava 400 client_secret invalid)'), ('nl', 'Strava koppelen lukte niet (Strava 400 client_secret invalid)')):
            be = Backend(); seed(be, finished=None)
            def sw(page, msg=msg):
                with_strava(page); page.goto(BASE + '?strava=error&why=Strava%20400%20client_secret%20invalid#settings'); page.wait_for_selector('#v-settings', state='visible', timeout=8000)
                check('error with a reason (%s): %s' % (lang, msg), until(lambda: msg in page.text_content('body')), '')
                check('address has no strava or why left', 'why=' not in page.url and 'strava=' not in page.url, page.url)
            errs = session(pw, be, ALICE, sw, width=390, lang=lang); check('no page errors (reason %s)' % lang, not errs, errs)

        # ---- 4. a finished workout is posted by itself when the switch is on
        be = Backend(); seed(be, finished=None, settings={'strava_auto': True}); be.strava_connected = True
        def s4(page):
            with_strava(page); page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.evaluate("window.YC_STRAVA.status()"); page.wait_for_timeout(500)
            page.click('#btn-start'); page.wait_for_selector('#f-legext_1-load', state='visible')
            for i in (1, 2, 3):
                page.fill('#f-legext_%d-load' % i, '25'); page.fill('#f-legext_%d-reps' % i, '10')
                page.locator('.set:has(#f-legext_%d-load) .set-tick' % i).click(); page.wait_for_timeout(250)
            page.wait_for_timeout(900)
            page.locator('button.skew:visible', has_text=re.compile(r'^\s*Finish', re.I)).first.click()
            check('finishing posts it', until(lambda: len(be.strava_posts) == 1), be.strava_calls)
            p = be.strava_posts[0]
            check('named for the training day', p['name'] == 'Legs', p)
            check('with the start as local time', re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', p['start']) is not None, p)
            check('and a duration of at least a minute', 60 <= p['seconds'] <= 3600, p)
            check('the sets are in the description, equal sets together', 'Leg extension: 3 × 10 @ 25 kg' in p['description'] and 'Logged with Yes Coach!' in p['description'], p['description'])
            check('the day remembers it was posted', until(lambda: (doc(be, 'yc/sessions/' + T) or {}).get('strava', {}).get('id') == 5001), doc(be, 'yc/sessions/' + T))
        errs = session(pw, be, ALICE, s4, width=390); check('no page errors (automatic)', not errs, errs)

        # ---- 5. the switch is off: nothing is posted by itself; the button does it once
        be = Backend(); seed(be, finished=True); be.strava_connected = True
        def s5(page):
            with_strava(page); page.goto(BASE); page.wait_for_selector('#today-card .t-head', timeout=8000)
            check('the Today card offers Post to Strava', until(lambda: page.locator('#today-card .st-day').count() == 1 and 'Post to Strava' in page.text_content('#today-card .st-day')), page.inner_text('#today-card'))
            check('nothing was posted by itself', not be.strava_posts)
            page.click('#today-card .st-day')
            check('the button posts it', until(lambda: len(be.strava_posts) == 1))
            check('and becomes a link to the activity', until(lambda: page.locator('#today-card a.st-day').count() == 1) and page.get_attribute('#today-card a.st-day', 'href') == 'https://www.strava.com/activities/5001', page.inner_text('#today-card'))
            check('no second button', page.locator('#today-card button.st-day').count() == 0)
            page.click('#wk-rows .wk-blk.is-today')
            check('the day in the week shows the link too', until(lambda: page.locator('#wk-sheet a.st-day').count() == 1), page.inner_text('#wk-sheet'))
        errs = session(pw, be, ALICE, s5, width=390); check('no page errors (manual)', not errs, errs)

        # ---- 6. Strava needs connecting again / is busy
        be = Backend(); seed(be, finished=True); be.strava_connected = True; be.strava_post = 'reconnect'
        def s6(page):
            with_strava(page); page.goto(BASE); page.wait_for_selector('#today-card .t-head', timeout=8000)
            until(lambda: page.locator('#today-card .st-day').count() == 1); page.click('#today-card .st-day')
            check('a refused link says to connect again', until(lambda: 'connected again' in page.text_content('body')), '')
            check('and the button is back to be tried again', until(lambda: page.locator('#today-card button.st-day').count() == 1 and page.locator('#today-card button.st-day').is_enabled()))
            check('the session is not marked as posted', not (doc(be, 'yc/sessions/' + T) or {}).get('strava'))
        errs = session(pw, be, ALICE, s6, width=390); check('no page errors (reconnect)', not errs, errs)

        be = Backend(); seed(be, finished=True); be.strava_connected = True; be.strava_post = 'busy'
        def s7(page):
            with_strava(page); page.goto(BASE); page.wait_for_selector('#today-card .t-head', timeout=8000)
            until(lambda: page.locator('#today-card .st-day').count() == 1); page.click('#today-card .st-day')
            check('busy says to try again later', until(lambda: 'busy' in page.text_content('body')), '')
        errs = session(pw, be, ALICE, s7, width=390); check('no page errors (busy)', not errs, errs)

        # ---- 7. not connected: no button even when set up
        be = Backend(); seed(be, finished=True)
        def s8(page):
            with_strava(page); page.goto(BASE); page.wait_for_selector('#today-card .t-head', timeout=8000); page.wait_for_timeout(800)
            check('set up but not connected: no Post to Strava button', page.locator('.st-day').count() == 0)
        errs = session(pw, be, ALICE, s8, width=390); check('no page errors (not connected)', not errs, errs)

        # ---- 8. German
        be = Backend(); seed(be, finished=None); be.strava_connected = True
        def s9(page):
            with_strava(page); page.goto(BASE); page.wait_for_selector('#today-card .t-head', timeout=8000); open_row(page)
            check('German: the block is translated', until(lambda: 'Mit Strava verbunden' in page.text_content('#strava-state')) and 'trennen' in page.text_content('#strava-off').lower() and 'automatisch' in page.text_content('#strava-auto-row'), page.text_content('#strava-row'))
        errs = session(pw, be, ALICE, s9, width=390, lang='de'); check('no page errors (German)', not errs, errs)
finally:
    server.terminate()
done()
