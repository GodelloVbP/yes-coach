"""Moving between exercises on a phone: the new card slides in from the side you move towards, and the page scrolls to the first open set."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today().isoformat()
def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for ex, nm, g in (('bench', 'Bench press', 'Chest'), ('row', 'Row', 'Back'), ('curl', 'Curl', 'Arms')):
        be.docs.append({'path': 'yc/exercises/' + ex, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = lambda ex, o, n: {'ex': ex, 'order': o, 'sets': n, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [it('bench', 1, 10), it('row', 2, 2), it('curl', 3, 2)]}})

def tick(page, key): page.locator('.set:has(#f-%s-load) .set-tick' % key).click()
def scroll_settled(page):
    """true once the page has stopped scrolling"""
    a = page.evaluate('scrollY'); page.wait_for_timeout(250); return page.evaluate('scrollY') == a
def in_view(page, sel):
    return page.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; }", sel)
def dx(page, sel): return page.evaluate("(s) => document.querySelector(s).closest('.ex').style.getPropertyValue('--dx')", sel)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def phone(page):
            page.set_viewport_size({'width': 390, 'height': 700})
            page.goto(BASE); page.wait_for_selector('#v-train', state='visible')
            page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('text=Start Push day')
            page.wait_for_selector('#sess-chips', state='attached')
            page.wait_for_timeout(300)
            for n in range(1, 9):
                page.fill('#f-bench_%d-load' % n, '60'); page.fill('#f-bench_%d-reps' % n, '8'); tick(page, 'bench_%d' % n)
            check('eight sets ticked', until(lambda: '8/10' in page.locator('.fchip >> nth=0').inner_text()), page.locator('.fchip >> nth=0').inner_text())

            page.click('#focus-next')
            check('Next shows the next exercise', until(lambda: vis(page, '#f-row_1-load') and not vis(page, '#f-bench_9-load')))
            check('moving forward: the card slides in from the right', dx(page, '#f-row_1-load') == '28px', dx(page, '#f-row_1-load'))
            check('the card plays the entrance animation', page.evaluate("document.querySelector('#f-row_1-load').closest('.ex').classList.contains('enter')"))
            check('a fresh exercise sits at the top', until(lambda: scroll_settled(page) and page.evaluate('scrollY') == 0), page.evaluate('scrollY'))

            page.click('.fchip >> nth=0')
            check('moving back: the card slides in from the left', dx(page, '#f-bench_9-load') == '-28px', dx(page, '#f-bench_9-load'))
            check('the page scrolls down to the first open set', until(lambda: scroll_settled(page) and in_view(page, '.set:has(#f-bench_9-load)'), 8), page.evaluate('scrollY'))
            check('and not all the way down', page.evaluate('scrollY') > 0)

            page.click('#focus-next')
            check('the next exercise starts at the top again', until(lambda: scroll_settled(page) and page.evaluate('scrollY') == 0 and vis(page, '#f-row_1-load')))
            check('no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, phone, width=390); check('no page errors (phone)', not errs, errs)

        be = Backend(); seed(be)
        def calm(page):
            page.emulate_media(reduced_motion='reduce')
            page.set_viewport_size({'width': 390, 'height': 700})
            page.goto(BASE); page.wait_for_selector('#v-train', state='visible')
            page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('text=Start Push day')
            page.wait_for_selector('#sess-chips', state='attached')
            page.click('#focus-next')
            check('reduced motion: the exercise still changes', until(lambda: vis(page, '#f-row_1-load')))
            check('reduced motion: no entrance animation', not page.evaluate("document.querySelector('#f-row_1-load').closest('.ex').classList.contains('enter')"))
        errs = session(pw, be, ALICE, calm, width=390); check('no page errors (reduced motion)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
