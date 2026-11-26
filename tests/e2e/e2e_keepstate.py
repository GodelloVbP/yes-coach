"""+ Set and - add or take away one row and touch nothing else: an open How to do it, an open Plates panel, a typed note and typed reps stay.
The cases that still rebuild the cards (+ Warm-up) put the open panels back."""
import datetime, subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
T = TD.isoformat()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    old = (TD - datetime.timedelta(days=4)).isoformat()
    be.docs.append({'path': 'yc/sessions/' + old, 'data': {'date': old, 'template': 'a', 'sets': {
        'bench_%d' % n: {'ex': 'bench', 'n': n, 'kind': 'work', 'reps': 8, 'load': 80, 'done': True, 'at': n} for n in (1, 2, 3)}}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Barbell bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher', 'library_id': 'l04'}})
    be.docs.append({'path': 'yc/exercises/row', 'data': {'name': 'Row', 'group': 'Back', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': k, 'order': i, 'sets': 3, 'reps': '10', 'target': '', 'target_at': '2026-01-01', 'rest_s': 60, 'note': None} for i, k in enumerate(('bench', 'row'))]}})

STATE = """() => { const ex = document.querySelector('.ex:not(.off)'); const q = (s) => ex.querySelector(s);
  const pb = q('.ex-plates');
  return { how: q('.ex-how') ? q('.ex-how').open : null, plates: pb ? pb.getAttribute('aria-expanded') === 'true' : null, note: q('.nt-in-ex .nt-text') ? q('.nt-in-ex .nt-text').value : null,
           reps2: document.querySelector('#f-bench_2-reps').value, rows: ex.querySelectorAll('.set:not(.set-head)').length, nodes: ex.id || '', all: document.querySelectorAll('.set:not(.set-head)').length }; }"""

def stored(be, key):
    d = next((d['data'] for d in reversed(be.docs) if d['path'] == 'yc/sessions/' + T), {})
    return (d.get('sets') or {}).get(key) or {}

server = serve()
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def sc(page):
            page.set_viewport_size({'width': 390, 'height': 700})
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start'); page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(400)
            page.locator('.ex-how summary').first.click()
            page.locator('.ex-plates').first.click(); page.wait_for_timeout(200)
            page.get_by_role('button', name='Note about Barbell bench press').click(); page.wait_for_timeout(200)
            page.locator('.ex:visible .nt-in-ex .nt-text').first.fill('felt heavy')
            page.fill('#f-bench_2-reps', '9')
            before = page.evaluate(STATE)
            check('set up: how-to open, plates open, note and reps typed', before['how'] and before['plates'] and before['note'] == 'felt heavy' and before['reps2'] == '9', before)
            mark = page.evaluate("() => { const e = document.querySelector('.ex:not(.off)'); e.dataset.mark = 'same'; return e.dataset.mark; }")
            # + Set
            page.locator('.ex:visible .ex-actions .skew', has_text='+ Set').click(); page.wait_for_timeout(600)
            a = page.evaluate(STATE)
            check('+ Set: one row more', a['rows'] == before['rows'] + 1, (before, a))
            check('+ Set: How to do it stays open', a['how'] is True, a)
            check('+ Set: Plates stays open', a['plates'] is True, a)
            check('+ Set: the typed note stays', a['note'] == 'felt heavy', a)
            check('+ Set: the typed reps stay', a['reps2'] == '9', a)
            check('+ Set: the card itself is the same element, not a new one', page.evaluate("() => document.querySelector('.ex:not(.off)').dataset.mark") == 'same')
            check('+ Set: the other exercise has the same rows', a['all'] == before['all'] + 1, (before, a))
            # the new row works
            page.fill('#f-bench_4-load', '60'); page.fill('#f-bench_4-reps', '8'); page.locator('.set:has(#f-bench_4-load) .set-tick').click(); page.wait_for_timeout(500)
            check('the new row can be ticked and is stored', until(lambda: stored(be, 'bench_4').get('load') == 60 and stored(be, 'bench_4').get('reps') == 8), stored(be, 'bench_4'))
            # -
            page.fill('#f-bench_4-reps', '8')
            page.locator('.set:has(#f-bench_4-load) .set-tick').click(); page.wait_for_timeout(300)   # untick so it can go
            page.locator('.ex:visible .ex-actions button[aria-label^="Remove the last set"]').first.click(); page.wait_for_timeout(500)
            r = page.evaluate(STATE)
            check('−: back to the first number of rows', r['rows'] == before['rows'], (before, r))
            check('−: panels, note and reps stay', r['how'] and r['plates'] and r['note'] == 'felt heavy' and r['reps2'] == '9', r)
            check('−: the card is still the same element', page.evaluate("() => document.querySelector('.ex:not(.off)').dataset.mark") == 'same')
            # + Warm-up rebuilds the cards but puts the open panels back
            warm = page.locator('.ex:visible .ex-warm')
            check('the + Warm-up button is there (the exercise has history)', warm.count() == 1 and warm.first.is_visible())
            before_rows = page.evaluate(STATE)['rows']
            warm.first.click(); page.wait_for_timeout(700)
            w = page.evaluate(STATE)
            check('+ Warm-up added rows (so the cards were rebuilt)', w['rows'] > before_rows, (before_rows, w))
            check('+ Warm-up (rebuild): How to do it and Plates are back open', w['how'] and w['plates'], w)
            check('+ Warm-up (rebuild): the typed note is still there', w['note'] == 'felt heavy', w)
        errs = session(pw, be, ALICE, sc, width=390); check('no page errors', not errs, errs)
finally:
    server.terminate()
done()
