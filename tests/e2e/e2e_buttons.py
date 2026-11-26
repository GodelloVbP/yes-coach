"""One colour language for buttons: orange with blue letters confirms, white with blue letters goes back or does anything else. Checked on the
screens people use (not disabled ones). The rest bar's text sits in the middle of the bar."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'schedule': {'enabled': True, 'mode': 'rotation', 'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], 'rotation': ['a']}}})
    for k, nm in (('bench', 'Bench press'), ('row', 'Row')):
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': nm, 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': k, 'order': i, 'sets': 3, 'reps': '10', 'target': '', 'target_at': '2026-01-01', 'rest_s': 60, 'note': None} for i, k in enumerate(('bench', 'row'))]}})

AUDIT = """() => {
  const rgb = (c) => { const e = document.createElement('i'); e.style.color = c; document.body.append(e); const v = getComputedStyle(e).color; e.remove(); return v; };
  const root = getComputedStyle(document.documentElement);
  const v = (n) => rgb(root.getPropertyValue(n).trim());
  const ok = { bg: [v('--pop'), v('--paper')], fg: [v('--on-pop'), v('--ink')] };
  const bad = [];
  document.querySelectorAll('.skew, .pk-go').forEach((b) => {
    if (!b.getClientRects().length || b.disabled || b.hasAttribute('disabled')) return;
    if (b.closest('[hidden]')) return;
    const c = getComputedStyle(b);
    const pair = (c.backgroundColor === ok.bg[0] && c.color === ok.fg[0]) || (c.backgroundColor === ok.bg[1] && c.color === ok.fg[1]);
    if (!pair) bad.push((b.id || b.className) + ' "' + b.textContent.trim().slice(0, 24) + '" ' + c.backgroundColor + ' / ' + c.color);
  });
  return bad;
}"""

server = subprocess.Popen(['python3', '-m', 'http.server', str(PORT), '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def sc(page):
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.wait_for_timeout(300)
            check('Train: every button is orange or white', not page.evaluate(AUDIT), page.evaluate(AUDIT))
            page.click('#btn-start'); page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(400)
            check('workout: every button is orange or white', not page.evaluate(AUDIT), page.evaluate(AUDIT))
            # rest bar: tick a set
            page.fill('#f-bench_1-reps', '10'); page.locator('.set:has(#f-bench_1-load) .set-tick').click(); page.wait_for_selector('#restbar', state='visible'); page.wait_for_timeout(500)
            check('rest bar: buttons are white with blue letters', not page.evaluate(AUDIT), page.evaluate(AUDIT))
            g = page.evaluate("""() => { const b = document.querySelector('#restbar').getBoundingClientRect(); const bar = { top: b.top, mid: b.top + (b.height - parseFloat(getComputedStyle(document.querySelector('#restbar')).paddingBottom || 0)) / 2 };
              const c = (sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return r.top + r.height / 2; }; return { mid: bar.mid, t: c('#rest-t'), lab: c('#rest-lab'), btn: c('#rest-add') }; }""")
            check('rest bar: the time sits in the middle', abs(g['t'] - g['mid']) <= 3, g)
            check('rest bar: the label too', abs(g['lab'] - g['mid']) <= 3, g)
            check('rest bar: and the buttons', abs(g['btn'] - g['mid']) <= 3, g)
            # picker
            page.get_by_role('button', name='+ Add exercise').first.click(); page.wait_for_timeout(500)
            check('picker: Add is orange, the rest white', not page.evaluate(AUDIT), page.evaluate(AUDIT))
            page.keyboard.press('Escape')
            # finish question
            page.locator('#focus-finish').click(); page.wait_for_selector('.fin-ask')
            r = page.evaluate("""() => { const q = (s) => getComputedStyle(document.querySelector(s)); const rgb = (c) => { const e = document.createElement('i'); e.style.color = c; document.body.append(e); const v = getComputedStyle(e).color; e.remove(); return v; };
              const root = getComputedStyle(document.documentElement); return { go: q('#finish-go').backgroundColor, keep: q('.fin-ask .confirm-keep').backgroundColor, pop: rgb(root.getPropertyValue('--pop').trim()), paper: rgb(root.getPropertyValue('--paper').trim()) }; }""")
            check('Finish question: Yes is orange', r['go'] == r['pop'], r)
            check('Finish question: Keep going is white', r['keep'] == r['paper'], r)
            check('Finish question: every button is orange or white', not page.evaluate(AUDIT), page.evaluate(AUDIT))
        errs = session(pw, be, ALICE, sc, width=390); check('no page errors', not errs, errs)

        be = Backend(); seed(be)
        def sc2(page):
            page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            for tab in ('#tab-plan', '#tab-food', '#tab-progress', '#tab-settings'):
                if page.locator(tab).count():
                    page.click(tab); page.wait_for_timeout(500)
                    check('%s: every button is orange or white' % tab, not page.evaluate(AUDIT), page.evaluate(AUDIT))
        errs = session(pw, be, ALICE, sc2, width=390); check('no page errors (tabs)', not errs, errs)
finally:
    server.terminate()
done()
