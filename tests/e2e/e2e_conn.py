"""Connected AI apps: the same app connected again is one row with its number of connections; Remove old keeps the newest, Disconnect removes
all of them. The Claude and your plan control has equal options and both are explained."""
import subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.grants = [{'client': {'id': 'c%d' % i, 'name': 'Claude', 'uri': 'https://claude.ai'}, 'scopes': ['openid'], 'granted_at': '2026-11-2%d' % i} for i in range(5)] + \
                [{'client': {'id': 'x1', 'name': 'Other AI', 'uri': 'https://other.example'}, 'scopes': ['openid'], 'granted_at': '2026-11-10'}]

def open_conn(page):
    page.goto(BASE); page.wait_for_selector('#tab-settings', timeout=8000); page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
    if page.locator('#conn-list').is_hidden(): page.locator('#v-settings section.fold').filter(has=page.locator('#conn-list')).locator('.set-tog').click()
    page.wait_for_selector('#conn-list .foot-row', timeout=6000); page.wait_for_timeout(300)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            page.set_viewport_size({'width': 390, 'height': 844}); open_conn(page)
            rows = page.locator('#conn-list .foot-row')
            check('two rows for six grants: one per app', rows.count() == 2, rows.count())
            check('the repeated app says how many connections', '5 connections' in rows.first.inner_text(), rows.first.inner_text())
            check('and offers to remove the old ones', page.get_by_role('button', name='Remove the 4 older connections of Claude and keep the newest').count() == 1)
            check('the single app has only Disconnect', rows.nth(1).locator('button').count() == 1)
            check('the equal-width choice: both options the same width', abs(page.locator('#claude-plan .seg-b').nth(0).bounding_box()['width'] - page.locator('#claude-plan .seg-b').nth(1).bounding_box()['width']) < 2)
            check('neither option wraps onto two lines', all(page.locator('#claude-plan .seg-b').nth(i).bounding_box()['height'] < 60 for i in (0, 1)))
            note = page.inner_text('#claude-plan-note')
            check('both options are explained', 'waits for your yes' in note and 'tells you what it changed' in note, note)
            page.get_by_role('button', name='Remove the 4 older connections of Claude and keep the newest').click()
            check('the 4 older ones are revoked', until(lambda: sorted(c[1] for c in be.calls if c[0] == 'revoke') == ['c0', 'c1', 'c2', 'c3']), be.calls)
            check('the newest stays', sorted(g['client']['id'] for g in be.grants) == ['c4', 'x1'], [g['client']['id'] for g in be.grants])
            check('the row now has one connection and no Remove button', until(lambda: '5 connections' not in page.inner_text('#conn-list') and page.get_by_role('button', name='Remove the 4 older connections of Claude and keep the newest').count() == 0))
            check('it says what happened', 'removed. The newest stays.' in page.inner_text('#conn-state'), page.inner_text('#conn-state'))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors', not errs, errs)

        be = Backend(); seed(be)
        def s2(page):
            page.set_viewport_size({'width': 390, 'height': 844}); open_conn(page)
            page.get_by_role('button', name='Disconnect Claude').click()
            check('Disconnect removes all five of that app', until(lambda: sorted(g['client']['id'] for g in be.grants) == ['x1']), [g['client']['id'] for g in be.grants])
            check('and leaves the other app', 'Other AI' in page.inner_text('#conn-list') and 'Claude' not in page.inner_text('#conn-list'), page.inner_text('#conn-list'))
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (disconnect)', not errs, errs)

        be = Backend(); seed(be)
        def s3(page):
            page.set_viewport_size({'width': 390, 'height': 844}); open_conn(page)
            low = page.inner_text('#conn-list').lower()
            check('Dutch: translated', 'verbindingen' in low and 'oude' in low, low)
        errs = session(pw, be, ALICE, s3, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
