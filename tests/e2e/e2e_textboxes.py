"""Text boxes that do not grow (the ticket text) scroll when the text is longer than the box; boxes that grow (notes about your body) do not."""
import subprocess, time
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

LONG = '\n'.join('Line %d of a long text' % i for i in range(1, 31))
GEOM = "(sel) => { const t = document.querySelector(sel); return { ov: getComputedStyle(t).overflowY, sh: t.scrollHeight, ch: t.clientHeight, top: t.scrollTop }; }"

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        def phone(page):
            # the ticket form: 30 lines in a 5-line box
            page.wait_for_selector('#tab-feedback:not([hidden])', state='attached')
            page.click('#tab-settings'); page.click('#more-feedback'); page.wait_for_selector('#v-feedback #tk', state='visible')
            page.click('#tk >> text=Send something')
            ta = page.locator('#tk form textarea')
            ta.fill(LONG)
            g = page.evaluate(GEOM, '#tk form textarea')
            check('the ticket text is longer than its box', g['sh'] > g['ch'] + 100, g)
            check('so the box can scroll, it is not clipped', g['ov'] in ('auto', 'scroll'), g)
            ta.evaluate('t => { t.scrollTop = 0; }')  # typing left it at the end; start from the top
            ta.hover(); page.mouse.wheel(0, 300); page.wait_for_timeout(250)
            check('scrolling over it moves the text', page.evaluate(GEOM, '#tk form textarea')['top'] > 0, page.evaluate(GEOM, '#tk form textarea'))
            check('what was typed is all still there', ta.input_value() == LONG)

            check('no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, phone, width=390); check('no page errors', not errs, errs)

        # notes about your body (start screen) grow with the text, so they never need a scroll bar
        be = Backend(); be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1}})
        def wizard(page):
            page.wait_for_selector('#intro-notes', state='attached', timeout=8000)
            page.click('details.wz-more > summary'); page.wait_for_selector('#intro-notes', state='visible')
            n = page.locator('#intro-notes'); n.fill('Short note'); page.wait_for_timeout(150)
            s1 = page.evaluate(GEOM, '#intro-notes')
            n.fill(LONG); page.wait_for_timeout(250)
            s2 = page.evaluate(GEOM, '#intro-notes')
            check('a short note fits its box', s1['sh'] <= s1['ch'] + 1, s1)
            check('a long note makes the box taller, nothing is cut off', s2['ch'] > s1['ch'] + 100 and s2['sh'] <= s2['ch'] + 1, (s1, s2))
        errs = session(pw, be, ALICE, wizard, width=390); check('no page errors (start screen)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
