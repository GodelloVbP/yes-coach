"""The sample workout (?demo): opens from the start page with a plan and two earlier sessions, shows the suggested next weight,
lets you log a set, and writes nothing: no database call, nothing on the device. "Create an account" leads to the sign-up form."""
from playwright.sync_api import sync_playwright
from signedout import *

with sync_playwright() as pw:
    # ---- from the start page into the sample
    br, pg, log = make(pw); pg.goto(BASE); pg.wait_for_selector('#hm-demo', state='visible')
    pg.click('#hm-demo'); pg.wait_for_selector('#demo-bar', state='visible'); pg.wait_for_selector('text=Start Push day')
    ok('Nothing here is saved' in pg.inner_text('#demo-bar'), 'a bar says it is a sample and nothing is saved')
    ok(pg.is_hidden('#hm-login') and pg.is_hidden('#au-email'), 'no sign-in form in the sample')
    pg.click('text=Start Push day'); pg.wait_for_selector('#f-barbell-bench-press_1-load', state='visible'); pg.wait_for_timeout(400)
    ok(pg.input_value('#f-barbell-bench-press_1-load') == '82.5', 'bench is prefilled with the suggested weight: %s' % pg.input_value('#f-barbell-bench-press_1-load'))
    why = pg.locator('.ex:not(.off) .ex-sug').first.text_content().strip()
    ok(why.startswith('+2.5 kg: all 3 sets reached 8'), 'the reason for the suggestion is shown: %s' % why)
    ok('8 @ 80' in pg.inner_text('.set:has(#f-barbell-bench-press_1-load)').replace('\n', ' ') or '80' in pg.inner_text('.ex:not(.off)'), 'last time is shown beside the sets')
    pg.locator('.set:has(#f-barbell-bench-press_1-load) .set-tick').click(); pg.wait_for_timeout(300)
    ok(pg.get_attribute('.set:has(#f-barbell-bench-press_1-load) .set-tick', 'aria-pressed') == 'true', 'a set can be ticked')
    pg.reload(); pg.wait_for_selector('#demo-bar', state='visible'); pg.wait_for_selector('text=Start Push day')
    ok(pg.locator('#f-barbell-bench-press_1-load').count() == 0, 'a reload starts the sample over: nothing was kept')
    ok(not log['rest'] and not [a for a in log['auth'] if a[0].startswith(('/auth/v1/token', '/auth/v1/signup'))], 'no database or sign-in call: %s %s' % (log['rest'], log['auth']))
    keys = pg.evaluate("Object.keys(localStorage).filter(k => k.startsWith('yc-') && k !== 'yc-lang' && k !== 'yc-theme')")
    ok(not keys, 'nothing of the sample stays on the device: %s' % keys)
    ok(not log['errors'] and not log['other'], 'no errors, nothing leaves the site: %s %s' % (log['errors'], log['other']))
    # ---- on to a real account
    pg.click('#demo-bar button'); pg.wait_for_selector('#au-email', state='visible')
    ok('create your account' in pg.inner_text('#au-h').lower(), 'Create an account opens the sign-up form: %s' % pg.inner_text('#au-h'))
    br.close()
    # ---- someone who is signed in never lands in the sample
    br, pg, log = make(pw, signed_in=True); pg.goto(BASE + 'index.html?demo'); pg.wait_for_selector('#v-train:not([hidden]), #v-home:not([hidden])'); pg.wait_for_timeout(500)
    ok(pg.locator('#demo-bar').count() == 0, 'a signed-in browser ignores ?demo')
    br.close()
print(passed(), 'demo checks passed'); srv.shutdown()
