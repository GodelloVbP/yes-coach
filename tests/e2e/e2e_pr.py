"""A personal record gets a block: in the workout under the exercise and on the finish screen. It says what was beaten, by how much, where
the previous best was, and one line on what the step means (small, solid or big)."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
T = TD.isoformat()
BACK = (TD - datetime.timedelta(days=5)).isoformat()
MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
BACK_TXT = '%d %s' % (int(BACK[8:10]), MON[int(BACK[5:7]) - 1])
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be, prev=60, extra=False):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/exercises/pull', 'data': {'name': 'Pull-up', 'group': 'Back', 'category': 'strength', 'unit': 'bw', 'better': 'higher'}})
    be.docs.append({'path': 'yc/exercises/row', 'data': {'name': 'Row', 'group': 'Back', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    it = lambda ex, o: {'ex': ex, 'order': o, 'sets': 2, 'reps': '8', 'target': '', 'target_at': '2026-01-01', 'rest_s': 90, 'note': None}
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': '', 'weekday': WD, 'items': [it('bench', 1), it('pull', 2), it('row', 3)]}})
    sets = {}
    for n in (1, 2): sets['bench_%d' % n] = {'ex': 'bench', 'n': n, 'kind': 'work', 'reps': 8, 'load': prev, 'done': True, 'at': n}
    for n in (1, 2): sets['pull_%d' % n] = {'ex': 'pull', 'n': n, 'kind': 'work', 'reps': 5, 'done': True, 'at': 10 + n}
    for n in (1, 2): sets['row_%d' % n] = {'ex': 'row', 'n': n, 'kind': 'work', 'reps': 8, 'load': 50, 'done': True, 'at': 20 + n}
    be.docs.append({'path': 'yc/sessions/' + BACK, 'data': {'date': BACK, 'template': 'push', 'sets': sets}})

def open_day(page):
    page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
    page.click('#btn-start'); page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(300)

def log(page, key, load, reps):
    if load is not None: page.fill('#f-%s-load' % key, str(load))
    page.fill('#f-%s-reps' % key, str(reps))
    page.locator('.set:has(#f-%s-reps) .set-tick' % key).click(); page.wait_for_timeout(250)

def block(page, name):
    return page.locator('.ex', has=page.locator('.ex-name', has_text=name)).locator('.ex-pr')

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. a solid step in the workout: bench 60 -> 62.5 (4%)
        be = Backend(); seed(be)
        def s1(page):
            open_day(page)
            check('no block before a record', block(page, 'Bench').is_hidden())
            log(page, 'bench_1', 60, 8)
            check('the same weight is not a record: no block', block(page, 'Bench').is_hidden())
            log(page, 'bench_2', 62.5, 8)
            b = block(page, 'Bench')
            check('a record: the block shows', until(lambda: b.is_visible()))
            tx = b.inner_text()
            check('it says New personal record, with the set', 'New personal record' in tx and '62.5 kg × 8' in tx, tx)
            check('what was beaten, by how much, and when', ('2.5 kg more than your previous best (60 kg × 8 on %s).' % BACK_TXT) in tx, tx)
            check('a solid step: the line says so', 'Stronger than you have ever been on this lift.' in tx, tx)
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (solid)', not errs, errs)

        # ---- 2. a big step and a small one
        for load, line in ((70, 'A big step up on this lift. Well earned.'), (60.5, 'A small step, and it counts: you are ahead of every earlier session.')):
            be = Backend(); seed(be)
            def s2(page, load=load, line=line):
                open_day(page); log(page, 'bench_1', load, 8)
                b = block(page, 'Bench'); until(lambda: b.is_visible())
                check('%s kg: %s' % (load, line[:20]), line in b.inner_text(), b.inner_text())
            errs = session(pw, be, ALICE, s2, width=390); check('no page errors (%s)' % load, not errs, errs)

        # ---- 3. bodyweight reps, and the finish screen with two records
        be = Backend(); seed(be)
        def s3(page):
            open_day(page); log(page, 'bench_1', 65, 8)
            page.get_by_role('button', name=re.compile('Next exercise', re.I)).first.click(); page.wait_for_selector('#f-pull_1-reps', state='visible'); page.wait_for_timeout(300)
            log(page, 'pull_1', None, 8)
            b = block(page, 'Pull'); until(lambda: b.is_visible())
            check('reps: 3 more than 5, a big step', ('3 reps more than your previous best (5 reps on %s).' % BACK_TXT) in b.inner_text() and 'big step' in b.inner_text(), b.inner_text())
            page.wait_for_timeout(900); page.locator('button.skew:visible', has_text=re.compile(r'^\s*Finish', re.I)).first.click(); page.click('#finish-go')
            page.wait_for_selector('.fin-prs li', timeout=6000)
            fin = page.locator('.fin').inner_text()
            check('the finish screen: two blocks', page.locator('.fin-prs li').count() == 2, fin)
            check('and a line for the session', '2 lifts beat their previous best today. A strong session.' in fin, fin)
            check('each block says what it beat', ('5 kg more than your previous best (60 kg × 8 on %s).' % BACK_TXT) in fin and ('3 reps more than your previous best (5 reps on %s).' % BACK_TXT) in fin, fin)
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (finish)', not errs, errs)

        # ---- 4. Dutch
        be = Backend(); seed(be)
        def s4(page):
            open_day(page); log(page, 'bench_1', 62.5, 8)
            b = block(page, 'Bench'); until(lambda: b.is_visible()); tx = b.inner_text()
            check('Dutch: translated', 'previous best' not in tx and 'Stronger than' not in tx and 'meer dan je vorige beste' in tx and 'Sterker dan je ooit was' in tx, tx)
        errs = session(pw, be, ALICE, s4, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
