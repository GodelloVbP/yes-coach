"""A rolling plan follows a swap: Back instead of Legs today means Legs is next, also over into next week."""
import datetime, subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

SUN = datetime.datetime(2026, 11, 8, 10, 0)
D = SUN.date().isoformat()
ALL = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

def seed(be, history=None):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'schedule': {'enabled': True, 'mode': 'rotation', 'days': ALL, 'rotation': ['legs', 'back', 'push']}}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    for i, (id, nm, k) in enumerate([('push', 'Push', 'Push'), ('back', 'Back', 'Pull'), ('legs', 'Legs', 'Legs')]):
        be.docs.append({'path': 'yc/templates/' + id, 'data': {'name': nm, 'order': i, 'kind': k, 'focus': '', 'items': [{'ex': 'bench', 'order': 1, 'sets': 2, 'reps': '8', 'target': '', 'target_at': D, 'rest_s': 90, 'note': None}]}})
    for date, tpl in (history or []):
        be.docs.append({'path': 'yc/sessions/' + date, 'data': {'date': date, 'template': tpl, 'sets': {'bench_1': {'ex': 'bench', 'n': 1, 'kind': 'work', 'kg': 60, 'reps': 8, 'done': True, 'at': 1}}}})

def nexts(page):
    """{day name: its 'next ...' label on the Plan page}"""
    page.click('#tab-plan'); page.wait_for_selector('.pw-card', timeout=8000)
    return page.evaluate("Object.fromEntries([...document.querySelectorAll('.pw-card')].map((c) => [c.querySelector('.pw-name').textContent, c.querySelector('.pw-wd').textContent]))")

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # 1. Sunday: Legs is planned, Back is swapped in before training. Next week starts with Legs, not Back.
        be = Backend(); seed(be)
        def s1(page):
            page.wait_for_selector('#today-card .t-head', timeout=8000)
            check('Legs is planned today', 'LEGS' in page.inner_text('#today-card .t-head').upper())
            page.click('#btn-swap'); page.click('.swaprow[aria-label^="Train Back"]')
            check('the toast says Legs is next on Monday', until(lambda: 'Legs is next on Mon 9 Nov.' in (page.evaluate("(document.querySelector('#toast')||document.body).innerText") or '')))
            page.click("#sb-back"); page.wait_for_timeout(300)
            n = nexts(page)
            check('Legs is next on Monday', 'next Mon 9 Nov' in n['Legs'], n)
            check('Back is not tomorrow', 'next Mon' not in n['Back'] and 'next Tue' not in n['Back'], n)
            check('Push follows Legs', 'next Tue 10 Nov' in n['Push'], n)
        errs = session(pw, be, ALICE, s1, width=390, clock=SUN); check('no page errors (swap)', not errs, errs)

        # 2. Back was trained today instead of Legs (logged, no swap record): the same order afterwards
        be = Backend(); seed(be, [(D, 'back')])
        def s2(page):
            page.wait_for_selector('#today-card', timeout=8000)
            n = nexts(page)
            check('logged Back first: Legs is next', 'next Mon 9 Nov' in n['Legs'], n)
            check('and Push after it', 'next Tue 10 Nov' in n['Push'], n)
        errs = session(pw, be, ALICE, s2, width=390, clock=SUN); check('no page errors (logged)', not errs, errs)

        # 3. Nothing out of order: the list rolls on as before
        be = Backend(); seed(be, [(D, 'legs')])
        def s3(page):
            page.wait_for_selector('#today-card', timeout=8000)
            n = nexts(page)
            check('in order: Back is next', 'next Mon 9 Nov' in n['Back'], n)
            check('in order: Push after it', 'next Tue 10 Nov' in n['Push'], n)
        errs = session(pw, be, ALICE, s3, width=390, clock=SUN); check('no page errors (in order)', not errs, errs)

        # 4. Push done ahead of Legs and Back: the two it passed come next, in their order
        be = Backend(); seed(be, [(D, 'push')])
        def s4(page):
            page.wait_for_selector('#today-card', timeout=8000)
            n = nexts(page)
            check('Push first: Back is next, then Legs', 'next Mon 9 Nov' in n['Back'] and 'next Tue 10 Nov' in n['Legs'], n)
        errs = session(pw, be, ALICE, s4, width=390, clock=SUN); check('no page errors (two ahead)', not errs, errs)
finally:
    server.terminate()
done()
