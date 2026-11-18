"""Finish asks first: "Are you sure you are done with your workout?" with the sets not done yet; Keep going, Escape and a tap outside go
back to the workout; Yes finishes and opens the finish screen. Every Finish button asks."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '10', 'target': '', 'target_at': '2026-01-01', 'rest_s': 60, 'note': None}]}})

def start(page):
    page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start')
    page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(300)
    page.fill('#f-bench_1-load', '50'); page.fill('#f-bench_1-reps', '10'); page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_timeout(900)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            start(page)
            fin = page.locator('#focus-finish')
            fin.click()
            check('the question comes up', until(lambda: page.locator('.fin-ask').is_visible()))
            tx = page.locator('.fin-ask').inner_text()
            check('it asks the question', 'Are you sure you are done with your workout?' in tx, tx)
            check('and says what is left: 2 sets', '2 sets are not done yet.' in tx, tx)
            check('the finish screen has not opened', page.locator('.fin').count() == 0)
            page.click('.fin-ask .textbtn')
            check('Keep going closes it and stays in the workout', until(lambda: page.locator('.fin-ask').count() == 0) and page.locator('.fin').count() == 0 and page.is_visible('#f-bench_1-load'))
            fin.click(); page.wait_for_selector('.fin-ask'); page.keyboard.press('Escape')
            check('Escape closes it too', until(lambda: page.locator('.fin-ask').count() == 0) and page.locator('.fin').count() == 0)
            fin.click(); page.wait_for_selector('.fin-ask'); page.mouse.click(5, 5)
            check('a tap outside closes it', until(lambda: page.locator('.fin-ask').count() == 0) and page.locator('.fin').count() == 0)
            fin.click(); page.wait_for_selector('.fin-ask'); page.click('#finish-go')
            check('Yes finishes: the finish screen opens', until(lambda: page.locator('.fin').is_visible(), 6))
            check('once', page.locator('.fin-ask').count() == 0)
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors', not errs, errs)

        be = Backend(); seed(be)
        def s2(page):
            start(page)
            page.click('#sb-more'); page.click('#m-finish')
            check('the menu Finish asks too', until(lambda: page.locator('.fin-ask').is_visible()))
            page.click('#finish-go'); check('and finishes after Yes', until(lambda: page.locator('.fin').is_visible(), 6))
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (menu)', not errs, errs)

        be = Backend(); seed(be)
        def s3(page):
            start(page)
            for i in (2, 3):
                page.fill('#f-bench_%d-reps' % i, '10'); page.locator('.set:has(#f-bench_%d-load) .set-tick' % i).click(); page.wait_for_timeout(250)
            page.locator('#focus-finish').click(); page.wait_for_selector('.fin-ask')
            tx = page.locator('.fin-ask').inner_text()
            check('all sets done: no "not done yet" line', 'not done yet' not in tx, tx)
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (all done)', not errs, errs)

        be = Backend(); seed(be)
        def s4(page):
            start(page); page.locator('#focus-finish').click(); page.wait_for_selector('.fin-ask')
            tx = page.locator('.fin-ask').inner_text()
            low = tx.lower()
            check('Dutch: translated', 'weet je zeker dat je klaar bent met je training?' in low and 'ja, afronden' in low and 'doorgaan' in low and '2 sets zijn nog niet klaar' in low, tx)
        errs = session(pw, be, ALICE, s4, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
