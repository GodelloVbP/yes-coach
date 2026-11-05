"""Cloudflare Turnstile on the sign-in, sign-up, reset and consent forms, and the length rule for passwords."""
import sys
from playwright.sync_api import sync_playwright
from signedout import *

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
    signin(pg, 'up'); until(pg, "document.querySelector('#au-msg').textContent.includes('Check your email')")
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
    # 3b the 8-character minimum is for choosing a password: an older, shorter one must still sign in
    br, pg, log = make(pw); pg.goto(BASE); signin(pg, pw='short1'); until(pg, 'document.body.classList.contains("signed-out") === false')
    ok([x for x in log['auth'] if x[0] == '/auth/v1/token'], 'a 6-character password is sent to Supabase on sign-in')
    br.close()
    br, pg, log = make(pw); pg.goto(BASE); signin(pg, mode='up', pw='short1')
    until(pg, "document.querySelector('#au-msg').textContent.includes('at least 8')")
    ok(not [x for x in log['auth'] if x[0] == '/auth/v1/signup'], 'sign-up with 6 characters is stopped before Supabase')
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
print(passed(), 'captcha checks passed'); srv.shutdown()
