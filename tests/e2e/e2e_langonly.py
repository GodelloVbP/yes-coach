"""End-to-end check of the tickets screens: the real built app in headless Chrome, Supabase faked in memory."""
import json, base64, subprocess, time, uuid, datetime, urllib.parse, sys
from playwright.sync_api import sync_playwright

import pathlib
REPO = str(pathlib.Path(__file__).resolve().parents[2])
BASE = 'http://localhost:8765/index.html'
SUPA = 'https://qazvzhhoalkyyasakphs.supabase.co'
ALICE, OWNER = '11111111-1111-1111-1111-111111111111', '44444444-4444-4444-4444-444444444444'
EMAILS = {ALICE: 'alice@example.com', OWNER: 'owner@example.com'}

def jwt(uid):
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()
    return b({'alg': 'HS256'}) + '.' + b({'sub': uid, 'exp': 4102444800, 'role': 'authenticated'}) + '.sig'
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

class Backend:
    def __init__(self, admins=()):
        self.tickets, self.messages, self.calls, self.requests = [], [], [], []
        self.admins = set(admins)
        self.docs = []
        self.grants = None  # None: the OAuth server is off (404)
    def ticket(self, user, **kw):
        t = dict(id=str(uuid.uuid4()), user_id=user, first_name='Alice', user_email=EMAILS.get(user, 'u@example.com'), type='feature', title='Dark mode', body='please add dark mode', status='open', outcome=None,
                 resolution_note=None, duplicate_of=None, app_version='t', context={}, created_at=now(), updated_at=now(), resolved_at=None, user_seen_at=None)
        t.update(kw); self.tickets.append(t); return t
    def message(self, tid, author, body):
        self.messages.append(dict(id=str(uuid.uuid4()), ticket_id=tid, author=author, body=body, created_at=now()))
    def uid(self, req):
        tok = req.headers.get('authorization', '').split(' ')[-1]
        try: return json.loads(base64.urlsafe_b64decode(tok.split('.')[1] + '=='))['sub']
        except Exception: return None
    def match(self, rows, q):
        for k, v in q.items():
            if k in ('select', 'order', 'limit', 'offset', 'columns'): continue
            v = v[0]
            if v.startswith('eq.'): rows = [r for r in rows if str(r.get(k)) == v[3:]]
            elif v.startswith('in.('): ids = v[4:-1].split(','); rows = [r for r in rows if str(r.get(k)) in ids]
        return rows
    def handle(self, route):
        req = route.request
        cors = {'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*'}
        if req.method == 'OPTIONS': return route.fulfill(status=204, headers=cors)
        u = urllib.parse.urlparse(req.url); q = urllib.parse.parse_qs(u.query); path = u.path
        me = self.uid(req); body = json.loads(req.post_data) if req.post_data else None
        self.requests.append((req.method, path, u.query, body))
        def ok(data, status=200): route.fulfill(status=status, headers={**cors, 'content-type': 'application/json'}, body=json.dumps(data))
        def empty(status=204): route.fulfill(status=status, headers=cors)
        def cols(rows):
            sel = q.get('select', ['*'])[0]
            return rows if sel == '*' else [{c: r[c] for c in sel.split(',')} for r in rows]
        def visible(rows): return rows if me in self.admins else [r for r in rows if r.get('user_id', me) == me]
        if path == '/auth/v1/user/oauth/grants':
            if self.grants is None: return ok({'msg': 'oauth server disabled'}, 404)
            if req.method == 'GET': return ok(self.grants)
            if req.method == 'DELETE':
                self.calls.append(('revoke', q.get('client_id', [None])[0])); self.grants = [g for g in self.grants if g['client']['id'] != q.get('client_id', [None])[0]]; return empty()
        if path == '/rest/v1/docs' and req.method == 'GET': return ok(self.docs)
        if path == '/rest/v1/rpc/yc_update':
            def dm(a, b):
                a = dict(a) if isinstance(a, dict) else {}
                for k, v in b.items(): a[k] = dm(a.get(k), v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
                return a
            cur = next((d for d in self.docs if d['path'] == body['p_path']), None)
            if cur is None: cur = {'path': body['p_path'], 'data': {}}; self.docs.append(cur)
            cur['data'] = dm(cur['data'], body['p_patch']); return ok(cur['data'])
        if path == '/rest/v1/docs' and req.method == 'DELETE':
            gone = q.get('path', [''])[0][3:]; self.docs = [d for d in self.docs if d['path'] != gone]; return empty()
        if path == '/rest/v1/docs' and req.method in ('POST', 'PATCH') and body is not None:
            for row in (body if isinstance(body, list) else [body]):
                if 'path' not in row: continue
                cur = next((d for d in self.docs if d['path'] == row['path']), None)
                if cur: cur.update({k: v for k, v in row.items() if k in ('data', 'path')})
                else: self.docs.append({k: v for k, v in row.items() if k in ('data', 'path')})
            return ok([], 201)
        if path == '/rest/v1/docs': return ok([], 201)
        if path == '/rest/v1/rpc/user_count': return ok(1)
        if path == '/rest/v1/rpc/is_admin': return ok(me in self.admins)
        if path == '/rest/v1/rpc/admin_reply':
            self.calls.append(('admin_reply', body)); self.message(body['p_ticket'], 'admin', body['p_body'])
            if body.get('p_ask'): [t.update(status='needs_info') for t in self.tickets if t['id'] == body['p_ticket']]
            return ok(None)
        if path == '/rest/v1/rpc/admin_set_ticket':
            self.calls.append(('admin_set_ticket', body))
            t = next(t for t in self.tickets if t['id'] == body['p_id'])
            t.update(status=body['p_status'], outcome=body['p_outcome'], resolution_note=body['p_note'] or None, duplicate_of=body['p_duplicate_of'])
            if t['status'] in ('resolved', 'declined'): t.update(user_seen_at=None, resolved_at=now())
            return ok(t)
        if path == '/rest/v1/rpc/admin_delete_ticket':
            self.calls.append(('admin_delete_ticket', body)); self.tickets = [t for t in self.tickets if t['id'] != body['p_id']]; return ok(None)
        if path == '/rest/v1/tickets':
            if req.method == 'GET':
                rows = self.match(visible(list(self.tickets)), q)
                rows.sort(key=lambda r: r['created_at'], reverse='desc' in q.get('order', ['created_at.desc'])[0]); return ok(cols(rows))
            if req.method == 'POST':
                if getattr(self, 'fail_insert', None): return ok({'message': self.fail_insert, 'code': 'P0001'}, 400)
                t = self.ticket(me, **{k: body[k] for k in ('type', 'title', 'body', 'first_name', 'app_version', 'context')}); return ok(cols([t]), 201)
            if req.method == 'PATCH':
                for t in self.match(visible(self.tickets), q): t.update(body)
                return empty()
        if path == '/rest/v1/ticket_messages':
            if req.method == 'GET':
                rows = [m for m in self.match(list(self.messages), q) if any(t['id'] == m['ticket_id'] and (me in self.admins or t['user_id'] == me) for t in self.tickets)]
                return ok(cols(sorted(rows, key=lambda r: r['created_at'])))
            if req.method == 'POST':
                self.message(body['ticket_id'], body['author'], body['body'])
                if body['author'] == 'user': [t.update(status='open') for t in self.tickets if t['id'] == body['ticket_id'] and t['status'] == 'needs_info']
                return empty(201)
        return ok({'message': 'unhandled ' + path}, 404)

passed = failed = 0
EXTERNAL = []  # every request that tried to leave localhost and the Supabase stand-in
def check(name, cond, extra=''):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print('FAIL', name, extra)

def session(pw, be, uid, scenario, width=1000, csp=False, home=False, ua=None, lang='en'):
    br = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = br.new_context(viewport={'width': width, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'], bypass_csp=not csp, **({'user_agent': ua} if ua else {}))
    sess = {'access_token': jwt(uid), 'token_type': 'bearer', 'expires_in': 3600, 'expires_at': 4102444800, 'refresh_token': 'r',
            'user': {'id': uid, 'email': EMAILS[uid], 'aud': 'authenticated', 'role': 'authenticated'}}
    ctx.add_init_script("localStorage.setItem('sb-qazvzhhoalkyyasakphs-auth-token', %s)" % json.dumps(json.dumps(sess)))
    if lang: ctx.add_init_script("if (!sessionStorage.getItem('lang-init')) { localStorage.setItem('yc-lang', %s); sessionStorage.setItem('lang-init', '1'); }" % json.dumps(lang))
    ctx.route(SUPA + '/**', be.handle)
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://localhost') else (EXTERNAL.append(r.request.url), r.abort()))  # nothing else leaves the machine
    ctx.route(SUPA + '/**', be.handle)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append('CSP: ' + m.text) if 'Content Security Policy' in m.text else None)
    page.on('dialog', lambda d: d.dismiss())
    page.goto(BASE + '#home')
    if not home:
        page.wait_for_selector('#v-home', state='visible')  # the app opens on Home
        try: page.click('#hm-train', timeout=4000)
        except Exception: pass  # a dialog on top (ticket pop-up) leaves the user on Home
    try: scenario(page)
    except Exception:
        print('PAGE ERRORS:', errors[:5])
        raise
    finally:
        br.close()
    return errors


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

def send_form(page, title, text, name=None, kind=None):
    page.click('#tk >> text=Send something')
    if name is not None: page.fill('#tk form input[autocomplete=given-name]', name)
    if kind: page.select_option('#tk form select', kind)
    page.fill('#tk form input[autocomplete=off]', title)
    page.fill('#tk form textarea', text)
    page.click('#tk form button[type=submit]')

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
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
finally:
    server.terminate()
print('passed %d, failed %d' % (passed, failed))
