"""Calendar subscription: Add to calendar stores the plan behind a secret address, offers Apple, Google and Outlook, keeps the feed current, and can stop."""
import subprocess, time, datetime, urllib.parse
from playwright.sync_api import sync_playwright
from harness import *

TODAY = datetime.date.today()
T = TODAY.isoformat()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TODAY.weekday()]

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = {'ex': 'bench', 'order': 1, 'sets': 2, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None}
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': WD, 'items': [it]}})

def doc(be, path): return next((d['data'] for d in be.docs if d['path'] == path), None)
def unfold(ics): return ics.replace('\r\n ', '')

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be); be.feed = None
        def s1(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('#btn-cal')
            check('the panel offers the three calendars', until(lambda: all(page.is_visible('#cal-panel a:has-text("%s")' % n) for n in ('Apple Calendar', 'Google Calendar', 'Outlook'))), page.inner_text('#cal-panel'))
            feed = 'https://qazvzhhoalkyyasakphs.supabase.co/functions/v1/cal/' + 'f' * 64 + '.ics'
            hrefs = {n: page.get_attribute('#cal-panel a:has-text("%s")' % n, 'href') for n in ('Apple Calendar', 'Google Calendar', 'Outlook')}
            check('Apple gets a webcal link to the feed', hrefs['Apple Calendar'] == feed.replace('https:', 'webcal:'), hrefs)
            check('Google gets the add-by-link address with the webcal feed', hrefs['Google Calendar'] == 'https://calendar.google.com/calendar/r?cid=' + urllib.parse.quote(feed.replace('https:', 'webcal:'), safe=''), hrefs)
            check('Outlook gets the add-from-web address with the https feed', hrefs['Outlook'].startswith('https://outlook.live.com/calendar/0/addfromweb?') and urllib.parse.quote(feed, safe='') in hrefs['Outlook'], hrefs)
            check('the feed is stored with the plan in it', be.feed and 'BEGIN:VCALENDAR' in be.feed['ics'] and 'SUMMARY:Yes Coach: Push day' in be.feed['ics'], be.feed and be.feed['ics'][:200])
            ics = unfold(be.feed['ics'])
            check('it is a subscription: named, refresh hint, one event per planned day', 'X-WR-CALNAME:Yes Coach' in ics and 'REFRESH-INTERVAL' in ics and ics.count('BEGIN:VEVENT') >= 8, ics.count('BEGIN:VEVENT'))
            uids = [l for l in ics.split('\r\n') if l.startswith('UID:')]
            check('every event has its own stable id', len(uids) == len(set(uids)) and ('UID:yes-coach-' + T + '-push@yescoach') in uids, uids[:3])
            check('lines are folded at 75 bytes', all(len(l.encode()) <= 75 for l in be.feed['ics'].split('\r\n')))
            check('sync is switched on and saved with the plan', until(lambda: (doc(be, 'yc') or {}).get('cal', {}).get('on') is True and doc(be, 'yc')['cal']['time'] == '18:00'), doc(be, 'yc'))
            # change the time: kept, and the feed follows
            page.fill('#cal-time', '07:30'); page.dispatch_event('#cal-time', 'change')
            check('a new start time is saved', until(lambda: doc(be, 'yc')['cal']['time'] == '07:30'), doc(be, 'yc'))
            want = page.evaluate("(d) => new Date(d + 'T07:30:00').toISOString().replace(/[-:]/g, '').replace(/\\.\\d{3}/, '')", T)
            check('and reaches the feed by itself, at that local time', until(lambda: ('DTSTART:' + want) in unfold(be.feed['ics']), 12), (want, [l for l in unfold(be.feed['ics']).split('\r\n') if l.startswith('DTSTART')][:2]))
            # copy link
            page.click('#cal-panel button:has-text("Other calendar")')
            check('copy link puts the https address on the clipboard', until(lambda: page.evaluate('navigator.clipboard.readText()') == feed))
            # new link
            page.click('#cal-panel button:has-text("New link")')
            check('a new link replaces the address everywhere', until(lambda: page.get_attribute('#cal-panel a:has-text("Apple Calendar")', 'href').endswith('e' * 64 + '.ics')), page.get_attribute('#cal-panel a:has-text("Apple Calendar")', 'href'))
            # stop
            page.click('#cal-panel button:has-text("Stop syncing")')
            check('stopping deletes the feed and switches sync off', until(lambda: be.feed is None and doc(be, 'yc')['cal']['on'] is False), (be.feed, doc(be, 'yc')))
            check('the panel closes', not page.is_visible('#cal-panel'))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (calendar)', not errs, errs)

        # a subscriber who only opens the app: the feed is refreshed without touching the panel
        be = Backend(); seed(be); be.feed = None
        doc(be, 'yc').update({'cal': {'on': True, 'time': '18:00', 'minutes': 75}})
        def s2(page):
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            check('opening the app refreshes the feed of a subscriber', until(lambda: be.feed is not None and 'Push day' in be.feed['ics'], 12), be.feed)
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (feed refresh)', not errs, errs)
finally:
    server.terminate()
done()
