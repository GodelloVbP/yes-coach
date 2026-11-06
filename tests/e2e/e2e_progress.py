"""Progress: the summary tiles, the PR badge on a lift whose latest session beat the rest, and the estimated one-rep max."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

D = lambda n: (datetime.date.today() - datetime.timedelta(days=n)).isoformat()

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for ex, nm, g, u in (('bench', 'Bench press', 'Chest', 'kg'), ('ohp', 'Overhead press', 'Shoulders', 'kg'), ('dip', 'Pull-up', 'Back', 'bw')):
        be.docs.append({'path': 'yc/exercises/' + ex, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': u, 'better': 'higher'}})
    plan = [(1, 'bench', [(82.5, 5), (80, 6)]), (1, 'ohp', [(40, 8)]), (4, 'bench', [(80, 6), (77.5, 6)]), (4, 'dip', [(None, 10), (None, 9)]),
            (8, 'bench', [(77.5, 6)]), (8, 'ohp', [(45, 8)]), (12, 'bench', [(75, 8)])]
    byd = {}
    for d, ex, sets in plan:
        s = byd.setdefault(D(d), {})
        for i, (l, r) in enumerate(sets): s['%s_%d' % (ex, i + 1)] = {'ex': ex, 'n': i + 1, 'kind': 'work', 'reps': r, 'load': l, 'done': True, 'at': i + 1}
    for d, sets in byd.items(): be.docs.append({'path': 'yc/sessions/' + d, 'data': {'date': d, 'template': None, 'sets': sets, 'split': 'Push'}})

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        for width in (390, 1280):
            be = Backend(); seed(be)
            def s1(page):
                page.goto(BASE); page.wait_for_selector('#tab-progress'); page.click('#tab-progress')
                page.wait_for_selector('#plist .prow', timeout=8000)
                tiles = [t.replace('\n', ' ') for t in page.locator('.p-tile').all_text_contents()]
                check('%d: three tiles' % width, len(tiles) == 3, tiles)
                check('%d: 4 sessions, 10 working sets, 3 lifts' % width, tiles[0].startswith('4') and tiles[1].startswith('10') and tiles[2].startswith('3'), tiles)
                rows = {r.locator('.p-name').text_content().replace('PR', '').strip().upper(): r for r in page.locator('#plist .prow').all()}
                bench, ohp, pull = rows.get('BENCH PRESS'), rows.get('OVERHEAD PRESS'), rows.get('PULL-UP')
                check('%d: all three lifts are listed' % width, bench is not None and ohp is not None and pull is not None, list(rows))
                check('%d: bench: the latest session is its best estimate, so PR' % width, bench.locator('.p-pr').count() == 1)
                check('%d: overhead press went down, no PR' % width, ohp.locator('.p-pr').count() == 0)
                check('%d: a single session is no record' % width, pull.locator('.p-pr').count() == 0)
                check('%d: e1RM on a kg lift' % width, 'e1RM 96.3 kg' in bench.text_content(), bench.text_content())
                check('%d: no e1RM on a bodyweight lift' % width, 'e1RM' not in pull.text_content())
            errs = session(pw, be, ALICE, s1, width=width); check('no page errors (%d)' % width, not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
