import json, threading, http.server, functools, sys, base64, re
from playwright.sync_api import sync_playwright
ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[2])
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT); H.log_message = lambda *a, **k: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8777), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = 'http://127.0.0.1:8777/'
SB = 'https://qazvzhhoalkyyasakphs.supabase.co'
KEY = '0x4AAAAAAF0wHRoRqdBkO_As'
n = 0
def ok(c, m):
    global n; n += 1
    if not c: print('FAIL', m); sys.exit(1)
b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()
JWT = b64({'alg': 'HS256', 'typ': 'JWT'}) + '.' + b64({'sub': 'u1', 'exp': 4102444800, 'aud': 'authenticated', 'role': 'authenticated', 'email': 'a@b.nl'}) + '.sig'
USER = {'id': 'u1', 'aud': 'authenticated', 'email': 'a@b.nl', 'app_metadata': {}, 'user_metadata': {}, 'created_at': '2026-01-01T00:00:00Z'}
STUB = """window.__n = 0; window.__ts = [];
window.turnstile = { render(box, o) { window.__ts.push({ box: box.id, key: o.sitekey, appearance: o.appearance }); window.__o = o; setTimeout(() => o.callback('TOKEN-' + (++window.__n)), 30); return 7; },
  reset() { setTimeout(() => window.__o.callback('TOKEN-' + (++window.__n)), 30); } };"""
