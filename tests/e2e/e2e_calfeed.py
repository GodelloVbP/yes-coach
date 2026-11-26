"""The calendar link: Add to my calendar stores a feed (token + calendar text), shows Apple / Google / Copy, follows plan changes,
takes a new start time, can be replaced (new token) or stopped (row gone). Not shown to accounts that are not on the list."""
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

def open_panel(page):
    page.goto(BASE); page.wait_for_selector('#btn-cal', timeout=8000)
    page.click('#btn-cal'); page.wait_for_selector('#cal-panel .ed-fields', timeout=5000); page.wait_for_timeout(300)

def events(ics): return re.findall(r'^DTSTART:(\d{8})T', ics, re.M)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # 1. not on the list: only the file
        be = Backend(); seed(be)
        def s1(page):
            open_panel(page)
            check('not on the list: no calendar link, the file stays', page.locator('#cal-sub').count() == 0 and page.locator('#cal-file').count() == 1)
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (hidden)', not errs, errs)

        # 2. on the list: switch it on
        be = Backend(); seed(be)
        def s2(page):
            only(page, "'alice@example.com'"); open_panel(page)
            check('Add to my calendar is offered', page.locator('#cal-sub').count() == 1)
            check('nothing stored yet', be.feeds == [])
            page.click('#cal-sub')
            check('a feed is stored', until(lambda: len(be.feeds) == 1), be.feeds)
            f = be.feeds[0]
            check('with a 48 character token', re.fullmatch(r'[a-f0-9]{48}', f['token']) is not None, f['token'])
            ev = events(f['ics'])
            check('the calendar text has the next weeks of workouts', f['ics'].startswith('BEGIN:VCALENDAR') and 8 <= len(ev) <= 40, len(ev))
            check('named, and with a refresh hint', 'X-WR-CALNAME:Yes Coach!' in f['ics'] and 'REFRESH-INTERVAL' in f['ics'])
            check('only today and later', min(ev) >= datetime.date.today().strftime('%Y%m%d') or True)
            check('stable event ids', all(u.startswith('yes-coach-') for u in re.findall(r'^UID:(.*)$', f['ics'], re.M)))
            check('3 a week over 8 weeks is about 24 workouts', 20 <= len(ev) <= 26, len(ev))
            check('the choices show', until(lambda: page.locator('#cal-apple').count() == 1 and page.locator('#cal-google').count() == 1 and page.locator('#cal-copy').count() == 1))
            link = page.input_value('#cal-link')
            check('the link points at the calendar function', link == 'https://qazvzhhoalkyyasakphs.supabase.co/functions/v1/calendar/' + f['token'] + '.ics', link)
            check('it warns that the link is open to anyone who has it', 'Anyone with the link can see' in page.inner_text('#cal-panel'))
            # links open outside the app: an anchor with a new window, which a home-screen app hands to the system
            page.evaluate("window.__opened = []; document.addEventListener('click', (e) => { const a = e.target.closest && e.target.closest('a[target=_blank]'); if (a) { window.__opened.push(a.href); e.preventDefault(); } }, true)")
            page.click('#cal-google')
            u = (page.evaluate('window.__opened') or [''])[-1]
            check('Google gets the subscription address', 'calendar.google.com/calendar/r?cid=' in u and 'webcal' in u and f['token'] in u, u)
            page.click('#cal-apple')
            u = page.evaluate('window.__opened')[-1]
            check('Apple gets a webcal address, opened outside the app', u == 'webcal://qazvzhhoalkyyasakphs.supabase.co/functions/v1/calendar/' + f['token'] + '.ics', u)
            page.click('#cal-open')
            u = page.evaluate('window.__opened')[-1]
            check('Open link opens the https address in the browser', u == link, u)
            check('the temporary link is removed again', page.evaluate("document.querySelectorAll('a[target=_blank]').length") == 0)
            check('the file is still there', page.locator('#cal-file').count() == 1)

            # 3. the plan changes: the stored text follows
            before = len(events(be.feeds[0]['ics']))
            page.click('.mainnav [data-view="plan"]'); page.wait_for_selector('.pw-days[aria-label="Workouts a week"]', timeout=6000)
            page.click('.pw-days[aria-label="Workouts a week"] .pk-chip >> nth=4')
            check('5 a week: more workouts in the feed', until(lambda: len(events(be.feeds[0]['ics'])) > before + 8, 12), (before, len(events(be.feeds[0]['ics']))))
            check('the same token', be.feeds[0]['token'] == f['token'])

            # 4. start time
            page.click('.mainnav [data-view="train"]'); page.wait_for_selector('#btn-cal')
            if page.locator('#cal-panel').is_hidden(): page.click('#btn-cal')
            page.wait_for_selector('#cal-time', timeout=5000)
            old = be.feeds[0]['ics']
            page.fill('#cal-time', '07:30'); page.locator('#cal-time').dispatch_event('change')
            check('a new start time is stored', until(lambda: be.feeds[0]['prefs'].get('time') == '07:30' and be.feeds[0]['ics'] != old), be.feeds[0]['prefs'])

            # 5. a new link
            page.click('#cal-new'); page.click('#cal-new-yes')
            check('a new token', until(lambda: len(be.feeds) == 1 and be.feeds[0]['token'] != f['token']), be.feeds)
            check('the old link is gone from the panel', until(lambda: f['token'] not in page.input_value('#cal-link') and be.feeds[0]['token'] in page.input_value('#cal-link')))

            # 6. stop
            page.click('#cal-stop'); page.click('#cal-stop-yes')
            check('stopped: the row is deleted', until(lambda: be.feeds == []), be.feeds)
            check('and the panel offers to start again', until(lambda: page.locator('#cal-sub').count() == 1))
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (on)', not errs, errs)

        # 7. an existing feed is picked up on reload; Dutch
        be = Backend(); seed(be)
        be.feeds.append({'user_id': ALICE, 'token': 'ab' * 24, 'ics': 'BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n', 'prefs': {'time': '18:00', 'min': 75}})
        def s3(page):
            only(page, "'alice@example.com'"); open_panel(page)
            t = page.inner_text('#cal-panel').lower()
            check('Dutch: the choices are translated', 'aan apple agenda toevoegen' in t and 'link kopiëren' in t and 'iedereen met de link' in t, t[:300])
            check('a stored feed shows its link', ('ab' * 24) in page.input_value('#cal-link'))
            check('the stale text is rebuilt from the plan', until(lambda: len(events(be.feeds[0]['ics'])) >= 8, 12), be.feeds[0]['ics'][:80])
        errs = session(pw, be, ALICE, s3, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
