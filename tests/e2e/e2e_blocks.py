"""Blocks: every function or option on a page sits in a block, and neighbouring blocks take turns between two tints."""
import datetime, subprocess, time
from harness import *
from harness import EXTERNAL

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
pw = sync_playwright().start()
SAT = datetime.datetime(2026, 11, 7, 10, 0)
TONES = """() => [...document.querySelectorAll('.view:not([hidden]) .blk')].filter((b) => b.getClientRects().length)
  .map((b) => ({ id: b.id || b.className, tone: b.dataset.tone, bg: getComputedStyle(b).backgroundColor }))"""

def alternate(page, name):
    page.wait_for_timeout(400)
    t = page.evaluate(TONES)
    check(name + ': has blocks', len(t) >= 2, t)
    check(name + ': neighbours never share a tint', all(a['tone'] != b['tone'] for a, b in zip(t, t[1:])), t)
    check(name + ': the tints differ on screen', all(a['bg'] != b['bg'] for a, b in zip(t, t[1:])), t)
    return t

be = Backend()
def run(page):
    until(lambda: page.is_visible('#wz-go'))
    for _ in range(3): page.click('#wz-go'); page.wait_for_timeout(150)
    until(lambda: page.is_visible('#wz-start')); page.click('#wz-start'); until(lambda: page.is_visible('#btn-start'))
    t = alternate(page, 'Train')
    check('Train: today, the week and the month are three blocks', [x['id'] for x in t] == ['today-card', 'week', 'ahead'], t)
    for tab in ('plan', 'progress', 'food'):
        page.click('#tab-' + tab); alternate(page, tab)
    # a block that appears in between: the turns are worked out again
    page.evaluate("document.querySelector('#fd-meals').hidden = false")
    alternate(page, 'Food with Your meals shown')
    page.click('#tab-settings'); page.wait_for_timeout(500)
    rows = page.evaluate("[...document.querySelectorAll('#v-settings .blk-row')].filter((r) => r.getClientRects().length).map((r) => r.dataset.tone)")
    check('More: groups take turns', 'a' in rows and 'b' in rows, rows)
    check('no sideways scroll on a phone', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
errs = session(pw, be, ALICE, run, width=390, clock=SAT)
check('no page errors', not errs, errs)
check('nothing left the machine', not EXTERNAL, EXTERNAL[:3])
pw.stop()
server.terminate()
done()