def make(pw, reject_captcha=False, block_cf=False, no_key=False, signed_in=False, users=7):
    br = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = br.new_context(device_scale_factor=2, viewport={'width': 390, 'height': 800})  # CSP on: the policy itself is part of the test
    ctx.add_init_script("if (!sessionStorage.getItem('li')) { localStorage.setItem('yc-lang','en'); sessionStorage.setItem('li','1'); }")
    if signed_in:
        sess = {'access_token': JWT, 'token_type': 'bearer', 'expires_in': 3600, 'expires_at': 4102444800, 'refresh_token': 'r', 'user': USER}
        ctx.add_init_script("localStorage.setItem('sb-qazvzhhoalkyyasakphs-auth-token', %s)" % json.dumps(json.dumps(sess)))
    log = {'auth': [], 'cf': [], 'other': [], 'errors': []}
    hd = {'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}
    def supa(route):
        r = route.request; u = r.url.replace(SB, '')
        j = lambda o, c=200: route.fulfill(status=c, content_type='application/json', body=json.dumps(o), headers=hd)
        if r.method == 'OPTIONS': return route.fulfill(status=204, headers=hd)
        body = json.loads(r.post_data or '{}') if r.post_data else {}
        tok = (body.get('gotrue_meta_security') or {}).get('captcha_token')
        if u.startswith('/auth/v1/'):
            log['auth'].append((u.split('?')[0], tok))
            if reject_captcha or (u.startswith(('/auth/v1/token', '/auth/v1/signup', '/auth/v1/recover')) and not tok and not no_key):
                return j({'code': 400, 'error_code': 'captcha_failed', 'msg': 'captcha verification process failed'}, 400)
            if '/token' in u: return j({'access_token': JWT, 'token_type': 'bearer', 'expires_in': 3600, 'refresh_token': 'r', 'user': USER})
            if '/signup' in u: return j({'id': 'u2', 'email': body.get('email'), 'aud': 'authenticated', 'created_at': '2026-01-01T00:00:00Z'})
            if '/user' in u: return j(USER)
            return j({})
        if u.startswith('/rest/v1/rpc/user_count'): return j(users)
        return j([])
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://127.0.0.1') else (log['other'].append(r.request.url), r.abort()))
    ctx.route(SB + '/**', supa)
    def cf(route):
        log['cf'].append(route.request.url)
        route.abort() if block_cf else route.fulfill(status=200, content_type='application/javascript', body=STUB)
    ctx.route('https://challenges.cloudflare.com/**', cf)
    if no_key:
        ctx.route(BASE + 'config.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=re.sub(r"\s*turnstileKey:[^\n]*\n", "\n", open(ROOT + '/config.js').read())))
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: log['errors'].append(str(e)))
    pg.on('console', lambda m: log['errors'].append('CSP: ' + m.text) if 'Content Security Policy' in m.text else None)
    return br, pg, log

def until(pg, expr, timeout=8000):
    for _ in range(timeout // 100):
        if pg.evaluate(expr): return
        pg.wait_for_timeout(100)
    raise AssertionError('timeout: ' + expr)

def signin(pg, mode='in', em='a@b.nl', pw='longenough1'):
    pg.wait_for_selector('#hm-login', state='visible')
    pg.click('#hm-signup' if mode == 'up' else '#hm-login')
    pg.wait_for_selector('#au-email', state='visible')
    if mode == 'reset': pg.click('#au-forgot')
    if mode != 'reset' or True: pg.fill('#au-email', em)
    if mode != 'reset': pg.fill('#au-pass', pw)
    pg.click('#au-go')

with sync_playwright() as pw:
    # 1 sign in: widget drawn with the site key, token goes to Supabase
    br, pg, log = make(pw); pg.goto(BASE)
    pg.wait_for_selector('#hm-login', state='visible')
    ok(pg.is_visible('#hm-login') and pg.is_hidden('#hm-train') and pg.is_hidden('#hm-ticket') and pg.is_hidden('#hm-claude'), 'signed out: Home with a sign-in button, no train/ticket/Claude buttons')
    ok(pg.is_visible('#v-home') and pg.is_hidden('#tabs-nav') and pg.is_hidden('#appbar'), 'signed out: opens on the landing page with no navigation bar')
    ok(pg.is_hidden('#au-email') and pg.is_hidden('#stick'), 'signed out: sign-in form and tab bar are not showing')
    pg.wait_for_timeout(1000)
    ok(pg.is_hidden('#hm-users'), 'signed out: 7 users is below the threshold, so no counter is shown')
    ok(len(log['cf']) == 0, 'Cloudflare not contacted until the form opens')
    ok(pg.is_visible('#hm-chip') and 'English' in pg.inner_text('#hm-chip') and pg.locator('#hm-chip svg.flag').count() == 1, 'header: a language chip with flag and name')
    ok(pg.is_hidden('#hm-lang-wrap') and pg.get_attribute('#hm-chip', 'aria-expanded') == 'false', 'header: the picker is closed')
    pg.click('#hm-chip')
    ok(pg.is_visible('#hm-lang') and pg.get_attribute('#hm-chip', 'aria-expanded') == 'true', 'header: the chip opens the picker')
    pg.keyboard.press('Escape')
    ok(pg.is_hidden('#hm-lang-wrap'), 'header: Escape closes the picker')
    names = pg.eval_on_selector_all('#hm-lang button', 'els => els.map(e => e.textContent.trim())')
    ok(names == ['Nederlands', 'English', 'Español', 'Deutsch', 'Français', 'Italiano'], 'Home language picker: native names in order: %s' % names)
    ok(pg.locator('#hm-lang button svg.flag').count() == 6, 'Home language picker: a flag on every button')
    ok(pg.eval_on_selector_all('#hm-lang [aria-checked=true]', 'els => els.map(e => e.textContent.trim())') == ['English'], 'Home language picker: current language marked')
    pg.click('#hm-login'); pg.wait_for_selector('#au-email', state='visible'); until(pg, 'window.__ts && window.__ts.length')
    ok(pg.is_hidden('#hm-login'), 'form open: Home is hidden')
    pg.click('#au-back'); pg.wait_for_selector('#hm-login', state='visible')
    ok(pg.is_hidden('#au-email'), 'back returns to Home')
    ok(pg.evaluate('window.__ts[0].key') == KEY and pg.evaluate('window.__ts[0].box') == 'au-cap', 'widget drawn into #au-cap with the site key')
    ok(pg.evaluate('window.__ts[0].appearance') == 'interaction-only', 'widget only shows when a challenge is needed')
    ok(len([u for u in log['cf'] if 'turnstile/v0/api.js' in u]) == 1, 'script loaded once from Cloudflare')
    signin(pg); until(pg, 'document.body.classList.contains("signed-out") === false')
    t = [x for x in log['auth'] if x[0] == '/auth/v1/token']
    ok(t and t[0][1] == 'TOKEN-1', 'sign-in sends the token: %s' % t)
    ok(not log['errors'], 'no page or CSP errors on sign-in: %s' % log['errors'])
    ok(not log['other'], 'nothing else left the site: %s' % log['other'])
    br.close()
    # the show-password toggle does not carry over to the next form
    br, pg, log = make(pw); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible')
    pg.click('#hm-login'); pg.wait_for_selector('#au-show', state='visible'); pg.click('#au-show')
    ok(pg.get_attribute('#au-pass', 'type') == 'text' and pg.get_attribute('#au-show', 'aria-pressed') == 'true' and 'Hide' in pg.inner_text('#au-show'), 'Show password shows it')
    pg.click('#au-alt')
    ok(pg.get_attribute('#au-pass', 'type') == 'password' and pg.get_attribute('#au-show', 'aria-pressed') == 'false' and 'Show' in pg.inner_text('#au-show'), 'switching to the other form hides the password again and resets the button')
    br.close()
    br, pg, log = make(pw); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible')
    pg.click('#hm-chip'); pg.click('#hm-lang button[lang=de]'); pg.wait_for_load_state('load'); pg.wait_for_selector('#hm-login', state='visible')
    ok(pg.evaluate("localStorage.getItem('yc-lang')") == 'de' and pg.evaluate('document.documentElement.lang') == 'de', 'Home picker switches the language')
    ok('ANMELDEN' in pg.inner_text('#hm-login').upper(), 'Home is in German after the switch: ' + pg.inner_text('#hm-login'))
    ok('Deutsch' in pg.inner_text('#hm-chip'), 'the chip shows the new language')
    br.close()
    br, pg, log = make(pw, users=150); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible')
    until(pg, "document.querySelector('#hm-users').hidden === false")
    ok('150' in pg.inner_text('#hm-users'), 'signed out: the counter shows from the threshold up: ' + pg.inner_text('#hm-users'))
    br.close()
    # 2 sign up and reset send tokens, and a spent token is replaced
    br, pg, log = make(pw); pg.goto(BASE)
    signin(pg, 'up'); until(pg, "document.querySelector('#au-msg').textContent.includes('We sent a confirmation link')")
    ok(pg.is_visible('#au-resend'), 'sign-up: Send the email again is offered')
    s = [x for x in log['auth'] if x[0] == '/auth/v1/signup']
    ok(s and s[0][1] == 'TOKEN-1', 'sign-up sends the token: %s' % s)
    pg.click('#au-forgot'); until(pg, 'window.__n >= 2')
    pg.fill('#au-email', 'a@b.nl'); pg.click('#au-go'); until(pg, "document.querySelector('#au-msg').textContent.includes('reset link')")
    r = [x for x in log['auth'] if x[0] == '/auth/v1/recover']
    ok(r and r[0][1] == 'TOKEN-2', 'reset sends a fresh token, the first was spent: %s' % r)
    ok(not log['errors'], 'no errors: %s' % log['errors'])
    br.close()
    # 3 Supabase refuses the token
    br, pg, log = make(pw, reject_captcha=True); pg.goto(BASE); signin(pg)
    until(pg, "document.querySelector('#au-msg').textContent.includes('human check failed')")
    ok(not pg.is_disabled('#au-go'), 'button usable again after a refused token')
    br.close()
    # 4 Cloudflare blocked (content blocker)
    br, pg, log = make(pw, block_cf=True); pg.goto(BASE); signin(pg)
    until(pg, "document.querySelector('#au-msg').textContent.includes('could not run')")
    ok(not [x for x in log['auth'] if x[0] == '/auth/v1/token'], 'no request to Supabase without a token')
    br.close()
    # 5 signed in: Cloudflare is never contacted
    br, pg, log = make(pw, signed_in=True); pg.goto(BASE + '#home'); pg.wait_for_selector('#v-home', state='visible'); pg.wait_for_timeout(600)
    ok(not log['cf'], 'signed in: no contact with Cloudflare: %s' % log['cf'])
    br.close()
    # 6 no site key: no widget, no Cloudflare, sign-in still works
    br, pg, log = make(pw, no_key=True); pg.goto(BASE); signin(pg); until(pg, 'document.body.classList.contains("signed-out") === false')
    ok(not log['cf'], 'no key: Cloudflare not contacted')
    ok([x for x in log['auth'] if x[0] == '/auth/v1/token'][0][1] is None, 'no key: no token sent')
    br.close()
    # 7 consent page
    br, pg, log = make(pw); pg.goto(BASE + 'consent.html?authorization_id=AID')
    pg.wait_for_selector('#login:not([hidden])'); until(pg, 'window.__ts && window.__ts.length')
    ok(pg.evaluate('window.__ts[0].box') == 'cap', 'consent: widget drawn')
    pg.fill('#em', 'a@b.nl'); pg.fill('#pw', 'longenough1'); pg.click('#login-go'); pg.wait_for_timeout(800)
    t = [x for x in log['auth'] if x[0] == '/auth/v1/token']
    ok(t and t[0][1] == 'TOKEN-1', 'consent: sign-in sends the token: %s' % t)
    ok(not log['errors'], 'consent: no CSP errors: %s' % log['errors'])
    br.close()
    # 8 the other pages never allow Cloudflare
    for page in ('connect.html', 'privacy.html'):
        csp = re.search(r'Content-Security-Policy" content="([^"]+)"', open(ROOT + '/' + page).read()).group(1)
        ok('cloudflare' not in csp, page + ' policy has no Cloudflare')
print(n, 'captcha checks passed'); srv.shutdown()
