"""Pressing a button gives feedback at once: a tint and a small press on the skewed buttons (Add exercise, + Set, Next exercise, Add in the
picker); the tint goes again after the press."""
import datetime, subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for k, nm in (('a', 'Bench press'), ('b', 'Row')):
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': nm, 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': k, 'order': i, 'sets': 2, 'reps': '10', 'target': '', 'target_at': '2026-01-01', 'rest_s': 60, 'note': None} for i, k in enumerate('ab')]}})

LOOK = """(el) => { const c = getComputedStyle(el); const m = c.transform.match(/matrix\\(([^)]+)\\)/); const v = m ? m[1].split(',').map(Number) : [1, 0, 0, 1]; return { shadow: c.boxShadow, d: v[3] }; }"""

def pressed(page, loc, name):
    el = loc.first; el.scroll_into_view_if_needed(); b = el.bounding_box()
    page.mouse.move(b['x'] + b['width'] / 2, b['y'] + b['height'] / 2); page.mouse.down(); page.wait_for_timeout(60)
    on = el.evaluate(LOOK)
    check('%s: tinted while pressed' % name, on['shadow'] != 'none', on)
    check('%s: shrinks a little while pressed' % name, 0.9 < on['d'] < 0.99, on)
    page.mouse.move(2, 2); page.mouse.up(); page.wait_for_timeout(500)  # moved off the button: no click
    off = el.evaluate(LOOK)
    check('%s: back to normal after' % name, off['shadow'] == 'none' and abs(off['d'] - 1) < 0.01, off)


def quick_tap(page, loc, name):
    """A tap that is over in a few milliseconds still shows: a ripple where the finger went (it survives a screen that is rebuilt or a button that
    hides), and the pressed look on a button that stays."""
    el = loc.first; el.scroll_into_view_if_needed(); b = el.bounding_box()
    page.mouse.move(b['x'] + b['width'] / 2, b['y'] + b['height'] / 2); page.mouse.down(); page.mouse.up(); page.wait_for_timeout(60)
    check('%s: a quick tap shows a ripple' % name, page.locator('.press-ripple').count() >= 1)
    page.wait_for_timeout(600)
    check('%s: and it goes again' % name, page.locator('.press-ripple').count() == 0)

server = subprocess.Popen(['python3', '-m', 'http.server', str(PORT), '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def sc(page):
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start')
            page.wait_for_selector('#f-a_1-load', state='visible'); page.wait_for_timeout(400)
            pressed(page, page.locator('.ex:visible .ex-actions .skew', has_text='+ Set'), '+ Set')
            pressed(page, page.get_by_role('button', name='+ Add exercise'), 'Add exercise')
            quick_tap(page, page.locator('.ex:visible .ex-actions .skew', has_text='+ Set'), '+ Set')
            quick_tap(page, page.get_by_role('button', name='Note about Bench press'), '✎ note icon')
            quick_tap(page, page.locator('#sb-more'), '⋯ menu'); page.keyboard.press('Escape')
            pressed(page, page.locator('.focusbar .skew.next'), 'Next exercise')
            page.get_by_role('button', name='+ Add exercise').first.click(); page.wait_for_timeout(400)
            pressed(page, page.locator('.pk-go').first, 'Add (picker)')
        errs = session(pw, be, ALICE, sc, width=390); check('no page errors', not errs, errs)
finally:
    server.terminate()
done()
