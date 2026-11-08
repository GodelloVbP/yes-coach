"""The signed-out start page: header chip, hero, screenshots, feature cards, counter threshold; the changelog under More."""
import re, os, sys
src = open(str(__import__('pathlib').Path(__file__).resolve().parent / 'e2e_captcha.py')).read().split('def until(pg')[0]
__file__ = str(__import__('pathlib').Path(__file__).resolve().parent / 'e2e_captcha.py')
exec(src)

def until(pg, expr, timeout=8000):
    for _ in range(timeout // 100):
        if pg.evaluate(expr): return
        pg.wait_for_timeout(100)
    raise AssertionError('timeout: ' + expr)

with sync_playwright() as pw:
    # ---- signed out, phone
    br, pg, log = make(pw); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible'); pg.wait_for_timeout(600)
    ok(pg.is_visible('#hm-chip') and pg.is_visible('#hm-logo svg'), 'header: logo and language chip')
    ok(pg.locator('.hm-h span').count() == 3, 'hero: a three-line headline')
    ok(pg.locator('.hm-tag').count() == 1 and pg.is_visible('.hm-tag'), 'hero: one subline')
    ok(pg.evaluate("document.querySelector('#hm-login').getBoundingClientRect().height") >= 64, 'hero: Sign in is at least 64px tall')
    ok(pg.is_visible('#hm-signup') and 'create an account' in pg.inner_text('#hm-signup').lower(), 'hero: Create an account')
    ok(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), 'phone: no sideways page scroll')
    imgs = pg.evaluate("[...document.querySelectorAll('.hm-shots img')].map(i => ({src: i.getAttribute('src'), alt: i.alt, w: i.naturalWidth}))")
    ok(len(imgs) == 3 and all(i['alt'].strip() for i in imgs), 'three screenshots, each with alt text: %s' % imgs)
    for i in imgs:
        ok(i['src'].endswith('.webp') and not i['src'].startswith('http'), 'screenshot is self-hosted WebP: ' + i['src'])
        ok(os.path.getsize(ROOT + '/' + i['src']) < 80 * 1024, 'screenshot under 80 KB: %s %d' % (i['src'], os.path.getsize(ROOT + '/' + i['src'])))
    pg.locator('.hm-shots').scroll_into_view_if_needed()
    for k in range(3): pg.locator('.hm-shots img').nth(k).scroll_into_view_if_needed(); pg.wait_for_timeout(200)
    ok(pg.evaluate("[...document.querySelectorAll('.hm-shots img')].every(i => i.complete && i.naturalWidth > 0)"), 'screenshots load under the CSP')
    ok(pg.locator('.hm-cards li').count() == 3 and [x.lower() for x in pg.locator('.hm-cards h3').all_text_contents()] == ['suggested weights', 'use your own ai', 'import your history'], 'three cards, in order: ' + str(pg.locator('.hm-cards h3').all_text_contents()))
    GRID = "(() => { const c = document.querySelector('.hm-cards'); const t = getComputedStyle(c).gridTemplateColumns.split(' ').length; const x = [...c.children].map(li => Math.round(li.getBoundingClientRect().left)); const fills = [...c.children].map(li => getComputedStyle(li).getPropertyValue('--ang-bg').trim()); return { tracks: t, lefts: x, fills, over: document.documentElement.scrollWidth > window.innerWidth }; })()"
    g = pg.evaluate(GRID)
    ok(g['tracks'] == 1 and len(set(g['lefts'])) == 1 and not g['over'], 'phone: the three cards stack in one column: %s' % g)
    ok(len(set(g['fills'])) == 1 and 'pop' not in g['fills'][0], 'all three cards share the faint fill, none is coral: %s' % g['fills'])
    pg.set_viewport_size({'width': 1280, 'height': 900}); pg.wait_for_timeout(200)
    g = pg.evaluate(GRID)
    ok(g['tracks'] == 3 and len(set(g['lefts'])) == 3 and not g['over'], 'desktop: three equal columns, no empty track: %s' % g)
    pg.set_viewport_size({'width': 390, 'height': 844}); pg.wait_for_timeout(200)
    ok('Privacy page' in pg.inner_text('#v-home') and pg.is_visible('#hm-install'), 'privacy link and home screen button')
    ok(pg.locator('#changelog').count() == 1 and pg.locator('#v-home #changelog').count() == 0, 'the changelog is not on the start page')
    ok("what's new" not in pg.inner_text('#v-home').lower(), "signed out: no What's new on the start page")
    ok(pg.is_hidden('#hm-users'), 'counter hidden below 100')
    ok(not log['errors'] and not log['other'], 'no errors, no outside requests: %s %s' % (log['errors'], log['other']))
    br.close()

    # ---- the threshold is read from config.js
    br, pg, log = make(pw, users=7)
    pg.route(BASE + 'config.js', lambda r: r.fulfill(status=200, content_type='application/javascript', body=open(ROOT + '/config.js').read().replace('userCounterMin: 100', 'userCounterMin: 5')))
    pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible')
    until(pg, "document.querySelector('#hm-users').hidden === false")
    ok('7' in pg.inner_text('#hm-users'), 'counter shows once the count reaches the config threshold')
    br.close()
    br, pg, log = make(pw, users=99); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible'); pg.wait_for_timeout(900)
    ok(pg.is_hidden('#hm-users'), '99 is still hidden')
    br.close()
    br, pg, log = make(pw, users=100); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible')
    until(pg, "document.querySelector('#hm-users').hidden === false")
    ok('100' in pg.inner_text('#hm-users'), '100 shows')
    br.close()

    # ---- desktop
    br, pg, log = make(pw); pg.set_viewport_size({'width': 1280, 'height': 860}); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible'); pg.wait_for_timeout(600)
    xs = pg.evaluate("[...document.querySelectorAll('.hm-shots li')].map(l => Math.round(l.getBoundingClientRect().x))")
    ok(len(set(xs)) == 3, 'desktop: three screenshots side by side: %s' % xs)
    ys = pg.evaluate("[...document.querySelectorAll('.hm-cards li')].map(l => Math.round(l.getBoundingClientRect().y))")
    ok(len(set(ys)) == 1, 'desktop: the three cards sit in one row: %s' % ys)
    ok(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), 'desktop: no sideways page scroll')
    br.close()

    # ---- signed in: the changelog lives under More
    br, pg, log = make(pw, signed_in=True); pg.goto(BASE); pg.wait_for_timeout(1500)
    pg.click('#tab-settings'); pg.wait_for_selector('#more-news', state='visible')
    pg.click('#more-news'); pg.wait_for_selector('#v-news', state='visible')
    ok(pg.locator('#changelog .cl-item').count() > 5, 'More > What\'s new lists the changes')
    ok('New start page' in pg.text_content('#changelog'), 'the newest entry is there')
    ok(pg.get_attribute('#tab-settings', 'class').find('in-more') >= 0, 'the More tab stays marked')
    pg.click('#news-back'); pg.wait_for_selector('#v-settings', state='visible')
    ok(pg.is_hidden('#v-news'), 'back returns to More')
    pg.click('#mark'); pg.wait_for_selector('#v-home', state='visible'); pg.wait_for_timeout(500)
    ok(pg.is_hidden('#hm-chip') and pg.is_hidden('#hm-login'), 'signed in: no header chip and no sign-in on Home')
    ok(not log['errors'] and not log['other'], 'signed in: no errors: %s %s' % (log['errors'], log['other']))
    br.close()
print(n, 'landing checks passed')
