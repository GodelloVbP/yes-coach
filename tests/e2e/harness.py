"""Shared pieces of the end-to-end tests: the real built app in headless Chrome with Supabase faked in memory."""
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

def settled(page, secs=10):
    """True once the app has nothing left to save. The app asks before a page is left while sets or notes are unsent (a beforeunload prompt),
    and these tests dismiss every dialog, which cancels the reload and leaves it waiting. Wait for the same condition the browser uses."""
    end = time.time() + secs
    while time.time() < end:
        if not page.evaluate("() => { const e = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(e); return e.defaultPrevented; }"): return True
        page.wait_for_timeout(100)
    return False

class Backend:
    def __init__(self, admins=()):
        self.tickets, self.messages, self.calls, self.requests = [], [], [], []
        self.admins = set(admins)
        self.docs = []
        self.grants = None  # None: the OAuth server is off (404)
        self.push_subs = []  # rest alerts: devices that allowed them
        self.rest_calls = []  # and what the app asked the rest-push function
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
        if path == '/rest/v1/push_subs':  # devices that allowed rest alerts
            if req.method == 'GET': return ok(list(self.push_subs))
            if req.method == 'DELETE':
                gone = (q.get('endpoint', [''])[0] or '').replace('eq.', '', 1)
                self.push_subs = [x for x in self.push_subs if x['endpoint'] != gone]; return empty()
            rows = body or []
            for r in (rows if isinstance(rows, list) else [rows]):
                self.push_subs = [x for x in self.push_subs if x['endpoint'] != r['endpoint']] + [dict(r, user_id=me)]
            return empty(201)
        if path == '/functions/v1/rest-push':  # the rest alert function: it only records what was asked
            call = body or {}
            self.rest_calls.append(call)
            return ok({'scheduled': True, 'id': 'alert-%d' % len(self.rest_calls)} if call.get('action') == 'schedule' else {'cancelled': True})
        if path == '/auth/v1/user/oauth/grants':
            if self.grants is None: return ok({'msg': 'oauth server disabled'}, 404)
            if req.method == 'GET': return ok(self.grants)
            if req.method == 'DELETE':
                self.calls.append(('revoke', q.get('client_id', [None])[0])); self.grants = [g for g in self.grants if g['client']['id'] != q.get('client_id', [None])[0]]; return empty()
        if path == '/rest/v1/docs' and req.method == 'GET':
            want = q.get('path', [''])[0]
            return ok([d for d in self.docs if d['path'] == want[3:]] if want.startswith('eq.') else self.docs)  # a lookup of one path finds that path only
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

PAGE = {}  # the page being driven: waiting must go through Playwright, or its route handlers (the fake server) never run
_tally = {'passed': 0, 'failed': 0}
def check(name, cond, extra=''):
    _tally['passed' if cond else 'failed'] += 1
    if not cond: print('FAIL', name, extra)
def done():
    """Print the result and exit non-zero when a check failed. The last line of every suite."""
    print('passed', _tally['passed'], 'failed', _tally['failed'])
    raise SystemExit(1 if _tally['failed'] else 0)
def until(fn, secs=8):
    end = time.time() + secs
    while time.time() < end:
        try:
            if fn(): return True
        except Exception: pass
        PAGE['p'].wait_for_timeout(100)
    return False
def vis(page, sel): return page.is_visible(sel)

EXTERNAL = []  # every request that tried to leave localhost and the Supabase stand-in

def session(pw, be, uid, scenario, width=1000, csp=False, home=False, ua=None, lang='en', clock=None):
    br = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = br.new_context(device_scale_factor=float(__import__('os').environ.get('DSF', '1')), viewport={'width': width, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'], bypass_csp=not csp, **({'user_agent': ua} if ua else {}))
    sess = {'access_token': jwt(uid), 'token_type': 'bearer', 'expires_in': 3600, 'expires_at': 4102444800, 'refresh_token': 'r',
            'user': {'id': uid, 'email': EMAILS[uid], 'aud': 'authenticated', 'role': 'authenticated'}}
    ctx.add_init_script("localStorage.setItem('sb-qazvzhhoalkyyasakphs-auth-token', %s)" % json.dumps(json.dumps(sess)))
    if lang: ctx.add_init_script("if (!sessionStorage.getItem('lang-init')) { localStorage.setItem('yc-lang', %s); sessionStorage.setItem('lang-init', '1'); }" % json.dumps(lang))
    ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://localhost') else (EXTERNAL.append(r.request.url), r.abort()))  # nothing else leaves the machine
    ctx.route(SUPA + '/**', be.handle)
    if clock: ctx.clock.install(time=clock)  # a fixed start time that then runs on, for tests about today
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e) + ' @ ' + str(getattr(e, 'stack', ''))[:600]))
    page.on('console', lambda m: errors.append('CSP: ' + m.text) if 'Content Security Policy' in m.text else None)
    page.on('dialog', lambda d: d.dismiss())
    page.goto(BASE + '#home')  # signed-in users open on Train; #home keeps the old tests on the page they were written for
    if not home:
        page.wait_for_selector('#v-home', state='visible')  # the app opens on Home
        try: page.click('#hm-train', timeout=4000)
        except Exception: pass  # a dialog on top (ticket pop-up) leaves the user on Home
    PAGE['p'] = page
    try: scenario(page)
    except Exception:
        print('PAGE ERRORS:', errors[:5])
        raise
    finally:
        br.close()
    return errors


