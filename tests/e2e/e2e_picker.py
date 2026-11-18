"""The exercise picker in a workout: the list ends above the bottom bar, so the last results are reachable, on a tall and a short phone."""
import datetime, subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for k, nm in (('a', 'Bench press'), ('b', 'Row'), ('c', 'Squat'), ('d', 'Curl')):
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': nm, 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': k, 'order': i, 'sets': 3, 'reps': '10', 'target': '', 'target_at': '2026-01-01', 'rest_s': 60, 'note': None} for i, k in enumerate('abcd')]}})

GEOM = """() => { const l = document.querySelector('.pk-list'); const r = l.getBoundingClientRect(); const fb = document.querySelector('.focusbar'); const bar = fb && fb.getClientRects().length ? fb.getBoundingClientRect().top : innerHeight;
  const items = [...l.querySelectorAll('.pk-item')].filter((e) => e.offsetParent); const last = items[items.length - 1]; const lb = last ? last.getBoundingClientRect().bottom : 0;
  return { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), bar: Math.round(bar), lastBottom: Math.round(lb), atEnd: l.scrollTop + l.clientHeight >= l.scrollHeight - 2 }; }"""

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        for w, h in ((390, 844), (360, 640)):
            be = Backend(); seed(be)
            def sc(page, w=w, h=h):
                page.set_viewport_size({'width': w, 'height': h})
                page.goto(BASE); page.wait_for_selector('text=Start Upper A', timeout=8000); page.click('text=Start Upper A')
                page.wait_for_selector('#f-a_1-load', state='visible'); page.wait_for_timeout(500)
                page.get_by_role('button', name='+ Add exercise').first.click(); page.wait_for_timeout(500)
                g = page.evaluate(GEOM)
                check('%dx%d: the list ends above the bar' % (w, h), g['bottom'] <= g['bar'] + 1, g)
                check('%dx%d: the list has room (at least 200px)' % (w, h), g['h'] >= 200, g)
                page.fill('.pk-search', 'raise'); page.wait_for_timeout(400)
                page.evaluate("() => { const l = document.querySelector('.pk-list'); l.scrollTop = l.scrollHeight; }"); page.wait_for_timeout(200)
                g = page.evaluate(GEOM)
                check('%dx%d: scrolled to its end, the last result is above the bar' % (w, h), g['atEnd'] and g['lastBottom'] <= g['bar'] + 1, g)
                page.keyboard.press('Escape')
            errs = session(pw, be, ALICE, sc, width=w); check('no page errors %dx%d' % (w, h), not errs, errs)
finally:
    server.terminate()
done()
