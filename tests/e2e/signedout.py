"""The signed-out pages (sign-in, Home, consent) in a phone-sized Chrome with Supabase and Turnstile stood in for. Shared by e2e_captcha.py and e2e_landing.py."""
import json, sys, base64, re
from playwright.sync_api import sync_playwright
from harness import REPO as ROOT, serve, launch
srv = serve(8777)
BASE = 'http://127.0.0.1:8777/'
SB = 'https://qazvzhhoalkyyasakphs.supabase.co'
KEY = '0x4AAAAAAF0wHRoRqdBkO_As'
n = 0
def ok(c, m):
    global n; n += 1
    if not c: print('FAIL', m); sys.exit(1)
def passed(): return n
b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()
JWT = b64({'alg': 'HS256', 'typ': 'JWT'}) + '.' + b64({'sub': 'u1', 'exp': 4102444800, 'aud': 'authenticated', 'role': 'authenticated', 'email': 'a@b.nl'}) + '.sig'
USER = {'id': 'u1', 'aud': 'authenticated', 'email': 'a@b.nl', 'app_metadata': {}, 'user_metadata': {}, 'created_at': '2026-01-01T00:00:00Z'}
STUB = """window.__n = 0; window.__ts = [];
window.turnstile = { render(box, o) { window.__ts.push({ box: box.id, key: o.sitekey, appearance: o.appearance }); window.__o = o; setTimeout(() => o.callback('TOKEN-' + (++window.__n)), 30); return 7; },
  reset() { setTimeout(() => window.__o.callback('TOKEN-' + (++window.__n)), 30); } };"""
def make(pw, reject_captcha=False, block_cf=False, no_key=False, signed_in=False, users=7):
    br = launch(pw)
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
