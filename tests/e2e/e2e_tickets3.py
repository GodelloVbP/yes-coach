"""End-to-end check, part of the old tickets file: Plan day in the week, Home invitation, finishing asks about Claude, Progress axis, security policy, languages. The real built app in headless Chrome, Supabase faked in memory."""
import subprocess, time, datetime, json
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

def card_of(page, title, root='#tk-admin-list'):
    return page.locator(root + ' .tk-card').filter(has=page.locator('.tk-title', has_text=title))

def go(page, tab):
    if tab in ('feedback', 'exercises'):
        page.click('#tab-settings'); page.click('#more-' + tab)
    else: page.click('#tab-' + tab)

def open_feedback(page):
    page.wait_for_selector('#tab-feedback:not([hidden])', state='attached')
    page.click('#tab-settings'); page.click('#more-feedback')
    page.wait_for_selector('#v-feedback #tk', state='visible')

def logo(page):
    page.locator('#mark:visible, #mark2:visible').first.click()

def send_form(page, title, text, name=None, kind=None):
    page.click('#tk .tk-type[data-type=%s]' % (kind or 'bug'))
    if name is not None: page.fill('#tk form input[autocomplete=given-name]', name)
    page.fill('#tk form input[autocomplete=off]', title)
    page.fill('#tk form textarea', text)
    page.click('#tk form button[type=submit]')

