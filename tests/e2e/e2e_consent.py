import json, sys
from playwright.sync_api import sync_playwright
from harness import serve, launch
srv=serve()
SB='https://qazvzhhoalkyyasakphs.supabase.co'
n=0
STUB="window.turnstile={render(b,o){setTimeout(()=>o.callback('TOKEN-1'),20);return 1},reset(){}};"
def ok(c,m):
    global n; n+=1
    if not c: print('FAIL',m); sys.exit(1)
def jwt():
    import base64
    b=lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()
    return b({'alg':'HS256','typ':'JWT'})+'.'+b({'sub':'u1','exp':4102444800,'aud':'authenticated','role':'authenticated','email':'a@b.nl'})+'.sig'
user={'id':'u1','aud':'authenticated','email':'a@b.nl','app_metadata':{},'user_metadata':{},'created_at':'2026-01-01T00:00:00Z'}
def run(already=False, bad_pw=False, invalid=False):
    log=[]
    with sync_playwright() as p:
        b=launch(p)
        pg=b.new_page()
        def auth(route):
            u=route.request.url; m=route.request.method
            log.append((m,u.replace(SB,'')))
            j=lambda o,c=200: route.fulfill(status=c,content_type='application/json',body=json.dumps(o),headers={'access-control-allow-origin':'*','access-control-allow-headers':'*'})
            if m=='OPTIONS': return route.fulfill(status=204,headers={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'*'})
            if '/token' in u:
                if bad_pw: return j({'error':'invalid_grant','error_description':'Invalid login credentials'},400)
                return j({'access_token':jwt(),'token_type':'bearer','expires_in':3600,'refresh_token':'r','user':user})
            if '/oauth/authorizations/' in u and u.endswith('/consent'):
                body=json.loads(route.request.post_data or '{}')
                return j({'redirect_url':'https://claude.ai/cb?'+('code=1' if body['action']=='approve' else 'error=access_denied')})
            if '/oauth/authorizations/' in u:
                if invalid: return j({'msg':'gone'},404)
                d={'authorization_id':'AID','redirect_uri':dest,'client':{'id':'c1','name':'<b>Claude</b>','uri':'https://claude.ai'},'scope':'openid'}
                if already: d['redirect_url']='https://claude.ai/cb?code=prev'
                return j(d)
            return j({})
        pg.route(SB+'/**',auth)
        pg.route('https://challenges.cloudflare.com/**',lambda r: r.fulfill(status=200,content_type='application/javascript',body=STUB))
        pg.route('https://claude.ai/**',lambda r: r.fulfill(status=200,body='back',content_type='text/plain'))
        return pg,b,p,log
def start(**k):
    pg,b,p,log=run(**k)
    return pg,b,log
# 1 no id
with sync_playwright() as p:
    b=launch(p); pg=b.new_page()
    pg.goto('http://127.0.0.1:8765/consent.html'); ok('Nothing to connect' in pg.inner_text('#msg'),'no id msg'); ok(pg.is_hidden('#login') and pg.is_hidden('#ask'),'no forms'); b.close()
