"""Units and labels built from pieces in code are translated: the unit words come from the dictionary, also next to numbers, and a pattern's tail is translated piece by piece."""
import subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

T = datetime.date.today().isoformat(); PAST = (datetime.date.today() - datetime.timedelta(days=4)).isoformat()
wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][datetime.date.today().weekday()]
def ex(name, unit, group, **kw): return dict({'name': name, 'group': group, 'category': 'strength', 'unit': unit, 'better': 'lower' if unit == 'assist' else 'higher'}, **kw)
def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True, 'nutrition': {'kcal': 2000, 'protein': 120}}})
    exs = [('bench', 'Bench press', 'kg', 'Chest', {'load_basis': 'per_side'}), ('legpress', 'Leg press', 'stack', 'Legs', {}), ('dip', 'Assisted dip', 'assist', 'Chest', {})]
    for i, n, u, g, kw in exs: be.docs.append({'path': 'yc/exercises/' + i, 'data': ex(n, u, g, **kw)})
    items = [{'ex': i, 'order': k + 1, 'sets': 2, 'reps': '8', 'target': '', 'target_at': T, 'rest_s': 90, 'note': None} for k, (i, _, _, _, _) in enumerate(exs)]
    be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'weekday': wd, 'items': items}})
    sets = {'%s_%d' % (i, n): {'ex': i, 'n': n, 'kind': 'work', 'reps': 8, 'load': 40, 'done': True, 'at': n} for i, _, _, _, _ in exs for n in (1, 2)}
    be.docs.append({'path': 'yc/sessions/' + PAST, 'data': {'date': PAST, 'template': 'push', 'finished_at': 1, 'sets': sets}})
    be.docs.append({'path': 'yc/food/' + T, 'data': {'date': T, 'entries': {'a': {'name': 'Appel', 'p': 0.3, 'c': 14, 'f': 0.2, 'kcal': 62, 'at': 1}}}})

# (language, English text, a part that must be in the translation, or None for "left exactly as it is")
CASES = [
    ('fr', '120 g left', 'restants'), ('fr', '1,938 kcal left', 'restantes'), ('de', '120 g left', 'übrig'), ('nl', '120 g left', 'over'),
    ('fr', '40 pin × 8', 'cran × 8'), ('es', '40 pin × 8', 'clavija × 8'),
    ('de', '40 kg assist × 8', 'Unterstützung × 8'), ('nl', '40 kg assist × 8', 'assistentie × 8'), ('es', '40 kg assist × 8', 'asistencia × 8'), ('it', '40 kg assist × 8', 'assistenza × 8'),
    ('fr', '40 kg/side × 8', 'côté × 8'), ('de', '40 kg/side × 8', 'Seite × 8'),
    ('nl', 'Target · Last time', 'Doel · Vorige keer'), ('nl', 'Target · Last time · Your note', 'Doel · Vorige keer · Jouw notitie'), ('fr', 'Target · Last time', 'Objectif · Dernière fois'),
    ('nl', '· 1 session', '· 1 training'), ('nl', '· 3 sessions', '· 3 trainingen'), ('fr', '· 2 sessions', '· 2 séances'),
    ('fr', 'Each day you logged, in the past month.', 'Chaque jour enregistré, sur le dernier mois.'), ('nl', 'Each day you logged, in the past 3 months.', 'in de afgelopen 3 maanden'), ('de', 'Each day you logged, in all your history.', 'in deinem gesamten Verlauf'), ('it', 'Average per logged day, by week, in the past 6 months.', 'Media per giorno registrato, per settimana: '),
    ('fr', 'Add your age, height and weight', 'âge, taille et poids'), ('de', 'Add your height and weight', 'Größe und Gewicht'),
    ('nl', '8 reps', '8 herhalingen'),
    # words that look like units but are ordinary text are left alone
    ('fr', 'Pin this page to the top', None), ('fr', '40 pin × 8 and some more words', None), ('de', '40 × 8', None),
]
server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        for lang in ('fr', 'nl', 'de', 'es', 'it'):
            be = Backend(); seed(be)
            def sc(page, lang=lang):
                page.wait_for_selector('#v-train', state='visible'); page.wait_for_timeout(300)
                for l, s, want in CASES:
                    if l != lang: continue
                    got = page.evaluate("(s) => window.YC_I18N.t(s)", s)
                    if want is None: check('%s: "%s" is left alone' % (l, s), got is None or got == s, got)
                    else: check('%s: "%s" -> %s' % (l, s, want), got is not None and want in got, got)
            errs = session(pw, be, ALICE, sc, width=390, lang=lang); check('no page errors (%s)' % lang, not errs, errs)

        # ---- on the real screens, in French: no English units left on Progress and Food, and the week
        be = Backend(); seed(be)
        def screens(page):
            page.wait_for_selector('#v-train', state='visible'); page.wait_for_timeout(500)
            check('the week says aujourd’hui, not today', 'today' not in page.inner_text('#v-train').lower().replace('aujourd’hui', ''), page.inner_text('#v-train')[:300])
            page.click('#tab-progress'); page.wait_for_timeout(900)
            t = page.inner_text('#v-progress')
            check('Progress: no English units next to the numbers', not any(x in t for x in (' kg assist ×', ' pin ×', 'kg/side ×', ' session')), [l for l in t.split('\n') if '×' in l or 'session' in l][:6])
            check('Progress: the units are in French', 'cran × 8' in t and '· 1 séance' in t, [l for l in t.split('\n') if '×' in l][:6])
            page.click('#tab-food'); page.wait_for_timeout(700)
            t = page.inner_text('#v-food')
            check('Food: what is left is in French', ' left' not in t and ('restants' in t or 'restantes' in t), t[:400])
            check('Food: the chart note is in French', 'Each day you logged' not in t and 'sur le dernier mois' in t, t[-400:])
        errs = session(pw, be, ALICE, screens, width=390, lang='fr'); check('no page errors (French screens)', not errs, errs)
        check('no outside requests', not EXTERNAL, EXTERNAL)
finally:
    server.terminate()
done()
