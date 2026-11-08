"""New personal records hit hard: the PR tag slams in when you tick the set, the finish screen slides the records in. Nothing moves with reduced motion."""
import re
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today().isoformat()
BACK = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for ex, nm, g in (('bench', 'Bench press', 'Chest'), ('row', 'Row', 'Back')):
        be.docs.append({'path': 'yc/exercises/' + ex, 'data': {'name': nm, 'group': g, 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    it = lambda ex, o: {'ex': ex, 'order': o, 'sets': 2, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [it('bench', 1), it('row', 2)]}})
    be.docs.append({'path': 'yc/sessions/' + BACK, 'data': {'date': BACK, 'template': 'push', 'sets': {
        '%s_%d' % (ex, n): {'ex': ex, 'n': n, 'kind': 'work', 'reps': 8, 'load': 60, 'done': True, 'at': n} for ex in ('bench', 'row') for n in (1, 2)}}})

def open_day(page, reduced=False):
    if reduced: page.emulate_media(reduced_motion='reduce')
    page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
    page.click('text=Start Push day')
    page.wait_for_selector('#f-bench_1-load', state='visible')
    if page.is_visible('#focus-toggle'): page.click('#focus-toggle')  # all exercises, so every field is on the page
    page.wait_for_timeout(300)

def log(page, key, load, reps):
    page.fill('#f-%s-load' % key, str(load)); page.fill('#f-%s-reps' % key, str(reps))
    page.locator('.set:has(#f-%s-load) .set-tick' % key).click()

def anim(page, sel): return page.evaluate("(s) => getComputedStyle(document.querySelector(s)).animationName", sel)
ROW = '.set:has(#f-bench_1-load)'

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def normal(page):
            open_day(page)
            log(page, 'bench_1', 50, 8)
            check('no record, no tag', page.locator(ROW + ' .pr').count() == 0)
            page.locator('.set:has(#f-bench_1-load) .set-tick').click()  # untick, then tick a record
            page.fill('#f-bench_1-load', '70'); page.locator('.set:has(#f-bench_1-load) .set-tick').click()
            check('a record shows the PR tag', until(lambda: page.locator(ROW + ' .pr').count() == 1))
            check('the tag slams in', until(lambda: 'slam' in (page.get_attribute(ROW + ' .pr', 'class') or '')))
            check('the slam animation is running', anim(page, ROW + ' .pr') == 'pr-slam', anim(page, ROW + ' .pr'))
            check('the row takes the hit', 'pr-hit' in (page.get_attribute(ROW, 'class') or '') and anim(page, ROW) == 'pr-hit', anim(page, ROW))
            log(page, 'bench_2', 71, 8); log(page, 'row_1', 65, 8)
            until(lambda: page.locator('.set:has(#f-row_1-load) .pr').count() == 1)
            # a reload shows the tag without the slam, once the sets are saved (the app asks before leaving with unsent sets)
            check('the sets are saved before the reload', settled(page))
            page.reload()
            until(lambda: page.is_visible('#resume-btn') or page.is_visible('#f-bench_1-load'), 10)
            if page.is_visible('#resume-btn'): page.click('#resume-btn')
            page.wait_for_selector('#f-bench_1-load', state='attached')
            check('after a reload the tag is there', until(lambda: page.locator(ROW + ' .pr').count() == 1))
            check('and it does not slam again', 'slam' not in (page.get_attribute(ROW + ' .pr', 'class') or ''))
            page.locator('button.skew:visible', has_text=re.compile(r'^\s*Finish', re.I)).first.click()
            page.wait_for_selector('.fin-prs li', state='attached')
            n = page.locator('.fin-prs li').count()
            check('the finish screen lists the records', n >= 2, n)
            check('records slide in', anim(page, '.fin-prs li') == 'pr-slide', anim(page, '.fin-prs li'))
            check('their tags slam', anim(page, '.fin-prs .pr') == 'pr-slam', anim(page, '.fin-prs .pr'))
            check('one after another', page.evaluate("[...document.querySelectorAll('.fin-prs li')].map((l) => parseFloat(getComputedStyle(l).animationDelay)).every((d, i, a) => i === 0 || d > a[i - 1])"))
            check('no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, normal, width=390); check('no page errors', not errs, errs)

        be = Backend(); seed(be)
        def calm(page):
            open_day(page, reduced=True)
            log(page, 'bench_1', 70, 8)
            check('reduced motion: the PR tag shows', until(lambda: page.locator(ROW + ' .pr').count() == 1))
            check('reduced motion: nothing animates on the row', anim(page, ROW + ' .pr') == 'none' and anim(page, ROW) == 'none', (anim(page, ROW + ' .pr'), anim(page, ROW)))
            page.locator('button.skew:visible', has_text=re.compile(r'^\s*Finish', re.I)).first.click()
            page.wait_for_selector('.fin-prs li', state='attached')
            check('reduced motion: the finish records are plain', anim(page, '.fin-prs li') == 'none' and anim(page, '.fin-prs .pr') == 'none')
        errs = session(pw, be, ALICE, calm, width=390); check('no page errors (reduced motion)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
