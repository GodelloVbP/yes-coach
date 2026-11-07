"""The bottom bar: Request is a tab of its own, and six labels fit in every language on a phone."""
import subprocess, time
from harness import *
from harness import EXTERNAL

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
pw = sync_playwright().start()
FIT = """() => [...document.querySelectorAll('.mainnav .tab:not([hidden]):not(.tab-sub)')].map((t) => {
  const s = t.querySelector('span'); const r = document.createRange(); r.selectNodeContents(s);
  return { label: s.textContent.trim(), text: r.getBoundingClientRect().width, tab: t.getBoundingClientRect().width }; })"""
for lang in ('en', 'nl', 'de', 'fr', 'es', 'it'):
    for w in (360, 390, 430):
        def run(page):
            page.wait_for_selector('#tab-feedback:not([hidden])', state='attached'); page.wait_for_timeout(500)
            t = page.evaluate(FIT)
            check('%s %d: six labels' % (lang, w), len(t) == 6, t)
            check('%s %d: every label fits its tab' % (lang, w), all(x['text'] <= x['tab'] + 1 for x in t), [x for x in t if x['text'] > x['tab'] + 1])
            check('%s %d: no sideways scroll' % (lang, w), page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        errs = session(pw, Backend(), ALICE, run, width=w, lang=lang)
        check('%s %d: no page errors' % (lang, w), not errs, errs)
def en(page):
    page.wait_for_selector('#tab-feedback:not([hidden])', state='attached')
    check('Request label', page.inner_text('#tab-feedback span').strip().lower() == 'request')
    check('the tab is named for a screen reader', page.get_attribute('#tab-feedback', 'aria-label') == 'Feedback and requests')
    page.click('#tab-feedback'); page.wait_for_selector('#tk', state='visible')
    check('one tap opens the request form', page.get_attribute('#tab-feedback', 'aria-selected') == 'true' and page.is_visible('#tk'))
    check('the orange marker sits on Request', page.evaluate("getComputedStyle(document.querySelector('#tab-feedback'), '::after').content") != 'none')
errs = session(pw, Backend(), ALICE, en, width=390); check('no page errors', not errs, errs)
check('nothing left the machine', not EXTERNAL, EXTERNAL[:3])
pw.stop(); server.terminate(); done()
