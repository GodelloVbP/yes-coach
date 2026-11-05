"""The signed-out start page: header chip, hero, screenshots, feature cards, counter threshold; the changelog under More."""
import re, os, sys
from playwright.sync_api import sync_playwright
from signedout import *

with sync_playwright() as pw:
    # ---- signed out, phone
    br, pg, log = make(pw); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible'); pg.wait_for_timeout(600)
    ok(pg.is_visible('#hm-chip') and pg.is_visible('#hm-logo svg'), 'header: logo and language chip')
    ok(pg.locator('h1').filter(visible=True).count() == 1 and 'know what to lift next' in pg.inner_text('#h-home').lower(), 'hero: the headline names the benefit, and is the one h1')
    ok(pg.locator('.hm-tag').count() == 1 and pg.is_visible('.hm-tag') and 'reason' in pg.inner_text('.hm-tag'), 'hero: one subline about the suggested weight and its reason')
    ok(pg.evaluate("getComputedStyle(document.querySelector('.hm-h')).color") != 'rgb(255, 138, 101)', 'hero: the headline is not coral on white')
    ok(pg.evaluate("document.querySelector('#hm-signup').getBoundingClientRect().height") >= 64 and 'start tracking free' in pg.inner_text('#hm-signup').lower(), 'hero: the big button is Start tracking free, at least 64px tall')
    ok(pg.is_visible('#hm-demo') and 'sample workout' in pg.inner_text('#hm-demo').lower(), 'hero: a See a sample workout button')
    ok(pg.is_visible('#hm-login') and pg.evaluate("document.querySelector('#hm-login').closest('.hm-bar') !== null"), 'header: Sign in is a link in the header')
    ok('third part' not in pg.inner_text('#v-home').lower() and 'never sold' in pg.inner_text('#v-home').lower(), 'trust: no claim about third parties, and a precise one about selling')
    ok(pg.is_visible('.hm-import') and 'Strong' in pg.inner_text('.hm-import'), 'hero: the import line sits next to the buttons')
    ok(pg.locator('.hm-live .hm-pin').count() == 2 and pg.locator('.hm-legend li').count() == 2 and pg.locator('.hm-live img').get_attribute('alt'), 'hero: the log screenshot with two numbered notes and a legend')
    ok(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), 'phone: no sideways page scroll')
    imgs = pg.evaluate("[...document.querySelectorAll('.hm-shots img')].map(i => ({src: i.getAttribute('src'), alt: i.alt, w: i.naturalWidth}))")
    ok(len(imgs) == 2 and all(i['alt'].strip() for i in imgs), 'two more screenshots, each with alt text: %s' % imgs)
    for i in imgs:
        ok(i['src'].endswith('.webp') and not i['src'].startswith('http'), 'screenshot is self-hosted WebP: ' + i['src'])
        ok(os.path.getsize(ROOT + '/' + i['src']) < 80 * 1024, 'screenshot under 80 KB: %s %d' % (i['src'], os.path.getsize(ROOT + '/' + i['src'])))
    pg.locator('.hm-shots').scroll_into_view_if_needed()
    for k in range(2): pg.locator('.hm-shots img').nth(k).scroll_into_view_if_needed(); pg.wait_for_timeout(200)
    ok(pg.evaluate("[...document.querySelectorAll('.hm-live img, .hm-shots img')].every(i => i.complete && i.naturalWidth > 0)"), 'screenshots load under the CSP')
    titles = [t.lower() for t in pg.eval_on_selector_all('.hm-cards h3', 'els => els.map(e => e.textContent.trim())')]
    ok(len(titles) == 6 and titles[0].startswith('next weight') and 'history' in titles[1], 'six cards, the suggested weight first and the import second: %s' % titles)
    ok(titles.index('bring your own ai') > 2 and 'food and nutrients' == titles[-1], 'the AI card follows the core cards and food comes last: %s' % titles)
    ok(not pg.evaluate("[...document.querySelectorAll('.hm-cards li')].some(l => getComputedStyle(l, '::before').backgroundColor === 'rgb(255, 138, 101)')"), 'no card is coral: the one coral thing is the main button')
    last = pg.locator('.hm-final')
    ok(last.locator('[data-auth="up"]').is_visible() and last.locator('[data-demo]').is_visible() and 'easier to follow' in last.inner_text().lower(), 'the page ends with the same call to action')
    pg.click('#hm-login'); pg.wait_for_selector('#au-email', state='visible')
    ok('sign in' in pg.inner_text('#au-h').lower(), 'the header link opens the sign-in form')
    pg.click('#au-back'); pg.wait_for_selector('#hm-signup', state='visible')
    pg.click('#hm-signup'); pg.wait_for_selector('#au-email', state='visible')
    ok('create your account' in pg.inner_text('#au-h').lower(), 'Start tracking free opens the sign-up form')
    pg.click('#au-back'); pg.wait_for_selector('#hm-signup', state='visible')
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

    # ---- every new line of the start page has a translation in all five languages
    EN = {'#h-home': 'Know what to lift next.', '.hm-kick': 'Free strength-training tracker', '.hm-tag': None, '#hm-signup': 'Start tracking free', '#hm-demo': 'See a sample workout', '.hm-trust': None, '.hm-import': None,
          '.hm-legend li:nth-child(1)': 'The next weight, with the reason.', '.hm-legend li:nth-child(2)': "Last time's numbers beside each set.", '.hm-cards li:nth-child(5) h3': 'Bring your own AI', '.hm-cards li:nth-child(5) p': None, '.hm-final h2': 'Make your next workout easier to follow.',
          '.hm-checks li:nth-child(4)': 'Your data is never sold or used for advertising.', '.hm-checks li:nth-child(5)': 'Optional AI connections only with your permission.'}
    for lang in ('nl', 'de', 'fr', 'es', 'it'):
        br, pg, log = make(pw); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible')
        pg.evaluate("localStorage.setItem('yc-lang', '%s')" % lang); pg.reload(); pg.wait_for_selector('#hm-signup', state='visible'); pg.wait_for_timeout(500)
        same = [sel for sel, en in EN.items() if (pg.inner_text(sel).strip().lower() == en.lower() if en else pg.inner_text(sel).strip() == '')]
        english = [sel for sel in ('.hm-tag', '.hm-trust', '.hm-import', '.hm-cards li:nth-child(5) p') if pg.inner_text(sel).startswith(('Log your', 'Free. No', 'Already', 'Already use'))]
        ok(not same and not english, '%s: the start page is translated, still English: %s %s' % (lang, same, english))
        br.close()

    # ---- desktop
    br, pg, log = make(pw); pg.set_viewport_size({'width': 1280, 'height': 860}); pg.goto(BASE); pg.wait_for_selector('#hm-login', state='visible'); pg.wait_for_timeout(600)
    copy, live = pg.evaluate("[...document.querySelectorAll('.hm-copy, .hm-live')].map(e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; })")
    ok(live[0] >= copy[0] + copy[2] and live[1] < copy[1] + copy[3] and live[1] + live[3] > copy[1], 'desktop: the hero is split, the text left and the real screenshot right: %s %s' % (copy, live))
    ok(pg.evaluate("document.querySelector('#hm-signup').getBoundingClientRect().bottom") < 860, 'desktop: the main button is on the first screen')
    xs = pg.evaluate("[...document.querySelectorAll('.hm-shots li')].map(l => Math.round(l.getBoundingClientRect().x))")
    ok(len(set(xs)) == 2, 'desktop: two more screenshots side by side: %s' % xs)
    ys = pg.evaluate("[...document.querySelectorAll('.hm-cards li')].map(l => Math.round(l.getBoundingClientRect().y))")
    ok(len(set(ys)) == 2, 'desktop: cards in two rows of three: %s' % ys)
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
print(passed(), 'landing checks passed')
