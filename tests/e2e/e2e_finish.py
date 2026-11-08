"""The finish screen: numbers, records, the share picture, its switches, sharing and saving."""
import re
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

TODAY = datetime.date.today().isoformat()
BACK = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
def seed(be, prev=60):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/exercises/row', 'data': {'name': 'Row', 'group': 'Back', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    it = lambda ex, o: {'ex': ex, 'order': o, 'sets': 2, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': [it('bench', 1), it('row', 2)]}})
    be.docs.append({'path': 'yc/sessions/' + BACK, 'data': {'date': BACK, 'template': 'push', 'sets': {
        'bench_%d' % n: {'ex': 'bench', 'n': n, 'kind': 'work', 'reps': 8, 'load': prev, 'done': True, 'at': n} for n in (1, 2)}}})

def open_day(page):
    page.goto(BASE); page.wait_for_selector('text=Start Push day', timeout=8000)
    page.click('text=Start Push day')
    page.wait_for_selector('#f-bench_1-load', state='visible')
    page.wait_for_timeout(300)

def log(page, key, load, reps):
    page.fill('#f-%s-load' % key, str(load)); page.fill('#f-%s-reps' % key, str(reps))
    page.locator('.set:has(#f-%s-load) .set-tick' % key).click()

def finish(page):
    page.wait_for_timeout(900); page.locator('button.skew:visible', has_text=re.compile(r'^\s*Finish', re.I)).first.click()

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. numbers, records, the picture, saving
        be = Backend(); seed(be)
        def s1(page):
            open_day(page)
            log(page, 'bench_1', 65, 8); log(page, 'bench_2', 65, 8)
            page.locator('.fchip').nth(1).click(); page.wait_for_selector('#f-row_1-load', state='visible'); log(page, 'row_1', 50, 10)
            page.wait_for_timeout(500)
            finish(page)
            page.wait_for_selector('.fin', timeout=5000)
            check('the finish screen opens', page.is_visible('#fin-h') and 'Push day done' in page.text_content('#fin-h'), page.text_content('#fin-h'))
            tiles = page.locator('.fin-t').all_text_contents()
            check('working sets counted', any(t.startswith('3') and 'Working sets' in t for t in tiles), tiles)
            vol = 65 * 8 * 2 + 50 * 10
            check('volume added up', any(('%d kg' % vol).replace(',', ' ') in t.replace(' ', ' ') or str(vol) in t.replace(' ', '') for t in tiles), tiles)
            check('a PR is listed', page.locator('.fin-prs li').count() == 1 and 'Bench press' in page.locator('.fin-prs li').first.text_content(), page.locator('.fin-prs').text_content() if page.locator('.fin-prs').count() else 'none')
            check('the picture is drawn at 1080 x 1350', until(lambda: page.evaluate("(() => { const c = document.querySelector('#fin-canvas'); return !!c && c.width === 1080 && c.height === 1350; })()")))
            blank = page.evaluate("""(() => { const c = document.querySelector('#fin-canvas'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; const first = [d[0], d[1], d[2]]; for (let i = 0; i < d.length; i += 4 * 97) if (d[i] !== first[0] || d[i+1] !== first[1] || d[i+2] !== first[2]) n += 1; return n; })()""")
            check('the picture is not blank', blank > 200, blank)
            check('weights switch is on by default', page.is_checked('#fin-w'))
            check('no note switch without a note', page.locator('#fin-n').count() == 0)
            page.uncheck('#fin-w')
            check('the switch is remembered', page.evaluate("JSON.parse(localStorage.getItem('yc-share-w'))") is False)
            page.check('#fin-w')
            check('with no share support the button saves', 'Save picture' in page.text_content('#fin-share'), page.text_content('#fin-share'))
            with page.expect_download(timeout=5000) as dl:
                page.click('#fin-share')
            check('a PNG named for the day is downloaded', dl.value.suggested_filename == 'yes-coach-%s.png' % TODAY, dl.value.suggested_filename)
            page.click('#fin-done')
            check('Done closes the screen', until(lambda: page.locator('.fin').count() == 0))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (finish)', not errs, errs)

        # ---- 2. with sharing support and a note
        be = Backend(); seed(be)
        be.docs.append({'path': 'yc/sessions/' + TODAY, 'data': {'date': TODAY, 'template': 'push', 'note': 'Felt strong today', 'sets': {}}})
        def s2(page):
            page.add_init_script("""navigator.canShare = (d) => !!(d && d.files && d.files.length); navigator.share = async (d) => { window.__shared = { n: d.files[0].name, size: d.files[0].size, type: d.files[0].type }; };""")
            open_day(page)
            log(page, 'bench_1', 70, 8)
            page.wait_for_timeout(400)
            finish(page)
            page.wait_for_selector('.fin', timeout=5000)
            check('with support the button shares', 'Share picture' in page.text_content('#fin-share'), page.text_content('#fin-share'))
            check('the note switch shows up and is off', page.locator('#fin-n').count() == 1 and not page.is_checked('#fin-n'))
            check('the picture is ready', until(lambda: page.evaluate("!!document.querySelector('#fin-canvas')")))
            page.wait_for_timeout(500)
            page.click('#fin-share')
            check('the picture goes to the share sheet as a PNG file', until(lambda: page.evaluate("!!window.__shared")) and page.evaluate("window.__shared.type") == 'image/png' and page.evaluate("window.__shared.size") > 5000, page.evaluate("window.__shared"))
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (share)', not errs, errs)

        # ---- 3. no sets: no finish screen
        be = Backend(); seed(be)
        def s3(page):
            open_day(page)
            finish(page)
            page.wait_for_timeout(800)
            check('nothing logged: no finish screen', page.locator('.fin').count() == 0)
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (empty)', not errs, errs)

        # ---- 4. desktop
        be = Backend(); seed(be)
        def s4(page):
            open_day(page)
            log(page, 'bench_1', 65, 8)
            page.wait_for_timeout(400)
            finish(page)
            page.wait_for_selector('.fin', timeout=5000)
            check('desktop: the screen and the picture', until(lambda: page.evaluate("!!document.querySelector('#fin-canvas')")))
        errs = session(pw, be, ALICE, s4, width=1280); check('no page errors (desktop)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
