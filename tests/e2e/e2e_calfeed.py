"""The calendar link as a few small steps: Add to my calendar -> when you train -> which calendar -> done. At most three buttons at a time, a
Go back on every step, a free length in minutes. The feed (token + calendar text) is only made when a calendar is chosen, follows plan
changes, and can be replaced or stopped under More. Not shown to accounts that are not on the list."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

ALL = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'schedule': {'enabled': True, 'mode': 'rotation', 'days': ALL, 'per_week': 3, 'rotation': ['day-a', 'day-b']}}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    for i, tid in enumerate(('day-a', 'day-b')):
        be.docs.append({'path': 'yc/templates/' + tid, 'data': {'name': 'Day ' + 'AB'[i], 'order': i, 'kind': 'Other', 'focus': '', 'items': [
            {'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '8 to 12', 'target': '60', 'target_at': '2026-10-01', 'rest_s': 90, 'note': None}]}})

def only(page, who):
    page.route('**/config.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=re.sub(r"planCheckOnly: \[[^\]]*\]", 'planCheckOnly: [%s]' % who, r.fetch().text(), count=1)))

def open_panel(page, sel):
    page.goto(BASE); page.wait_for_selector('#btn-cal', timeout=8000)
    page.click('#btn-cal'); page.wait_for_selector(sel, timeout=5000); page.wait_for_timeout(200)

def events(ics): return re.findall(r'^DTSTART:(\d{8})T', ics, re.M)
def buttons(page): return page.locator('#cal-panel button:visible').count()
def last(page):
    until(lambda: page.evaluate('window.__opened.length') > 0)
    return page.evaluate('window.__opened')[-1]
def capture(page):
    page.evaluate("window.__opened = []; document.addEventListener('click', (e) => { const a = e.target.closest && e.target.closest('a[target=_blank]'); if (a) { window.__opened.push(a.href); e.preventDefault(); } }, true)")

server = serve()
try:
    with sync_playwright() as pw:
        # 1. not on the list: only the file
        be = Backend(); seed(be)
        def s1(page):
            open_panel(page, '#cal-file')
            check('not on the list: no calendar link, the file stays', page.locator('#cal-sub').count() == 0 and page.locator('#cal-file').count() == 1)
            check('the length is a number of minutes, not a short list', page.get_attribute('#cal-len', 'type') == 'number')
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (hidden)', not errs, errs)

        # 2. the steps
        be = Backend(); seed(be)
        def s2(page):
            only(page, "'alice@example.com'"); open_panel(page, '#cal-sub')
            check('step 1: one button, and a small way to a file', buttons(page) == 2 and page.locator('#cal-sub').count() == 1, buttons(page))
            page.click('#cal-sub'); page.wait_for_selector('#cal-len')
            check('step 2: when do you train, with a Next and a Go back', buttons(page) == 2 and 'when do you train' in page.inner_text('#cal-panel').lower(), page.inner_text('#cal-panel')[:80])
            check('nothing is stored yet', be.feeds == [])
            page.go_back if False else None
            page.click('#cal-panel button:has-text("Go back")')
            check('Go back returns to step 1', until(lambda: page.locator('#cal-sub').count() == 1))
            page.click('#cal-sub'); page.wait_for_selector('#cal-len')
            page.fill('#cal-len', '10'); page.click('#cal-next')
            check('a length under 15 minutes is refused', 'Length has to be 15 to 480 minutes' in page.inner_text('#cal-msg') and page.locator('#cal-apple').count() == 0, page.inner_text('#cal-msg'))
            page.fill('#cal-len', '50'); page.fill('#cal-time', '06:45'); page.click('#cal-next')
            check('step 3: which calendar, three choices and a Go back', until(lambda: page.locator('#cal-apple').count() == 1) and page.locator('#cal-google').count() == 1 and page.locator('#cal-outlook').count() == 1 and buttons(page) == 4, buttons(page))
            check('still nothing stored', be.feeds == [])
            capture(page)
            page.click('#cal-google')
            check('choosing a calendar stores the feed', until(lambda: len(be.feeds) == 1), be.feeds)
            f = be.feeds[0]
            check('with a 48 character token', re.fullmatch(r'[a-f0-9]{48}', f['token']) is not None, f['token'])
            check('the picked time and length are kept', f['prefs'] == {'time': '06:45', 'min': 50}, f['prefs'])
            ev = events(f['ics'])
            check('the calendar text has the next 8 weeks of workouts', f['ics'].startswith('BEGIN:VCALENDAR') and 20 <= len(ev) <= 26, len(ev))
            check('named, with a refresh hint, stable event ids', 'X-WR-CALNAME:Yes Coach!' in f['ics'] and 'REFRESH-INTERVAL' in f['ics'] and all(u.startswith('yes-coach-') for u in re.findall(r'^UID:(.*)$', f['ics'], re.M)))
            u = last(page)
            check('Google gets the subscription address, outside the app', 'calendar.google.com/calendar/r?cid=' in u and 'webcal' in u and f['token'] in u, u)
            check('step 4: what happens now, and a Done', until(lambda: page.locator('#cal-done').count() == 1) and 'confirm on its website' in page.inner_text('#cal-panel') and buttons(page) == 2, buttons(page))
            page.click('#cal-other'); page.wait_for_selector('#cal-apple')
            page.evaluate('window.__opened = []')
            page.click('#cal-apple')
            u = last(page)
            check('Apple gets a webcal address', u == 'webcal://qazvzhhoalkyyasakphs.supabase.co/functions/v1/calendar/' + f['token'] + '.ics', u)
            check('and is told to tap Subscribe', until(lambda: 'Tap Subscribe' in page.inner_text('#cal-panel')))
            page.click('#cal-other'); page.wait_for_selector('#cal-outlook'); page.evaluate('window.__opened = []'); page.click('#cal-outlook')
            u = last(page)
            check('Outlook gets its add-from-web address', u.startswith('https://outlook.live.com/calendar/0/addfromweb?url=') and 'calendar%2F' + f['token'] in u, u)
            page.click('#cal-done')
            check('Done closes the panel', until(lambda: page.locator('#cal-panel').is_hidden()))

            # 3. open again: the link is on
            page.click('#btn-cal'); page.wait_for_selector('#cal-add')
            check('home with the link on: three buttons at most, none of them the link itself', buttons(page) <= 4 and page.locator('#cal-link').count() == 0, buttons(page))
            check('it says what is on', 'follow your plan' in page.inner_text('#cal-panel'))

            # 4. the plan changes: the stored text follows
            before = len(events(be.feeds[0]['ics']))
            page.click('.mainnav [data-view="plan"]'); page.wait_for_selector('.pw-days[aria-label="Workouts a week"]', timeout=6000)
            page.click('.pw-days[aria-label="Workouts a week"] .pk-chip >> nth=4')
            check('5 a week: more workouts in the feed', until(lambda: len(events(be.feeds[0]['ics'])) > before + 8, 12), (before, len(events(be.feeds[0]['ics']))))
            check('the same token', be.feeds[0]['token'] == f['token'])

            # 5. change the time
            page.click('.mainnav [data-view="train"]'); page.wait_for_selector('#btn-cal')
            if page.locator('#cal-panel').is_hidden(): page.click('#btn-cal')
            page.wait_for_selector('#cal-when'); old = be.feeds[0]['ics']
            page.click('#cal-when'); page.wait_for_selector('#cal-len')
            check('the saved length is shown', page.input_value('#cal-len') == '50' and page.input_value('#cal-time') == '06:45')
            page.fill('#cal-time', '07:30'); page.fill('#cal-len', '120'); page.click('#cal-next')
            check('Save stores both', until(lambda: be.feeds[0]['prefs'] == {'time': '07:30', 'min': 120} and be.feeds[0]['ics'] != old), be.feeds[0]['prefs'])
            check('and says so, back on home', until(lambda: page.locator('#cal-add').count() == 1 and 'Saved' in page.inner_text('#cal-msg')))

            # 6. More: new link, stop
            page.click('#cal-more'); page.wait_for_selector('#cal-link')
            check('More: the link with Copy, New link and Stop sharing, and a Go back', buttons(page) <= 6 and 'Anyone with the link' in page.inner_text('#cal-panel'))
            check('the link points at the calendar function', page.input_value('#cal-link') == 'https://qazvzhhoalkyyasakphs.supabase.co/functions/v1/calendar/' + f['token'] + '.ics')
            page.evaluate('window.__opened = []'); page.click('#cal-open')
            check('Open link opens the https address outside the app', last(page) == page.input_value('#cal-link'))
            page.click('#cal-new'); page.click('#cal-new-yes')
            check('a new token', until(lambda: len(be.feeds) == 1 and be.feeds[0]['token'] != f['token']), be.feeds)
            check('the panel stays on the link and shows the new one', until(lambda: page.locator('#cal-link').count() == 1 and be.feeds[0]['token'] in page.input_value('#cal-link')))
            check('and says so', 'New link made' in page.inner_text('#cal-msg'))
            page.click('#cal-stop'); page.click('#cal-stop-yes')
            check('stopped: the row is deleted', until(lambda: be.feeds == []), be.feeds)
            check('and the panel offers to start again', until(lambda: page.locator('#cal-sub').count() == 1))
            check('with the message', 'Stopped' in page.inner_text('#cal-msg'))
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (steps)', not errs, errs)

        # 7. an existing feed is picked up on reload; Dutch
        be = Backend(); seed(be)
        be.feeds.append({'user_id': ALICE, 'token': 'ab' * 24, 'ics': 'BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n', 'prefs': {'time': '18:00', 'min': 75}})
        def s3(page):
            only(page, "'alice@example.com'"); open_panel(page, '#cal-add')
            t = page.inner_text('#cal-panel').lower()
            check('Dutch: home is translated', 'toevoegen aan een agenda' in t or 'aan een agenda toevoegen' in t, t[:300])
            check('the stale text is rebuilt from the plan', until(lambda: len(events(be.feeds[0]['ics'])) >= 8, 12), be.feeds[0]['ics'][:80])
            page.click('#cal-add'); page.wait_for_selector('#cal-apple')
            t = page.inner_text('#cal-panel').lower()
            check('Dutch: the choices are translated', 'welke agenda' in t and 'apple agenda' in t, t[:300])
            check('Dutch: Go back says terug', 'terug' in t and '\nrug' not in t, t)
        errs = session(pw, be, ALICE, s3, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
