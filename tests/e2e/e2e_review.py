"""The review after a finished day: the text sent to Claude (connector) or copied for any AI, Copy day and the full export.
They share one brief: a critical stance, the five judgements (sets, notes, the plan of the day, the whole week, missing muscle groups), a self-check."""
import time, datetime, urllib.parse
from playwright.sync_api import sync_playwright
from harness import *

passed = failed = 0
def check(name, cond, extra=''):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print('FAIL', name, extra)

TODAY = datetime.date.today().isoformat()
def ago(n): return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
FROM = ago(27)

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'profile': {'goal': 'muscle', 'days_per_week': 4, 'session_length': 'medium', 'where': 'gym'},
        'schedule': {'enabled': True, 'mode': 'rotation', 'days': [WD[(datetime.date.today().weekday() + k) % 7] for k in (0, 2, 3)], 'rotation': ['push', 'pull']}}})
    ex = {'bench': ('Bench press', 'Chest', 'kg'), 'ohp': ('Overhead press', 'Shoulders', 'kg'), 'pushdown': ('Triceps pushdown', 'Arms', 'stack'), 'row': ('Barbell row', 'Back', 'kg'), 'curl': ('Biceps curl', 'Arms', 'kg')}
    for k, (n, g, u) in ex.items():
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': n, 'group': g, 'category': 'strength', 'unit': u, 'better': 'higher'}})
    it = lambda e, o, s, r: {'ex': e, 'order': o, 'sets': s, 'reps': r, 'target': '', 'target_at': ago(30), 'rest_s': 90, 'note': None}
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest and shoulders', 'weekday': WD[datetime.date.today().weekday()], 'items': [it('bench', 1, 3, '8'), it('ohp', 2, 3, '8'), it('pushdown', 3, 3, '12')]}})
    be.docs.append({'path': 'yc/templates/pull', 'data': {'name': 'Pull day', 'order': 2, 'kind': 'Pull', 'focus': 'Back and biceps', 'items': [it('row', 1, 3, '8'), it('curl', 2, 3, '12')]}})
    def sess(date, tpl, plan):
        sets = {}
        for ex_, load, reps in plan:
            for i, r in enumerate(reps): sets['%s_%d' % (ex_, i + 1)] = {'ex': ex_, 'n': i + 1, 'kind': 'work', 'reps': r, 'load': load, 'done': True, 'at': 1}
        be.docs.append({'path': 'yc/sessions/' + date, 'data': {'date': date, 'template': tpl, 'split': 'Chest' if tpl == 'push' else 'Back', 'label': tpl, 'sets': sets}})
    for d, b in ((4, 80), (11, 77.5)): sess(ago(d), 'push', [('bench', b, [8, 8, 7]), ('ohp', 40, [8, 7, 6]), ('pushdown', 35, [12, 12, 12])])
    for d in (2, 9): sess(ago(d), 'pull', [('row', 70, [8, 8, 8]), ('curl', 14, [12, 12, 10])])
    be.docs.append({'path': 'yc/notes/n1', 'data': {'text': 'Right shoulder pinches on the way down', 'about': 'bench', 'about_label': 'Bench press', 'date': ago(4), 'status': 'new'}})

CONNECTED = [{'client': {'id': 'c-claude', 'name': 'Claude', 'uri': 'https://claude.ai'}, 'scopes': ['openid'], 'granted_at': now()}]
GOT = {}

def start_day(page):
    page.evaluate("window.__opened = []; window.open = (u) => { window.__opened.push(u); return null; }; 0")
    page.wait_for_selector('text=Start Push day', timeout=8000); page.click('text=Start Push day')
    page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(300)
def log_bench(page):
    for key, load, reps in (('bench_1', 82.5, 8), ('bench_2', 82.5, 8), ('bench_3', 82.5, 5)):
        page.fill('#f-%s-load' % key, str(load)); page.fill('#f-%s-reps' % key, str(reps)); page.locator('.set:has(#f-%s-load) .set-tick' % key).click()
def finish(page): page.locator('button.skew:visible', has_text='Finish day').first.click()
def clip(page): return page.evaluate('navigator.clipboard.readText()')

# the brief every route carries
BRIEF = ['critical review, not encouragement', 'Every statement needs a number', 'did every set reach the planned reps', 'Planned exercises that were not done', 'My notes outrank progression',
         'Judge the plan of each day', 'Judge the whole week every time', 'missing or neglected', 'rear delts, calves, hamstrings', 'Review yourself once', 'Self-check: ']

