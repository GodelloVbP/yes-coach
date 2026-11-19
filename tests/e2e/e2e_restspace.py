"""The rest bar takes room at the bottom: the end of the page and an open exercise list both stay above it, whichever came first, and when
the bar comes up at the end of the page, the page moves up with it."""
import datetime, subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for k in ('bench', 'row', 'curl'):
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': k.title(), 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': k, 'order': i, 'sets': 3, 'reps': '10', 'target': '', 'target_at': '2026-01-01', 'rest_s': 90, 'note': None} for i, k in enumerate(('bench', 'row', 'curl'))]}})

GEOM = """() => { const rb = document.querySelector('#restbar'); const fb = document.querySelector('.focusbar');
  const bars = [rb, fb].filter((b) => b && b.getClientRects().length).map((b) => b.getBoundingClientRect().top);
  const barTop = bars.length ? Math.min(...bars) : innerHeight;
  const els = [...document.querySelectorAll('main *')].filter((e) => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden' && e.offsetHeight > 0 && !e.closest('[hidden]') && !e.closest('.focusbar') && !e.closest('#restbar'));
  const low = els.reduce((m, e) => Math.max(m, e.getBoundingClientRect().bottom), 0);
  return { barTop: Math.round(barTop), lowest: Math.round(low), left: Math.round(document.documentElement.scrollHeight - innerHeight - scrollY), resting: document.body.classList.contains('resting') }; }"""

PK = """() => { const l = document.querySelector('.pk-list'); const r = l.getBoundingClientRect(); const rb = document.querySelector('#restbar'); const fb = document.querySelector('.focusbar');
  const bars = [rb, fb].filter((b) => b && b.getClientRects().length).map((b) => b.getBoundingClientRect().top); const bar = bars.length ? Math.min(...bars) : innerHeight;
  return { listBottom: Math.round(r.bottom), barTop: Math.round(bar), h: Math.round(r.height), resting: document.body.classList.contains('resting') }; }"""

def tick_at_bottom(page):
    """scroll to the end, then press the lowest visible set tick with the mouse (no automatic scrolling)"""
    page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)"); page.wait_for_timeout(500)
    box = page.evaluate("""() => { const t = [...document.querySelectorAll('.ex:not(.off) .set-tick')].filter((e) => e.getClientRects().length && e.getAttribute('aria-pressed') !== 'true').map((e) => e.getBoundingClientRect()).filter((r) => r.top > 80 && r.bottom < innerHeight - 10).pop(); return t ? { x: t.x + t.width / 2, y: t.y + t.height / 2 } : null; }""")
    return box

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # the end of the page with the bar up, in both views
        for mode in ('one exercise at a time', 'all exercises'):
            be = Backend(); seed(be)
            def sc(page, mode=mode):
                page.set_viewport_size({'width': 390, 'height': 760})
                page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start'); page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(400)
                if mode == 'all exercises':
                    page.get_by_text('All exercises').first.click(); page.wait_for_timeout(500)
                page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_selector('#restbar', state='visible'); page.wait_for_timeout(500)
                page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)"); page.wait_for_timeout(600)
                g = page.evaluate(GEOM)
                check('%s: at the end of the page nothing is under the bar' % mode, g['lowest'] <= g['barTop'] + 1 and g['left'] <= 2, g)
            errs = session(pw, be, ALICE, sc, width=390); check('no page errors (%s)' % mode, not errs, errs)

        # an open exercise list and the bar, in either order
        for order in ('the bar first, then the list', 'the list first, then the bar'):
            be = Backend(); seed(be)
            def sc3(page, order=order):
                page.set_viewport_size({'width': 390, 'height': 760})
                page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start'); page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(400)
                if order.startswith('the bar'):
                    page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_selector('#restbar', state='visible'); page.wait_for_timeout(500)
                    page.get_by_role('button', name='+ Add exercise').first.click(); page.wait_for_timeout(600)
                else:
                    page.get_by_role('button', name='+ Add exercise').first.click(); page.wait_for_timeout(600)
                    page.evaluate("() => window.scrollTo(0, 0)")
                    page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_selector('#restbar', state='visible'); page.wait_for_timeout(500)
                    page.evaluate("() => document.querySelector('.pk').scrollIntoView({block: 'start'})"); page.wait_for_timeout(500)
                g = page.evaluate(PK)
                check('%s: the bar is up' % order, g['resting'], g)
                check('%s: the list ends above the bar' % order, g['listBottom'] <= g['barTop'] + 1, g)
                check('%s: and still has room' % order, g['h'] >= 200, g)
            errs = session(pw, be, ALICE, sc3, width=390); check('no page errors (%s)' % order, not errs, errs)
        # the bar going away gives the room back to the list
        be = Backend(); seed(be)
        def sc4(page):
            page.set_viewport_size({'width': 390, 'height': 760})
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start'); page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(400)
            page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_selector('#restbar', state='visible'); page.wait_for_timeout(500)
            page.get_by_role('button', name='+ Add exercise').first.click(); page.wait_for_timeout(600)
            page.evaluate("() => document.activeElement && document.activeElement.blur()"); page.wait_for_timeout(900)   # stop typing: the bars come back
            check('the bar is back after typing stops', page.locator('#restbar').is_visible())
            h1 = page.evaluate(PK)['h']
            check('with the bar back, the list ends above it', page.evaluate(PK)['listBottom'] <= page.evaluate(PK)['barTop'] + 1, page.evaluate(PK))
            page.evaluate("() => document.querySelector('#rest-skip').click()"); page.wait_for_timeout(600)
            g = page.evaluate(PK)
            check('skipping the rest: the list grows into the room', not g['resting'] and g['h'] > h1, (h1, g))
        errs = session(pw, be, ALICE, sc4, width=390); check('no page errors (skip)', not errs, errs)
finally:
    server.terminate()
done()