server = serve()
try:
    with sync_playwright() as pw:
        # ---- 13. Plan: put a day in the week from the day itself; delete in plain sight; styled dropdowns
        def docdata(be, path): return next((d['data'] for d in be.docs if d['path'] == path), None)
        def plan_be(mode):
            be = Backend(); be.grants = []
            sched = {'enabled': True, 'mode': 'fixed', 'week': {'Mon': 'push', 'Wed': 'legs'}} if mode == 'fixed' else {'enabled': True, 'mode': 'rotation', 'days': ['Mon', 'Wed'], 'rotation': ['push', 'legs']}
            be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach', 'schedule': sched}})
            be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'unit': 'kg', 'category': 'strength'}})
            for i, (k, n) in enumerate((('push', 'Push'), ('legs', 'Legs'), ('pull', 'Pull'))):
                be.docs.append({'path': 'yc/templates/' + k, 'data': {'name': n, 'order': i + 1, 'kind': n, 'focus': '', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '8', 'target': ''}]}})
            return be
        be = plan_be('fixed')
        def plan_fixed(page):
            go(page, 'plan'); page.wait_for_selector('.pw-srow')
            check('no native dropdown is visible any more', page.evaluate("[...document.querySelectorAll('select')].every(s => s.classList.contains('ysel-native') && getComputedStyle(s).opacity === '0')"))
            check('styled dropdown button replaces the select', page.locator('.pw-srow .ysel-btn').count() == 1)
            gap = page.evaluate("(() => { const a = document.querySelector('.pw-spare').getBoundingClientRect(); const b = document.querySelector('.pw-more > .foot-row').getBoundingClientRect(); return b.top - a.bottom; })()")
            check('room between Not in your week and New training day', gap >= 16, gap)
            page.click('.pw-srow .ysel-btn'); page.wait_for_selector('.ysel-pop')
            opts = page.eval_on_selector_all('.ysel-pop [role=option]', 'e => e.map(x => x.textContent)')
            check('dropdown lists Put on and the weekdays', opts[0] == 'Put on…' and 'Fri' in opts and any(o.startswith('Mon (instead of Push') for o in opts), opts)
            page.keyboard.press('Escape'); check('Escape closes it', page.locator('.ysel-pop').count() == 0)
            page.click('.pw-srow .ysel-btn'); page.click('.ysel-pop >> text=Fri')
            page.wait_for_function("document.querySelector('.pw-board').textContent.includes('Pull')")
            check('picking from the list sets Fri', docdata(be, 'yc')['schedule']['week'].get('Fri') == 'pull', docdata(be, 'yc'))
            # open Pull and move it with the weekday chips
            page.click('.pw-board >> text=Pull >> xpath=ancestor::div[contains(@class,"pw-card") or contains(@class,"pw-day")][1] >> text=Edit') if False else None
        errs = session(pw, be, ALICE, plan_fixed, width=1000); check('no page errors (plan dropdown)', not errs, errs)

        be = plan_be('fixed')
        def plan_week(page):
            go(page, 'plan'); page.wait_for_selector('.pw-srow')
            page.click('.pw-srow >> text=Edit'); page.wait_for_selector('.pw-inweek')
            check('editor shows In your week with weekday chips', page.locator('.pw-inweek .pk-chip').count() == 7 and 'Not in your week yet' in page.inner_text('.pw-inweek'))
            page.click('.pw-inweek .pk-chip >> text=Fri')
            check('Fri chip is on and saved', page.get_attribute('.pw-inweek .pk-chip:has-text("Fri")', 'aria-pressed') == 'true' and docdata(be, 'yc')['schedule']['week'].get('Fri') == 'pull')
            page.click('.pw-inweek .pk-chip >> text=Mon')
            check('taking a taken day replaces it and says so', docdata(be, 'yc')['schedule']['week']['Mon'] == 'pull' and 'Push is no longer on Mon' in page.inner_text('#toast'), page.inner_text('#toast'))
            page.click('#toast-undo'); page.wait_for_timeout(200)
            check('undo puts Push back on Monday', docdata(be, 'yc')['schedule']['week']['Mon'] == 'push', docdata(be, 'yc'))
            page.click('.pw-inweek .pk-chip >> text=Fri'); page.wait_for_timeout(300)
            check('tapping an on chip takes it out of the week', docdata(be, 'yc')['schedule']['week'].get('Fri') == '')
            check('delete is visible without opening anything', page.is_visible('#ed-delete') and page.inner_text('#ed-delete').lower() == 'delete this day')
            gap = page.evaluate("(() => { const a = document.querySelector('.pw-daymore').getBoundingClientRect(); const b = document.querySelector('#ed-delete').getBoundingClientRect(); return b.top - a.bottom; })()")
            check('delete has room above it', gap >= 24, gap)
            page.click('.pw-daymore summary'); page.click('#ed-kind ~ .ysel-btn, .pw-daymore .ysel-btn')
            check('type picker is a styled list', page.locator('.ysel-pop').count() == 1)
            page.keyboard.press('Escape')
            page.click('#ed-delete'); check('first tap asks again', 'tap again' in page.inner_text('#ed-delete').lower())
            page.click('#ed-delete'); page.wait_for_selector('.pw-top')
            check('second tap deletes the day', docdata(be, 'yc/templates/pull') is None and 'pull' not in page.inner_text('#editor').lower())
        errs = session(pw, be, ALICE, plan_week, width=390); check('no page errors (plan week)', not errs, errs)

        be = plan_be('rotation')
        def plan_rot(page):
            go(page, 'plan'); page.wait_for_selector('.pw-srow'); page.click('.pw-srow >> text=Edit'); page.wait_for_selector('.pw-inweek')
            check('rotation: Put in your week button', page.inner_text('.pw-inweek button').lower() == 'put in your week')
            page.click('.pw-inweek button')
            check('rotation: day joins the order', docdata(be, 'yc')['schedule']['rotation'] == ['push', 'legs', 'pull'], docdata(be, 'yc'))
            check('rotation: button flips', page.inner_text('.pw-inweek button').lower() == 'take out of your week')
            page.click('.pw-inweek button')
            check('rotation: and back out', docdata(be, 'yc')['schedule']['rotation'] == ['push', 'legs'])
        errs = session(pw, be, ALICE, plan_rot, width=1000); check('no page errors (plan rotation)', not errs, errs)

        # ---- 14. Home: invitation text, Connect to Claude, home screen
        be = Backend(); be.grants = []
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        def home_a(page):
            page.wait_for_selector('#v-home', state='visible')
            txt = page.inner_text('#v-home')
            for want in ('Feedback', 'Send bugs and feature requests', 'Free and private', '100% free. Forever.', 'No ads.', 'No tracking.', 'export it any time', 'What makes it different', 'Strong, Hevy or FitNotes', 'Use your own AI'):
                check('home says: ' + want, want.lower() in txt.lower(), txt[:200])
            check('home no longer promises 24 hours', '24 hours' not in txt and 'Made with you' not in txt)
            check('bullets are ticks', page.locator('.hm-checks li').count() == 5)
            page.evaluate("window.__opened = []; window.open = (u) => { window.__opened.push(u); return null; }; 0")
            page.wait_for_selector('#hm-claude:not([hidden])')
            check('button says Connect to Claude', page.inner_text('#hm-claude').lower() == 'connect to claude')
            page.click('#hm-claude'); page.wait_for_selector('#hm-claude-panel:not([hidden])')
            check('it opens the Claude connectors page', page.evaluate('window.__opened[0]') == 'https://claude.ai/customize/connectors', page.evaluate('window.__opened'))
            check('and copies the connector address', page.evaluate('navigator.clipboard.readText()').endswith('/functions/v1/mcp'))
            check('panel explains the two steps', 'Add custom connector' in page.inner_text('#hm-claude-panel') and 'Allow' in page.inner_text('#hm-claude-panel'))
            page.click('#hm-claude'); check('tap again closes the panel', page.is_hidden('#hm-claude-panel'))
            # home screen
            check('home screen button shown in a browser', page.is_visible('#hm-install'))
            page.click('#hm-install'); page.wait_for_selector('#hm-install-panel:not([hidden])')
            check('desktop gets the dock/address bar steps and the logo', 'address bar' in page.inner_text('#hm-install-panel') and page.locator('#hm-install-panel img[src^="icon-192"]').count() == 1)
            page.click('#hm-install')
            page.evaluate("(() => { const e = new Event('beforeinstallprompt'); e.prompt = () => { window.__prompted = true; return Promise.resolve(); }; e.userChoice = Promise.resolve({ outcome: 'accepted' }); window.dispatchEvent(e); })()")
            page.click('#hm-install'); page.wait_for_timeout(300)
            check('browsers that can install get the real prompt', page.evaluate('window.__prompted') is True)
        errs = session(pw, be, ALICE, home_a, width=390, home=True); check('no page errors (home)', not errs, errs)

        be = Backend()  # connector off: the button stays away
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        def home_b(page):
            page.wait_for_selector('#v-home', state='visible'); page.wait_for_timeout(500)
            check('no Connect button when the connector is off', page.is_hidden('#hm-claude'))
        errs = session(pw, be, ALICE, home_b, width=390, home=True); check('no page errors (home, connector off)', not errs, errs)

        be = Backend(); be.grants = []
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        def home_ios(page):
            page.wait_for_selector('#hm-install', state='visible'); page.click('#hm-install')
            t = page.inner_text('#hm-install-panel')
            check('iPhone gets Share, Add to Home Screen and the logo', 'Share' in t and 'Add to Home Screen' in t and page.locator('#hm-install-panel img').count() == 1, t)
        errs = session(pw, be, ALICE, home_ios, width=390, home=True, ua='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
        check('no page errors (home iOS)', not errs, errs)
        be = Backend(); be.grants = []
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        def home_android(page):
            page.wait_for_selector('#hm-install', state='visible'); page.click('#hm-install')
            t = page.inner_text('#hm-install-panel')
            check('Android gets Install app steps', 'Install app' in t and 'three dots' in t, t)
        errs = session(pw, be, ALICE, home_android, width=390, home=True, ua='Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36')
        check('no page errors (home Android)', not errs, errs)

        # ---- 15. finishing a day asks about Coach Claude only when Claude is connected
        def finish_be(grants):
            be = Backend(); be.grants = grants
            be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
            be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
            be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'weekday': 'Mon', 'kind': 'Push', 'focus': 'Chest', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': 8, 'target': '', 'rest_s': 90, 'note': None}]}})
            return be
        def fin_claude(page):
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-fin', state='visible')
            page.evaluate("window.__opened = []; if (!window.__oc) { window.__oc = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { if (/claude\\.ai/.test(this.href)) { window.__opened.push(this.href); return; } return window.__oc.call(this); }; } 0")
            page.click('#resume-fin'); page.click('#finish-go'); page.wait_for_selector('#claude-review-go')
            check('asks: Send to Claude, with what happens next', 'claude reads it through your connector' in page.text_content('.ydlg').lower() and page.text_content('#claude-review-go').strip().lower() == 'send to claude', page.text_content('.ydlg'))
            check('focus is on the Send button', page.evaluate("document.activeElement.id") == 'claude-review-go')
            page.click('.ydlg >> text=Not now'); check('Not now closes it', page.locator('.ydlg').count() == 0)
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-fin', state='visible')
            page.evaluate("window.__opened = []; if (!window.__oc) { window.__oc = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { if (/claude\\.ai/.test(this.href)) { window.__opened.push(this.href); return; } return window.__oc.call(this); }; } 0")
            page.click('#resume-fin'); page.click('#finish-go'); page.wait_for_selector('#claude-review-go'); page.keyboard.press('Escape'); check('Escape closes it', page.locator('.ydlg').count() == 0)
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-fin', state='visible')
            page.evaluate("window.__opened = []; if (!window.__oc) { window.__oc = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { if (/claude\\.ai/.test(this.href)) { window.__opened.push(this.href); return; } return window.__oc.call(this); }; } 0")
            page.click('#resume-fin'); page.click('#finish-go'); page.wait_for_selector('#claude-review-go'); page.click('#claude-review-go'); page.wait_for_timeout(300)
            u = page.evaluate('window.__opened[0]') or ''
            check('Send opens Claude with the request', u.startswith('https://claude.ai/new?q=') and 'Push day' in urllib.parse.unquote(u) and 'connector' in urllib.parse.unquote(u), u)
            check('after Send the app is back on the Train screen', page.is_visible('#pickday') and page.locator('.ydlg, .fin').count() == 0 and not page.evaluate("document.body.classList.contains('fin-open')"))
            check('request is also on the clipboard', 'Push day' in page.evaluate('navigator.clipboard.readText()'))
        errs = session(pw, finish_be([{'client': {'id': 'c-claude', 'name': 'Claude'}, 'scopes': [], 'granted_at': now()}]), ALICE, fin_claude, width=390) if False else session(pw, finish_be([{'client': {'id': 'c-claude', 'name': 'Claude'}, 'scopes': [], 'granted_at': now()}]), ALICE, fin_claude, width=390)
        check('no page errors (finish asks)', not errs, errs)
        def fin_none(page):
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-fin', state='visible')
            page.click('#resume-fin'); page.click('#finish-go'); page.wait_for_timeout(700)
            check('no question without a connected Claude', page.locator('.ydlg').count() == 0)
        errs = session(pw, finish_be([]), ALICE, fin_none, width=390); check('no page errors (finish quiet)', not errs, errs)

        # ---- 16. Progress: the chart axis shows weights you lifted by default
        be = Backend(); be.grants = []
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        be.docs.append({'path': 'yc/exercises/squat', 'data': {'name': 'Squat', 'group': 'Legs', 'category': 'strength', 'unit': 'kg'}})
        for k, (l1, r1, l2, r2) in zip((6, 4, 2), ((60, 8, 40, 12), (70, 8, 50, 12), (80, 8, 60, 12))):
            day = (datetime.date.today() - datetime.timedelta(days=k)).isoformat()
            be.docs.append({'path': 'yc/sessions/' + day, 'data': {'date': day, 'label': 'Legs', 'finished_at': 1, 'sets': {'a': {'ex': 'squat', 'n': 1, 'order': 1, 'kind': 'work', 'reps': r1, 'load': l1, 'done': True}, 'b': {'ex': 'squat', 'n': 2, 'order': 1, 'kind': 'work', 'reps': r2, 'load': l2, 'done': True}}}})
        def trends(page):
            go(page, 'progress'); page.wait_for_selector('.prow'); page.click('.prow')
            page.wait_for_selector('.p-detail svg')
            check('heaviest set is the default chart', 'heaviest set per workout' in (page.get_attribute('.p-detail svg', 'aria-label') or '').lower() or 'heaviest set' in page.inner_text('.p-detail').lower(), page.inner_text('.p-detail')[:200])
            nums = page.evaluate("[...document.querySelectorAll('.p-detail svg text')].map(t => parseFloat(t.textContent)).filter(n => !isNaN(n))")
            check('axis stays at lifted weights (no estimated 1RM above 80 kg)', nums and max(nums) <= 90, nums)
            page.click('.p-detail >> text=Est. strength')
            check('estimate chart says it is an estimate', 'not a weight you lifted' in page.inner_text('.p-detail'))
            labs = page.evaluate("[...document.querySelectorAll('.p-detail .val-lab')].map(t => t.textContent)")
            check('estimate points are labelled as estimates', labs and all(l.startswith('≈') for l in labs), labs)
        errs = session(pw, be, ALICE, trends, width=1000); check('no page errors (trends)', not errs, errs)

        # ---- 12. the security policy is active: every screen works with it, and nothing leaves the site except Supabase
        be = Backend(); be.grants = []
        base = 'yc/'
        d0 = datetime.date.today()
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach', 'schedule': {'enabled': True, 'mode': 'fixed', 'week': {'Mon': 'push'}}}})
        be.docs.append({'path': base + 'templates/push', 'data': {'name': 'Push', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '8', 'target': '60'}]}})
        be.docs.append({'path': base + 'exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'unit': 'kg', 'category': 'strength'}})
        for k in (1, 3):
            day = (d0 - datetime.timedelta(days=k)).isoformat()
            be.docs.append({'path': base + 'sessions/' + day, 'data': {'date': day, 'label': 'Push', 'template': 'push', 'finished_at': 1, 'sets': {'a': {'ex': 'bench', 'n': 1, 'order': 1, 'kind': 'work', 'reps': 8, 'load': 60, 'done': True}}}})
        def policy(page):
            page.wait_for_selector('#tab-progress')
            for tab in ('train', 'plan', 'progress', 'food', 'feedback', 'settings', 'home'):
                if page.is_visible('#tab-' + tab): page.click('#tab-' + tab)
                page.wait_for_timeout(250)
            page.click('#tab-progress'); page.wait_for_selector('#p-days rect', state='attached')
            check('the chart (d3) loads from this site with the policy on', page.evaluate("typeof d3") == 'object')
            check('fonts come from this site', page.evaluate("document.fonts.check('700 1em \"Barlow Condensed\"')") is True)
            page.click('#tab-settings'); page.wait_for_selector('#look .set-tog')
            if page.get_attribute('#look .set-tog', 'aria-expanded') != 'true': page.click('#look .set-tog')
            page.click('#look-row >> text=Dark')
            check('policy on: dark theme still applies', page.evaluate("document.documentElement.dataset.theme") == 'dark')
            meta = page.get_attribute('meta[http-equiv="Content-Security-Policy"]', 'content')
            check('policy forbids inline script without a hash and other hosts', "script-src 'self' 'sha256-" in meta and 'unsafe-inline' not in meta.split('style-src')[0] and 'unsafe-eval' not in meta and "default-src 'none'" in meta, meta[:200])
        errs = session(pw, be, ALICE, policy, width=1000, csp=True); check('no CSP violations or errors with the policy on', not errs, errs)
        # ---- languages ----
        print('languages')
        if True:
            be = Backend()
            def picker(page):
                page.wait_for_selector('.yl-b')
                names = page.eval_on_selector_all('.yl-b', 'els => els.map(e => e.textContent)')
                check('first start: the picker offers six languages in order', names == ['Nederlands', 'English', 'Español', 'Deutsch', 'Français', 'Italiano'], names)
                check('first start: nothing chosen yet', page.evaluate("localStorage.getItem('yc-lang')") is None)
                page.click('.yl-b[lang=nl]'); page.wait_for_load_state('load'); page.wait_for_selector('#v-home', state='visible')
                check('choosing a language stores it', page.evaluate("localStorage.getItem('yc-lang')") == 'nl')
                check('picker gone after choosing', page.query_selector('.yl-b') is None)
                check('page language is set', page.evaluate("document.documentElement.lang") == 'nl')
                check('Home is translated', 'Training van vandaag' in page.inner_text('#hm-train').capitalize() or 'vandaag' in page.inner_text('#hm-train').lower(), page.inner_text('#hm-train'))
                page.reload(); page.wait_for_selector('#v-home', state='visible')
                check('choice survives a reload without asking again', page.query_selector('.yl-b') is None and page.evaluate("document.documentElement.lang") == 'nl')
                page.click('#hm-train'); go(page, 'settings')
                if page.get_attribute('#lang .set-tog', 'aria-expanded') != 'true': page.click('#lang .set-tog')
                check('Settings has a languages section, titled in Dutch', page.inner_text('#h-lang').strip().lower() == 'talen', page.inner_text('#h-lang'))
                checked = page.eval_on_selector_all('#lang-list [aria-checked=true]', 'els => els.map(e => e.textContent)')
                check('the current language is marked', len(checked) == 1 and 'Nederlands' in checked[0], checked)
                check('six options in Settings', page.locator('#lang-list button').count() == 6)
                check('the notice says the translations are AI-generated', 'AI' in page.inner_text('#lang .note') and 'Engels' in page.inner_text('#lang .note'), page.inner_text('#lang .note'))
                page.click('#lang-list button:has-text("Español")'); page.wait_for_load_state('load'); page.wait_for_selector('#v-home', state='visible')
                check('switching in Settings changes the language', page.evaluate("localStorage.getItem('yc-lang')") == 'es' and page.evaluate("document.documentElement.lang") == 'es')
                page.click('#hm-train'); go(page, 'settings')
                if page.get_attribute('#lang .set-tog', 'aria-expanded') != 'true': page.click('#lang .set-tog')
                check('the notice is in Spanish now', 'inglés' in page.inner_text('#lang .note'), page.inner_text('#lang .note'))
                page.click('#lang-report'); page.wait_for_selector('#v-feedback', state='visible')
                check('report button opens the form prefilled with the language', 'es' in page.input_value('#v-feedback input[maxlength="120"]'), page.input_value('#v-feedback input[maxlength="120"]'))
                page.click('#lang-list button:has-text("English")') if page.is_visible('#lang-list') else None
            errs = session(pw, be, ALICE, picker, width=390, lang=None, home=True); check('no errors in the language flow', not errs, errs)
            # English: no dictionary needed, nothing changes, weekday chips stay English
            def english(page):
                page.wait_for_selector('#v-home', state='visible')
                check('English: no picker when a choice exists', page.query_selector('.yl-b') is None and page.evaluate("document.documentElement.lang") == 'en')
            session(pw, Backend(), ALICE, english, width=390, lang='en', home=True)
            # with the content security policy on, the dictionary still loads from this site
            def csp_de(page):
                page.wait_for_selector('#v-home', state='visible'); page.wait_for_timeout(500)
                check('policy on: the German dictionary loads', 'Heutiges Training' in page.inner_text('#hm-train').title() or 'HEUTIGES' in page.inner_text('#hm-train').upper(), page.inner_text('#hm-train'))
            errs = session(pw, Backend(), ALICE, csp_de, width=390, csp=True, lang='de', home=True); check('policy on: no violations with a translation', not errs, errs)
    check('nothing left the site except Supabase (no fonts, CDNs or analytics)', not [u for u in EXTERNAL if not u.startswith('data:') and not u.startswith(SUPA)], sorted(set(EXTERNAL))[:5])
finally:
    server.terminate()
done()