server = serve()
try:
    with sync_playwright() as pw:
        # ---- 1. connected: finish, then the review goes to Claude
        be = Backend(); seed(be); be.grants = CONNECTED
        def s1(page):
            start_day(page); log_bench(page)
            page.click('text=Copy day'); page.wait_for_timeout(300); GOT['copyday'] = clip(page)
            finish(page); page.wait_for_selector('#fin-done'); page.wait_for_timeout(400)
            check('connected: no copy button on the finish screen, the dialog comes instead', page.locator('#fin-ai').count() == 0)
            page.click('#fin-done'); page.wait_for_selector('#claude-review-go')
            GOT['dialog'] = page.inner_text('.ydlg')
            page.click('#claude-review-go'); page.wait_for_timeout(500)
            GOT['url'] = page.evaluate('window.__opened[0]'); GOT['clip'] = clip(page)
        errs = session(pw, be, ALICE, s1, width=1000); check('no page errors (connected)', not errs, errs)
        d = GOT['dialog'].lower()
        check('the dialog says what Claude judges and that nothing changes unasked', 'critical review' in d and 'your whole week' in d and 'muscle groups you miss' in d and 'changes nothing until you say so' in d, GOT['dialog'])
        url = GOT['url'] or ''
        q = urllib.parse.unquote(url.split('?q=', 1)[1]) if '?q=' in url else ''
        check('the chat opens with the review request in the address', url.startswith('https://claude.ai/new?q=') and len(url) <= 12000, len(url))
        check('the address carries the same text as the clipboard', q == GOT['clip'], (len(q), len(GOT['clip'])))
        t = GOT['clip']
        for phrase in BRIEF: check('connector text has: ' + phrase, phrase in t)
        check('it says where to read: tools, the exact from date and the exercise ids', all(x in t for x in ('get_overview', 'get_exercise_history', 'get_plan', 'get_notes', 'with from ' + FROM, 'exercise_id bench')), t[:900])
        check('it says nothing changes before agreement, and that notes may be answered', 'Change nothing yet' in t and 'answer_note' in t and 'save_training_day' in t)
        check('it carries what the app saw today with last time, and the skipped exercises', 'Did 8 @ 82.5 kg' in t and 'Last time' in t and 'Overhead press (exercise_id ohp): plan 3 × 8. Not done' in t, t)
        check('it carries the lifter\'s note about the shoulder', 'Right shoulder pinches on the way down' in t)
        check('it carries the app\'s count per body part, with the group that is missing', 'counted by the app' in t and 'Legs: none logged' in t and 'Core: none logged' in t)
        import re
        check('the count is per week with plural days', re.search(r'Chest: [\d.]+ sets a week, [\d.]+ days? a week', t) is not None, t[-900:])
        check('the profile is there', 'goal: gain muscle' in t and 'trains in a gym' in t)
        check('units: plan changes use the exercise\'s own unit', 'own unit (kg, pin or kg assist)' in t)
        # Copy day: the same brief, with the data in the text
        c = GOT['copyday']
        for phrase in BRIEF: check('Copy day has: ' + phrase, phrase in c)
        check('Copy day has the data and no tool instructions', 'Right shoulder pinches' in c and 'Training days (the whole plan)' in c and 'Legs: none logged' in c and 'get_overview' not in c and 'I will make the changes myself' in c)

        # ---- 2. not connected: the same review through the clipboard
        be = Backend(); seed(be); be.grants = []
        def s2(page):
            start_day(page); log_bench(page); finish(page)
            page.wait_for_selector('#fin-ai'); page.click('#fin-ai'); page.wait_for_timeout(400)
            GOT['paste'] = clip(page); GOT['status'] = page.inner_text('.fin-status')
            page.click('#fin-done'); page.wait_for_timeout(400)
            check('not connected: no Claude dialog after Done', page.locator('#claude-review-go').count() == 0)
        errs = session(pw, be, ALICE, s2, width=1000); check('no page errors (paste)', not errs, errs)
        check('the finish screen says it copied the review', 'Review request copied' in GOT['status'], GOT['status'])
        for phrase in BRIEF: check('pasted text has: ' + phrase, phrase in GOT['paste'])

        # ---- 3. a day with nothing logged has nothing to review
        be = Backend(); seed(be); be.grants = CONNECTED
        def s3(page):
            start_day(page); finish(page); page.wait_for_timeout(900)
            check('nothing logged: no finish screen and no review dialog', page.locator('.fin').count() == 0 and page.locator('#claude-review-go').count() == 0)
        errs = session(pw, be, ALICE, s3, width=1000); check('no page errors (empty day)', not errs, errs)

        # ---- 4. the full export carries the same brief
        be = Backend(); seed(be); be.grants = []
        def s4(page):
            page.wait_for_selector('text=Start Push day', timeout=8000)
            page.click('[data-view=settings]'); page.wait_for_selector('#ex-out', state='attached'); page.wait_for_timeout(500)
            GOT['export'] = page.evaluate("document.querySelector('#ex-out').value")
        errs = session(pw, be, ALICE, s4, width=1000); check('no page errors (export)', not errs, errs)
        e = GOT['export']
        for phrase in ('critical review, not encouragement', 'My notes outrank progression', 'Judge the plan of every training day', 'Judge the whole week every time', 'Review yourself once', 'Self-check: ', 'counted by the app', 'Right shoulder pinches'):
            check('export has: ' + phrase, phrase in e)
        check('export no longer calls the lifter "himself"', 'himself' not in e)
finally:
    server.shutdown()
print('passed %d, failed %d' % (passed, failed))
raise SystemExit(1 if failed else 0)
