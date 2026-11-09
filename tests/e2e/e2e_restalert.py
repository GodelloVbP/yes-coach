"""Rest alerts: the setting, the device, and the hand-over to the server when the app goes to the background during a rest."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

TODAY = datetime.date.today()
T = TODAY.isoformat()
KEY = 'BPvENfCtRnTXuxtA2fpYyWDexuyvvsQQy6HdjU6EM5rWA1DokN5Jyv_3TXdKmYhI_jaAG1fg60Zcbl__K-3yJ7U'

MOCK = """(() => {
  window.__sw = { texts: [], keyLen: 0 };
  window.Notification = { permission: window.__perm || 'default', requestPermission: async function () { window.Notification.permission = 'granted'; return 'granted'; } };
  let sub = null;
  const reg = { pushManager: {
    getSubscription: async () => sub,
    subscribe: async (o) => { window.__sw.keyLen = o.applicationServerKey.length; sub = { endpoint: 'https://push.example/device-1', toJSON: () => ({ endpoint: 'https://push.example/device-1', keys: { p256dh: 'PK', auth: 'AK' } }), unsubscribe: async () => { sub = null; return true; } }; return sub; } },
    active: { postMessage: (m) => window.__sw.texts.push(m) } };
  Object.defineProperty(navigator, 'serviceWorker', { value: { register: async () => reg, ready: Promise.resolve(reg), getRegistration: async () => reg }, configurable: true });
})();"""
HIDE = "Object.defineProperty(document, 'visibilityState', { get: () => 'hidden', configurable: true }); document.dispatchEvent(new Event('visibilitychange'));"
SHOW = "Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true }); document.dispatchEvent(new Event('visibilitychange'));"

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'settings': {}}})
    be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': TODAY.strftime('%a'), 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None}]}})

def with_key(page, key=KEY, mock=True, perm=None):
    page.route('**/config.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=__import__('re').sub(r"vapidPublicKey: '[^']*'", "vapidPublicKey: '%s'" % key, r.fetch().text())))
    if perm: page.add_init_script("window.__perm = '%s';" % perm)
    if mock: page.add_init_script(MOCK)

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. without the key (not set up) nothing shows
        be = Backend(); seed(be)
        def s1(page):
            with_key(page, key='', mock=False); page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible'); page.wait_for_timeout(300)
            check('not set up: no rest alert setting, no hint', page.locator('#push-row').is_hidden() and page.locator('#push-note').is_hidden())
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (not set up)', not errs, errs)

        # ---- 2. set up: switch it on and off
        be = Backend(); seed(be)
        def s2(page):
            with_key(page); page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
            page.locator('#v-settings section.fold').filter(has=page.locator('#push-row')).locator('.set-tog').click() if page.locator('#push-row').is_hidden() else None
            check('the setting is there and off', until(lambda: page.is_visible('#set-push')) and not page.is_checked('#set-push'))
            page.check('#set-push')
            check('switching it on saves this device', until(lambda: len(be.push_subs) == 1 and be.push_subs[0]['endpoint'] == 'https://push.example/device-1' and be.push_subs[0]['p256dh'] == 'PK'), be.push_subs)
            check('it stays on', page.is_checked('#set-push'))
            check('the public key was handed to the browser as 65 bytes', page.evaluate('window.__sw.keyLen') == 65)
            check('the words for the notification went to the service worker', until(lambda: page.evaluate('window.__sw.texts[0]') == {'type': 'text', 'title': 'Rest is over', 'body': 'Time for the next set.'}), page.evaluate('window.__sw.texts'))
            page.uncheck('#set-push')
            check('switching it off forgets the device', until(lambda: not be.push_subs), be.push_subs)
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (on and off)', not errs, errs)

        # ---- 3. a rest while the app goes away
        be = Backend(); seed(be)
        def s3(page):
            with_key(page); page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
            page.locator('#v-settings section.fold').filter(has=page.locator('#push-row')).locator('.set-tog').click() if page.locator('#push-row').is_hidden() else None
            page.wait_for_selector('#set-push', state='visible'); page.check('#set-push'); until(lambda: len(be.push_subs) == 1)
            page.click('#tab-train'); page.click('#btn-start'); page.wait_for_selector('#f-bench_1-load', state='visible')
            page.page_hide = None
            page.evaluate(HIDE); page.wait_for_timeout(300)
            check('no rest running: going away asks the server for nothing', not be.rest_calls, be.rest_calls)
            page.evaluate(SHOW)
            page.fill('#f-bench_1-load', '60'); page.fill('#f-bench_1-reps', '8'); page.locator('.set:has(#f-bench_1-load) .set-tick').click()
            check('the rest bar is running', until(lambda: page.is_visible('#restbar')))
            page.evaluate(HIDE)
            check('going away during a rest asks the server for an alert', until(lambda: any(c.get('action') == 'schedule' for c in be.rest_calls)), be.rest_calls)
            sched = [c for c in be.rest_calls if c.get('action') == 'schedule'][0]
            check('for the time that is left (about 90 s)', 80 <= sched['seconds'] <= 90, sched)
            page.evaluate(HIDE); page.wait_for_timeout(300)
            check('going away twice does not ask twice', len([c for c in be.rest_calls if c.get('action') == 'schedule']) == 1, be.rest_calls)
            page.evaluate(SHOW)
            check('coming back cancels it, by its id', until(lambda: any(c.get('action') == 'cancel' and c.get('id') == 'alert-1' for c in be.rest_calls)), be.rest_calls)
        errs = session(pw, be, ALICE, s3, width=390); check('no page errors (rest)', not errs, errs)

        # ---- 4. switched off: going away asks nothing
        be = Backend(); seed(be)
        def s4(page):
            with_key(page); page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.click('#btn-start'); page.wait_for_selector('#f-bench_1-load', state='visible')
            page.fill('#f-bench_1-load', '60'); page.fill('#f-bench_1-reps', '8'); page.locator('.set:has(#f-bench_1-load) .set-tick').click(); until(lambda: page.is_visible('#restbar'))
            page.evaluate(HIDE); page.wait_for_timeout(400)
            check('without the setting nothing is sent', not be.rest_calls, be.rest_calls)
        errs = session(pw, be, ALICE, s4, width=390); check('no page errors (off)', not errs, errs)

        # ---- 5. notifications blocked in the phone
        be = Backend(); seed(be)
        def s5(page):
            with_key(page, perm='denied'); page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
            page.locator('#v-settings section.fold').filter(has=page.locator('#push-row')).locator('.set-tog').click() if page.locator('#push-row').is_hidden() else None
            check('blocked: it says where to allow them', until(lambda: 'blocked' in page.text_content('#push-note')), page.text_content('#push-note'))
        errs = session(pw, be, ALICE, s5, width=390); check('no page errors (blocked)', not errs, errs)

        # ---- 6. an iPhone browser tab can not receive pushes: the hint says what to do
        be = Backend(); seed(be)
        IOS = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
        def s6(page):
            with_key(page, mock=False); page.add_init_script("delete window.PushManager; delete window.Notification;"); page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
            page.locator('#v-settings section.fold').filter(has=page.locator('#push-note')).locator('.set-tog').click() if page.locator('#push-note').is_hidden() else None
            check('iPhone browser: the hint says to add it to the home screen', until(lambda: 'home screen' in page.text_content('#push-note')) and page.locator('#push-row').is_hidden(), page.text_content('#push-note'))
        errs = session(pw, be, ALICE, s6, width=390, ua=IOS); check('no page errors (iPhone)', not errs, errs)

        # ---- 7. in German the notification words are German
        be = Backend(); seed(be)
        def s7(page):
            with_key(page); page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000)
            page.click('#tab-settings'); page.wait_for_selector('#v-settings .set-tog', state='visible')
            page.locator('#v-settings section.fold').filter(has=page.locator('#push-row')).locator('.set-tog').click() if page.locator('#push-row').is_hidden() else None
            page.wait_for_selector('#set-push', state='visible'); page.check('#set-push')
            check('German: the words are sent in German', until(lambda: page.evaluate('window.__sw.texts[0]') == {'type': 'text', 'title': 'Die Pause ist vorbei', 'body': 'Zeit f\u00fcr den n\u00e4chsten Satz.'}), page.evaluate('window.__sw.texts'))
            check('German: the setting reads German', 'Pause' in page.text_content('#push-row'), page.text_content('#push-row'))
        errs = session(pw, be, ALICE, s7, width=390, lang='de'); check('no page errors (German)', not errs, errs)

        # ---- 8. the real service worker registers under the strict content policy
        be = Backend(); seed(be)
        def s8(page):
            res = page.evaluate("""async () => { const r = await navigator.serviceWorker.register('sw.js'); const reg = await navigator.serviceWorker.ready; return { scope: r.scope.endsWith('/'), active: !!reg.active }; }""")
            check('sw.js registers and activates', res == {'scope': True, 'active': True}, res)
        errs = session(pw, be, ALICE, s8, width=390, csp=True); check('no policy violations or page errors (service worker)', not errs, errs)
finally:
    server.terminate()
done()
