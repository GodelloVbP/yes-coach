"""Translate exercise names: off by default (most people know an exercise by its English name), a switch under Languages, kept on this device."""
import subprocess, time, json
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL


NAMES = ['Pull-up', 'Barbell bench press', 'My own move']
def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for i, n in enumerate(NAMES):
        be.docs.append({'path': 'yc/exercises/x%d' % i, 'data': {'name': n, 'group': 'Back', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    import datetime
    T = datetime.date.today().isoformat(); wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Back', 'weekday': wd,
        'items': [{'ex': 'x%d' % i, 'order': i + 1, 'sets': 2, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None} for i in range(len(NAMES))]}})
def exercise_text(page):
    # the names as they show while training
    if not page.is_visible('#session'):
        if page.is_visible('#resume-btn'): page.click('#resume-btn')
        else:
            page.locator('#v-train button:visible', has_text='Push day').first.click(); page.wait_for_timeout(300)
            if not page.is_visible('#session'): page.locator('#v-train button.skew:visible').first.click()
    page.wait_for_selector('#session', state='visible'); page.wait_for_timeout(500)
    t = page.inner_text('#session'); page.click('#sb-back'); page.wait_for_timeout(400)
    return t
def open_settings(page):
    page.click('#tab-settings'); page.wait_for_selector('#lang', state='visible'); page.wait_for_timeout(300)
    if not page.is_visible('#lang-body'):   # the sections in Settings open and close
        page.locator('#lang button').first.click(); page.wait_for_selector('#lang-body', state='visible')
def back_in(page):
    # after a reload the harness' #home hash shows Home first: step into the app again
    page.wait_for_selector('#v-home, #v-train', state='visible')
    if page.is_visible('#v-home'):
        try: page.click('#hm-train', timeout=4000)
        except Exception: pass
    page.wait_for_selector('#v-train', state='visible'); page.wait_for_timeout(500)

# the dictionary files carry the names to leave alone
for code in ('nl', 'es', 'de', 'fr', 'it'):
    d = json.load(open('%s/i18n/%s.json' % (REPO, code)))
    nm = d.get('__names', [])
    check('%s: the dictionary lists the library names (not the one that is also a screen label)' % code, len(nm) == 303 and 'Pull-up' in nm and 'Cable Y-raise' not in nm and all(isinstance(x, str) for x in nm), len(nm))

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- French: English names by default, the rest of the screen translated
        be = Backend(); seed(be)
        def fr(page):
            page.wait_for_selector('#v-train', state='visible'); page.wait_for_timeout(500)
            t = page.evaluate
            check('by default exercise names are not translated', t("window.YC_I18N.t('Barbell bench press')") is None and t("window.YC_I18N.t('Pull-up')") is None)
            check('the rest of the interface still is', t("window.YC_I18N.t('Chest')") == 'Pectoraux' and 'entraînement' in page.inner_text('#tabs-nav').lower(), page.inner_text('#tabs-nav'))
            check('the switch is off', t("window.YC_I18N.exercises()") is False)
            txt = exercise_text(page)
            check('your exercises show their English names', 'pull-up' in txt.lower() and 'barbell bench press' in txt.lower() and 'my own move' in txt.lower() and 'traction' not in txt.lower() and 'développé couché à la barre' not in txt.lower(), txt[:300])
            open_settings(page); page.locator('#lang-ex').scroll_into_view_if_needed()
            check('Settings shows the switch, in French, off', vis(page, '#lang-ex') and not page.is_checked('#lang-ex') and 'Traduire les noms des exercices' in page.inner_text('#lang-ex-row'), page.inner_text('#lang-ex-row'))
            # switch it on: the page reloads and the names are French
            with page.expect_navigation(): page.click('#lang-ex')
            back_in(page)
            check('it is kept on this device', page.evaluate("localStorage.getItem('yc-lang-ex')") == '1' and page.evaluate("window.YC_I18N.exercises()") is True)
            check('and now names are translated', page.evaluate("window.YC_I18N.t('Barbell bench press')") == 'Développé couché à la barre' and page.evaluate("window.YC_I18N.t('Pull-up')") == 'Traction')
            txt = exercise_text(page)
            check('your exercises show French names, your own stays as you wrote it', 'traction' in txt.lower() and 'développé couché à la barre' in txt.lower() and 'my own move' in txt.lower(), txt[:300])
            open_settings(page); page.locator('#lang-ex').scroll_into_view_if_needed()
            check('the switch is on', page.is_checked('#lang-ex'))
            with page.expect_navigation(): page.click('#lang-ex')
            back_in(page)
            check('switched off again: English names, kept', page.evaluate("localStorage.getItem('yc-lang-ex')") == '0' and page.evaluate("window.YC_I18N.t('Pull-up')") is None)
            check('no horizontal overflow on a phone', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        errs = session(pw, be, ALICE, fr, width=390, lang='fr'); check('no page errors (French)', not errs, errs)

        # ---- Dutch: the same, and a library name that Dutch does translate
        be = Backend(); seed(be)
        def nl(page):
            page.wait_for_selector('#v-train', state='visible'); page.wait_for_timeout(500)
            check('nl: off by default', page.evaluate("window.YC_I18N.t('Barbell bench press')") is None and page.evaluate("window.YC_I18N.t('Chest')") == 'Borst')
            page.evaluate("localStorage.setItem('yc-lang-ex', '1')"); page.reload(); back_in(page)
            check('nl: on gives the Dutch name', page.evaluate("window.YC_I18N.t('Barbell bench press')") == 'Bankdrukken met barbell')
        errs = session(pw, be, ALICE, nl, width=390, lang='nl'); check('no page errors (Dutch)', not errs, errs)

        # ---- English: nothing to switch
        be = Backend(); seed(be)
        def en(page):
            page.wait_for_selector('#v-train', state='visible'); page.wait_for_timeout(300)
            open_settings(page); page.wait_for_selector('#lang', state='visible')
            check('in English the switch is not shown', not vis(page, '#lang-ex-row'))
        errs = session(pw, be, ALICE, en, width=390, lang='en'); check('no page errors (English)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