# 2 sign in then approve
with sync_playwright() as p:
    b=launch(p); pg=b.new_page()
    def mk(pg,bad=False,already=False,invalid=False,log=None,dest='https://claude.ai/api/mcp/auth_callback'):
        def auth(route):
            u=route.request.url; m=route.request.method
            if log is not None: log.append((m,u.replace(SB,'')))
            hd={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'*'}
            j=lambda o,c=200: route.fulfill(status=c,content_type='application/json',body=json.dumps(o),headers=hd)
            if m=='OPTIONS': return route.fulfill(status=204,headers=hd)
            if '/token' in u:
                if bad: return j({'error':'invalid_grant','error_description':'Invalid login credentials'},400)
                return j({'access_token':jwt(),'token_type':'bearer','expires_in':3600,'refresh_token':'r','user':user})
            if u.endswith('/consent'):
                body=json.loads(route.request.post_data or '{}')
                return j({'redirect_url':'https://claude.ai/cb?'+('code=1' if body['action']=='approve' else 'error=access_denied')})
            if '/oauth/authorizations/' in u:
                if invalid: return j({'msg':'gone'},404)
                d={'authorization_id':'AID','redirect_uri':dest,'client':{'id':'c1','name':'<b>Claude</b>','uri':'https://claude.ai'},'scope':'openid'}
                if already: d['redirect_url']='https://claude.ai/cb?code=prev'
                return j(d)
            return j({})
        pg.route(SB+'/**',auth)
        pg.route('https://challenges.cloudflare.com/**',lambda r: r.fulfill(status=200,content_type='application/javascript',body=STUB))
        pg.route('https://claude.ai/**',lambda r: r.fulfill(status=200,body='back',content_type='text/plain'))
    log=[]; mk(pg,log=log)
    pg.goto('http://127.0.0.1:8765/consent.html?authorization_id=AID')
    pg.wait_for_selector('#login:not([hidden])'); ok(pg.is_hidden('#ask'),'sign-in first')
    pg.fill('#em','a@b.nl'); pg.fill('#pw','x'); pg.click('#login-go')
    pg.wait_for_selector('#ask:not([hidden])')
    ok(pg.inner_text('#client')=='<b>Claude</b>' and pg.locator('#client b').count()==0,'client name is text, not html')
    ok('a@b.nl' in pg.inner_text('#me') and 'claude.ai' in pg.inner_text('#client-uri'),'who')
    ok('can not' in pg.inner_text('#ask').lower() and 'logged in a session' in pg.inner_text('#ask'),'limits stated')
    pass
    with pg.expect_navigation(url='https://claude.ai/cb?code=1'): pg.click('#ok')
    ok(any(m=='POST' and u.endswith('/consent') for m,u in log),'consent posted')
    # reload now signed in (session persisted): goes straight to ask
    pg2=b.new_page()
    # 3 deny
    pg.goto('http://127.0.0.1:8765/consent.html?authorization_id=AID'); pg.wait_for_selector('#ask:not([hidden])')
    ok(pg.is_hidden('#login'),'session reused, no second sign-in')
    with pg.expect_navigation(url='https://claude.ai/cb?error=access_denied'): pg.click('#no')
    # 4 already consented -> redirect at once
    ctx=b.new_context(); pg3=ctx.new_page(); mk(pg3,already=True)
    pg3.goto('http://127.0.0.1:8765/consent.html'); pg3.evaluate("()=>0")
    ctx.close()
    # 5 bad password
    ctx=b.new_context(); pg4=ctx.new_page(); mk(pg4,bad=True)
    pg4.goto('http://127.0.0.1:8765/consent.html?authorization_id=AID'); pg4.wait_for_selector('#login:not([hidden])')
    pg4.fill('#em','a@b.nl'); pg4.fill('#pw','bad'); pg4.click('#login-go'); pg4.wait_for_selector('#login-err:not(:empty)')
    ok(pg4.is_hidden('#ask') and 'not right' in pg4.inner_text('#login-err') and not pg4.is_disabled('#login-go'),'bad password')
    ctx.close()
    # 6 invalid authorization after sign in
    ctx=b.new_context(); pg5=ctx.new_page(); mk(pg5,invalid=True)
    pg5.goto('http://127.0.0.1:8765/consent.html?authorization_id=AID'); pg5.wait_for_selector('#login:not([hidden])')
    pg5.fill('#em','a@b.nl'); pg5.fill('#pw','x'); pg5.click('#login-go'); pg5.wait_for_selector('#msg:has-text("not valid")')
    ok(pg5.is_hidden('#ask'),'invalid request')
    ctx.close()
    # 6b destination shown; unknown host warns and relabels the button
    ctx=b.new_context(); pg7=ctx.new_page(); errs=[]; pg7.on('console',lambda m: errs.append(m.text) if 'Content Security Policy' in m.text else None); mk(pg7)
    pg7.goto('http://127.0.0.1:8765/consent.html?authorization_id=AID'); pg7.wait_for_selector('#login:not([hidden])'); pg7.fill('#em','a@b.nl'); pg7.fill('#pw','x'); pg7.click('#login-go'); pg7.wait_for_selector('#ask:not([hidden])')
    ok('claude.ai is shown without a warning' and 'claude.ai' in pg7.inner_text('#dest') and 'not Claude' not in pg7.inner_text('#dest') and pg7.inner_text('#ok').lower()=='allow','known destination')
    ok(not errs,'consent page works under its security policy: %s' % errs)
    ctx.close()
    ctx=b.new_context(); pg8=ctx.new_page(); mk(pg8,dest='https://evil.example/cb')
    pg8.goto('http://127.0.0.1:8765/consent.html?authorization_id=AID'); pg8.wait_for_selector('#login:not([hidden])'); pg8.fill('#em','a@b.nl'); pg8.fill('#pw','x'); pg8.click('#login-go'); pg8.wait_for_selector('#ask:not([hidden])')
    ok('evil.example' in pg8.inner_text('#dest') and 'not Claude' in pg8.inner_text('#dest') and pg8.inner_text('#ok').lower()=='allow anyway' and 'warn' in (pg8.get_attribute('#dest','class') or ''),'unknown destination warns')
    ctx.close()
    # 6c the page can not be framed (click-jacking): inside a frame it stays hidden
    ctx=b.new_context(); pg9=ctx.new_page(); mk(pg9)
    pg9.route('http://127.0.0.1:8765/attacker.html',lambda r: r.fulfill(status=200,content_type='text/html',body='<iframe id=f sandbox="allow-scripts allow-same-origin" src="/consent.html?authorization_id=AID"></iframe>'))
    pg9.goto('http://127.0.0.1:8765/attacker.html'); fr=pg9.frame_locator('#f'); pg9.wait_for_timeout(1500)
    disp=[f for f in pg9.frames if 'consent.html' in f.url][0].evaluate("getComputedStyle(document.documentElement).display")
    ok(disp=='none','framed consent page stays hidden, got '+disp)
    ctx.close()
    # 7 already consented: signed-in, details carry redirect_url
    ctx=b.new_context(); pg6=ctx.new_page(); mk(pg6,already=True)
    pg6.goto('http://127.0.0.1:8765/consent.html?authorization_id=AID'); pg6.wait_for_selector('#login:not([hidden])')
    pg6.fill('#em','a@b.nl'); pg6.fill('#pw','x')
    with pg6.expect_navigation(url='https://claude.ai/cb?code=prev'): pg6.click('#login-go')
    ok(True,'already consented redirects')
    b.close()
print(n,'consent checks passed')
