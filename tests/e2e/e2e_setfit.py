"""The numbers in a set row are never cut off: weights like 15,8 pin or 102,5 kg fit next to the RIR column on a small phone."""
import datetime, subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
OLD = (TD - datetime.timedelta(days=3)).isoformat()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be, unit, load, rir):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {'show_rir': rir}}})
    be.docs.append({'path': 'yc/exercises/fp', 'data': {'name': 'Face pull', 'group': 'Shoulders', 'category': 'strength', 'unit': unit, 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': 'fp', 'order': 1, 'sets': 3, 'reps': '15', 'target': '', 'target_at': '2026-01-01', 'rest_s': 60, 'note': None}]}})
    be.docs.append({'path': 'yc/sessions/' + OLD, 'data': {'date': OLD, 'template': 'a', 'sets': {
        'fp_%d' % i: {'ex': 'fp', 'n': i, 'kind': 'work', 'reps': 15, 'load': load, 'done': True, 'at': i} for i in (1, 2, 3)}}})

server = serve()
try:
    with sync_playwright() as pw:
        for width in (360, 390):
            for unit, load in (('stack', 15.8), ('kg', 102.5), ('stack', 113)):
                for rir in (True, False):
                    be = Backend(); seed(be, unit, load, rir)
                    def sc(page, width=width, unit=unit, load=load, rir=rir):
                        page.goto(BASE); page.wait_for_selector('text=Start Upper A', timeout=8000); page.click('text=Start Upper A')
                        page.wait_for_selector('#f-fp_1-load', state='visible'); page.wait_for_timeout(400)
                        page.fill('#f-fp_1-load', str(load)); page.wait_for_timeout(200)  # typed: the edited dot shows
                        r = page.evaluate("""() => ['#f-fp_1-reps', '#f-fp_1-load', '#f-fp_2-load'].map((s) => { const i = document.querySelector(s); return [s, i.scrollWidth > i.clientWidth + 1]; })""")
                        check('%dpx, %s %s, RIR %s: nothing cut off' % (width, unit, load, 'on' if rir else 'off'), not any(c for _, c in r), r)
                        if rir:
                            dot = page.evaluate("""() => { const f = document.querySelector('#f-fp_1-load').parentElement; const d = getComputedStyle(f.querySelector('small'), '::after'); return d.position; }""")
                            check('%dpx, %s: the edited dot takes no width' % (width, load), dot == 'absolute', dot)
                    errs = session(pw, be, ALICE, sc, width=width); check('no page errors', not errs, errs)
finally:
    server.terminate()
done()
