"""End-to-end check, part of the old tickets file: owner copies, the Home link, navigation, theme, Progress tooltip, connected AI apps. The real built app in headless Chrome, Supabase faked in memory."""
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
        # ---- 7b. owner copies the shown tickets as text, without emails
        be = Backend(admins=[OWNER])
        a = be.ticket(ALICE, title='Finish button', type='feature', first_name='Sanne', body='Please add a finish workout button.', context={'installed': True, 'screen': '390x844', 'ua': 'iPhone Safari'})
        be.message(a['id'], 'admin', 'Do you mean on the Train screen?'); be.message(a['id'], 'user', 'Yes, at the bottom.')
        be.ticket(ALICE, title='Closed one', status='resolved', outcome='built', resolution_note='Done.', resolved_at=now())
        got = {}
        def s8b(page):
            open_feedback(page); page.wait_for_selector('.tk-bar'); page.click('.tk-bar > summary'); page.wait_for_selector('#tk-admin-list .tk-card')
            page.click('.tk-bar >> text=Copy these tickets'); page.wait_for_function("document.querySelector('.tk-bar-body').innerText.includes('Copied')")
            got['text'] = page.evaluate('navigator.clipboard.readText()')
        errs = session(pw, be, OWNER, s8b)
        t = got.get('text', '')
        check('copy has the shown ticket, name, text, thread, device', all(x in t for x in ('Finish button', 'Sanne', 'Please add a finish workout button.', 'We wrote: Do you mean on the Train screen?', 'Sanne wrote: Yes, at the bottom.', 'installed app')), t)
        check('copy leaves out email and closed tickets', 'example.com' not in t and 'Closed one' not in t, t)
        check('no page errors (copy)', not errs, errs)

        # ---- 7c. an open day can be finished from the Resume bar
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'weekday': 'Mon', 'kind': 'Push', 'focus': 'Chest', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': 8, 'target': '', 'target_at': datetime.date.today().isoformat(), 'rest_s': 90, 'note': None}]}})
        def s7c(page):
            page.wait_for_selector('#tab-train', state='attached')
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-btn', state='visible'); page.click('#resume-btn'); page.wait_for_selector('#session', state='visible')
            check('bottom button says Finish workout', page.locator('#session >> text=Finish workout').count() >= 1)
            page.click('#sb-back'); page.wait_for_selector('#resume', state='visible')
            check('resume bar offers Finish workout', page.is_visible('#resume-fin') and 'finish workout' in page.inner_text('#resume-fin').lower())
            page.click('#resume-fin'); page.click('#finish-go'); page.wait_for_selector('#resume', state='hidden')
            check('finishing clears the open day', page.evaluate("localStorage.getItem('yc-active')") in (None, 'null'))
            page.reload(); page.wait_for_timeout(800)
            check('not shown again after a reload', not page.is_visible('#resume'))
        errs = session(pw, be, ALICE, s7c, width=390); check('no page errors (finish)', not errs, errs)

        # ---- 8. Home link opens the tab
        be = Backend()
        def s10(page):
            page.wait_for_selector('#tab-feedback:not([hidden])', state='attached'); logo(page)
            page.click('#hm-ticket')
            page.wait_for_selector('#tk', state='visible')
            check('home link opens the tab', page.get_attribute('#tab-feedback', 'aria-selected') == 'true')
            page.goto(BASE); page.wait_for_selector('#v-train', state='visible')
            check('signed in, the app opens on Train after reload', page.is_visible('#v-train') and page.get_attribute('#tab-feedback', 'aria-selected') != 'true')
        errs = session(pw, be, ALICE, s10); check('no page errors (home link)', not errs, errs)

        # ---- 9. navigation: a sidebar from 1024px, a bottom bar below it; More holds the rest
        be = Backend()
        def desk(page):
            page.wait_for_selector('#tab-feedback:not([hidden])', state='attached')
            check('wide: sidebar on the left', page.evaluate("(() => { const r = document.querySelector('#tabs-nav').getBoundingClientRect(); return r.left === 0 && r.top === 0 && r.width < 300 && r.height >= innerHeight - 1; })()"))
            check('wide: six main entries visible, Request among them', all(page.is_visible('#tab-' + t) for t in ('train', 'plan', 'progress', 'food', 'feedback', 'settings')))
            check('wide: Exercises is not in the bar', not page.is_visible('#tab-exercises'))
            page.wait_for_timeout(600)
            check('wide: no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        for w in (1024, 1280): errs = session(pw, be, ALICE, desk, width=w); check('no errors wide %d' % w, not errs, errs)
        def phone(page):
            page.wait_for_selector('#tab-feedback', state='attached'); page.wait_for_timeout(300)
            check('phone: bottom bar at the bottom', page.evaluate("(() => { const r = document.querySelector('#tabs-nav').getBoundingClientRect(); return Math.abs(r.bottom - innerHeight) < 1 && r.left === 0 && r.right <= innerWidth + 0.5; })()"))
            check('phone: six entries, Request between Food and More', all(page.is_visible('#tab-' + t) for t in ('train', 'plan', 'progress', 'food', 'feedback', 'settings')) and page.evaluate("[...document.querySelectorAll('.mainnav .tab:not(.tab-sub)')].map((t) => t.id).join()") == 'tab-train,tab-plan,tab-progress,tab-food,tab-feedback,tab-settings')
            check('phone: no hamburger', page.query_selector('#menu-btn') is None)
            check('phone: Train is selected on start', page.get_attribute('#tab-train', 'aria-selected') == 'true' and page.is_visible('#v-train'))
            check('phone: no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            check('phone: no dot without a question', page.evaluate("getComputedStyle(document.querySelector('#tab-feedback .nav-dot')).display") == 'none')
            page.click('#tab-settings'); page.wait_for_selector('#more-feedback', state='visible')
            check('phone: More lists Exercises and Feedback', page.is_visible('#more-exercises') and page.is_visible('#more-feedback'))
            check('phone: More stays marked in the bar', page.get_attribute('#tab-settings', 'aria-selected') == 'true')
            page.click('#more-feedback'); page.wait_for_selector('#tk', state='visible')
            check('phone: Feedback opens from More, the bar marks Request and not More', page.get_attribute('#tab-feedback', 'aria-selected') == 'true' and 'in-more' not in (page.get_attribute('#tab-settings', 'class') or ''), page.get_attribute('#tab-settings', 'class'))
            page.click('#tab-train'); page.wait_for_selector('#v-train', state='visible')
            page.click('#tab-feedback'); page.wait_for_selector('#tk', state='visible')
            check('phone: the Request tab opens it in one tap', page.get_attribute('#tab-feedback', 'aria-selected') == 'true' and not page.is_visible('#v-train'))
            page.click('#tab-plan'); page.wait_for_selector('#v-plan', state='visible')
            check('phone: switching tabs works', page.get_attribute('#tab-plan', 'aria-selected') == 'true')
        be2 = Backend(); be2.ticket(ALICE, title='Q', status='needs_info')
        def dot(page):
            page.wait_for_selector('#tab-feedback.tk-dot', state='attached')
            check('phone: a dot on Request', page.evaluate("getComputedStyle(document.querySelector('#tab-feedback .nav-dot')).display") != 'none')
            page.click('#tab-settings'); page.wait_for_selector('#more-feedback', state='visible')
            check('phone: a dot on the Feedback row', page.evaluate("getComputedStyle(document.querySelector('#more-feedback .nav-dot')).display") != 'none')
        errs = session(pw, be2, ALICE, dot, width=390); check('no errors dot', not errs, errs)
        for w in (360, 375, 390, 414, 430): errs = session(pw, be, ALICE, phone, width=w); check('no errors phone %d' % w, not errs, errs)

        # ---- 10. theme: auto, light, dark; saved on this device; applied before the app loads
        be = Backend()
        def theme(page):
            page.wait_for_selector('#tab-settings'); page.click('#tab-settings'); page.wait_for_selector('#look .set-tog')
            if page.get_attribute('#look .set-tog', 'aria-expanded') != 'true': page.click('#look .set-tog')
            bg = lambda: page.evaluate("getComputedStyle(document.body).backgroundColor")
            attr = lambda: page.evaluate("document.documentElement.dataset.theme || 'auto'")
            checked = lambda: page.eval_on_selector('#look-row [aria-checked=true]', 'e => e.textContent')
            check('auto is the default', attr() == 'auto' and checked() == 'Auto')
            page.click('#look-row >> text=Dark'); check('dark applies', attr() == 'dark' and checked() == 'Dark' and bg() != 'rgb(255, 255, 255)', bg())
            page.reload(); page.wait_for_selector('#tab-settings')
            check('dark survives a reload', attr() == 'dark')
            page.click('#tab-settings'); page.wait_for_selector('#look .set-tog')
            if page.get_attribute('#look .set-tog', 'aria-expanded') != 'true': page.click('#look .set-tog')
            page.click('#look-row >> text=Light'); check('light applies over a dark system', attr() == 'light' and bg() == 'rgb(255, 255, 255)', bg())
            page.click('#look-row >> text=Auto'); check('auto removes the override', attr() == 'auto' and page.evaluate("localStorage.getItem('yc-theme')") is None)
        for scheme in ('dark', 'light'):
            br = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
            if scheme == 'dark':
                ctx = br.new_context(viewport={'width': 1000, 'height': 900}, color_scheme='dark')
                sess = {'access_token': jwt(ALICE), 'token_type': 'bearer', 'expires_in': 3600, 'expires_at': 4102444800, 'refresh_token': 'r', 'user': {'id': ALICE, 'email': EMAILS[ALICE], 'aud': 'authenticated', 'role': 'authenticated'}}
                ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('yc-lang', 'en'); localStorage.setItem('sb-qazvzhhoalkyyasakphs-auth-token', %s); sessionStorage.setItem('seeded', '1'); }" % json.dumps(json.dumps(sess)))
                ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://localhost') else r.abort()); ctx.route(SUPA + '/**', be.handle)
                page = ctx.new_page(); errs = []; page.on('pageerror', lambda e: errs.append(str(e))); page.goto(BASE)
                try:
                    # a dark system with no choice made: auto follows it
                    page.wait_for_selector('#tab-settings')
                    check('auto follows a dark system', page.evaluate("getComputedStyle(document.body).backgroundColor") != 'rgb(255, 255, 255)')
                    theme(page)
                finally: br.close()
                check('no page errors (theme)', not errs, errs)
            else: br.close()

        # ---- 11. Progress: the day tooltip keeps working after it was hidden once
        be = Backend()
        base = 'yc/'
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        be.docs.append({'path': base + 'exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        d0 = datetime.date.today()
        be.docs.append({'path': base + 'templates/push', 'data': {'name': 'Push day', 'order': 1, 'weekday': 'Mon', 'kind': 'Push', 'focus': 'Chest', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': 8, 'target': '', 'target_at': d0.isoformat(), 'rest_s': 90, 'note': None}]}})
        for k in (1, 3):
            day = (d0 - datetime.timedelta(days=k)).isoformat()
            be.docs.append({'path': base + 'sessions/' + day, 'data': {'date': day, 'split': 'Push', 'label': 'Push day', 'template': 'push' if k == 1 else 'gone', 'sets': {'a': {'ex': 'bench', 'n': 1, 'reps': 8, 'load': 60, 'done': True, 'order': 1}, 'b': {'ex': 'bench', 'n': 2, 'reps': 8, 'load': 60, 'done': True, 'order': 2}}}})
        def hover(page):
            page.wait_for_selector('#tab-progress'); page.click('#tab-progress'); page.wait_for_selector('#p-days rect', state='attached')
            cells = page.locator('#p-days rect')
            n = cells.count(); trained = [i for i in range(n) if (cells.nth(i).get_attribute('fill') or '') == 'var(--ink)']
            check('two trained days drawn', len(trained) == 2, trained)
            tipvis = lambda: page.evaluate("(() => { const t = document.querySelector('#p-days .tip'); return !!t && !t.hidden && getComputedStyle(t).display !== 'none'; })()")
            for attempt in (1, 2, 3):
                for i in trained:
                    page.evaluate("document.querySelector('#p-days').scrollIntoView({ block: 'center' })")  # clear of the bottom bar
                    box = cells.nth(i).bounding_box(); page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                    page.wait_for_timeout(120)
                    check('tooltip shows on hover #%d day %d' % (attempt, i), tipvis())
                page.mouse.move(2, 2); page.wait_for_timeout(120)
                check('tooltip hides when leaving #%d' % attempt, not tipvis())
            links = page.eval_on_selector_all('#p-days rect.day-go', 'e => e.length')
            check('only the day whose plan day still exists is a link', links == 1, links)
            tip = lambda: page.evaluate("document.querySelector('#p-days .tip').innerText")
            box = cells.nth(trained[1]).bounding_box(); page.mouse.move(box['x'] + 4, box['y'] + 4); page.wait_for_timeout(120)
            check('tooltip offers to open it', 'open workout' in tip().lower(), tip())
            cells.nth(trained[1]).click()
            page.wait_for_selector('#session', state='visible')
            check('click opens that session on the Train tab', page.get_attribute('#tab-train', 'aria-selected') == 'true' and page.is_visible('#session'))
            check('it is the clicked date and plan day', json.loads(page.evaluate("localStorage.getItem('yc-active')")).get('date') == (d0 - datetime.timedelta(days=1)).isoformat() and json.loads(page.evaluate("localStorage.getItem('yc-active')")).get('tpl') == 'push')
            page.click('#sb-back'); page.click('#tab-progress'); page.wait_for_selector('#p-days rect.day-go', state='attached')
            c2 = page.locator('#p-days rect.day-go').first; c2.focus(); page.keyboard.press('Enter')
            page.wait_for_selector('#session', state='visible')
            check('keyboard Enter opens it too', page.is_visible('#session'))
        errs = session(pw, be, ALICE, hover, width=1000); check('no page errors (hover)', not errs, errs)
        # ---- 11. connected AI apps in Settings
        def conn_open(page):
            page.wait_for_selector('#tab-settings'); page.click('#tab-settings'); page.wait_for_selector('#look .set-tog')
        def conn_off(page):
            conn_open(page); page.wait_for_timeout(400)
            check('connected apps hidden when the OAuth server is off', page.is_hidden('#conn'))
        be = Backend(); errs = session(pw, be, ALICE, conn_off, width=1000); check('no page errors (conn off)', not errs, errs)
        be = Backend(); be.grants = [{'client': {'id': 'c-claude', 'name': 'Claude', 'uri': 'https://claude.ai'}, 'scopes': ['openid'], 'granted_at': now()}, {'client': {'id': 'c-x', 'name': 'Other AI'}, 'scopes': [], 'granted_at': now()}]
        def conn_on(page):
            conn_open(page); page.wait_for_selector('#conn:not([hidden])')
            if page.get_attribute('#conn .set-tog', 'aria-expanded') != 'true': page.click('#conn .set-tog')
            check('connector address shown', page.input_value('#conn-url') == 'https://qazvzhhoalkyyasakphs.supabase.co/functions/v1/mcp', page.input_value('#conn-url'))
            page.click('#conn-copy'); page.wait_for_function("document.querySelector('#conn-state').textContent.length > 0")
            check('copy gives feedback', page.inner_text('#conn-state') in ('Copied.', 'Press and hold the address to copy it.'))
            check('step by step link', page.get_attribute('#conn a.link', 'href') == 'connect.html')
            pass
            check('lists both apps', page.inner_text('#conn-list').lower().count('disconnect') == 2 and 'Claude' in page.inner_text('#conn-list') and 'Other AI' in page.inner_text('#conn-list'))
            page.click('#conn-list button[aria-label="Disconnect Claude"]')
            page.wait_for_function("document.querySelectorAll('#conn-list button').length === 1")
            check('revoked that client only', ('revoke', 'c-claude') in be.calls and [g['client']['id'] for g in be.grants] == ['c-x'], be.calls)
            page.click('#conn-list button'); page.wait_for_function("document.querySelector('#conn-list').textContent.includes('None connected')")
            check('empty state', 'None connected' in page.inner_text('#conn-list'))
        errs = session(pw, be, ALICE, conn_on, width=1000); check('no page errors (conn on)', not errs, errs)
finally:
    server.terminate()
done()
