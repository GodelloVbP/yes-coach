"""When the rest bar comes up the page does not jump: scrolled near the end (but not at it) the page stays where it is; at the very end
it moves up with the bar so the last content is not left under it. Rebuilding the cards (a weight step) keeps the scroll place."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

src = open(__file__.replace('e2e_restscroll', 'e2e_restbar')).read().split("def tick")[0]
exec(src)

def tickjs(page, key):
    b = page.locator('.set:has(#f-%s-load) .set-tick' % key).bounding_box()
    page.mouse.click(b['x'] + b['width'] / 2, b['y'] + b['height'] / 2)
def maxy(page): return page.evaluate('document.documentElement.scrollHeight - innerHeight')

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            page.set_viewport_size({'width': 390, 'height': 844})
            page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('text=Start Push day'); page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(400)
            page.fill('#f-bench_1-load', '60'); page.fill('#f-bench_1-reps', '8'); page.fill('#f-bench_2-load', '60'); page.fill('#f-bench_2-reps', '8'); page.fill('#f-bench_3-load', '60'); page.fill('#f-bench_3-reps', '8')
            m = maxy(page); y = m - 60
            check('the page can scroll', m > 150, m)
            page.evaluate('scrollTo(0, %d)' % y); page.wait_for_timeout(300)
            tickjs(page, 'bench_3')
            check('the bar comes up', until(lambda: vis(page, '#restbar')))
            page.wait_for_timeout(900)
            check('60 px from the end: the page stays where it is', abs(page.evaluate('scrollY') - y) <= 2, (y, page.evaluate('scrollY')))
            # at the very end: the page moves up with the bar
            page.click('#rest-skip') if page.locator('#rest-skip').count() else page.locator('.rest-acts button').nth(1).click()
            check('the bar goes away', until(lambda: not vis(page, '#restbar')))
            m = maxy(page); page.evaluate('scrollTo(0, %d)' % m); page.wait_for_timeout(300)
            tickjs(page, 'bench_2')
            check('the bar comes up at the end', until(lambda: vis(page, '#restbar')))
            page.wait_for_timeout(600)
            check('at the very end: still at the end, nothing left under the bar', abs(page.evaluate('scrollY') - maxy(page)) <= 2, (page.evaluate('scrollY'), maxy(page)))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors', not errs, errs)
finally:
    server.terminate()
done()
