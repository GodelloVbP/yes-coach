"""Imports keep the measure of the file, and two copies of one exercise can be merged."""
import re, subprocess, time, datetime
from playwright.sync_api import sync_playwright
from harness import *

SAT = datetime.datetime(2026, 11, 7, 10, 0)
TODAY = SAT.date().isoformat()
def doc(be, path): return next((d['data'] for d in be.docs if d['path'] == path), None)
def under(be, prefix): return [d for d in be.docs if d['path'].startswith(prefix)]

HEAD = '"title","start_time","end_time","description","exercise_title","superset_id","exercise_notes","set_index","set_type","weight_kg","reps","distance_km","duration_seconds","rpe"'
def csv(*names):
    rows = [HEAD]
    for day in ('5', '12'):
        when = '"%s Oct 2026, 18:00"' % day
        for nm in names:
            for k in range(3):
                rows.append(','.join(['"Legs"', when, when, '""', '"%s"' % nm, '""', '""', str(k), '"normal"', '25', '10', '""', '""', '""']))
    return '\n'.join(rows)

def import_history(page, text):
    until(lambda: page.is_visible('#wz-import')); page.click('#wz-import')
    page.get_by_role('radiogroup', name='Coming from').get_by_role('radio', name='Hevy').click()
    page.set_input_files('#wz-file', files=[{'name': 'w.csv', 'mimeType': 'text/csv', 'buffer': text.encode()}])
    until(lambda: 'w.csv' in page.text_content('#wiz'))
    page.click('#wz-history')

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. an import keeps kg, also for a machine
        be = Backend()
        def s1(page):
            import_history(page, csv('Leg Extension (Machine)', 'Squat (Barbell)'))
            check('import: both sessions are written', until(lambda: len(under(be, 'yc/sessions/')) == 2))
            ex = {d['path'].split('/')[-1]: d['data'] for d in under(be, 'yc/exercises/')}
            check('import: a machine exercise is counted in kg, as the file has it', ex.get('leg-extension', {}).get('unit') == 'kg' and ex['leg-extension'].get('library_id') == 'l45', ex)
            units = {st['unit'] for d in under(be, 'yc/sessions/') for st in d['data']['sets'].values()}
            check('import: the sets are stored as kg', units == {'kg:total'}, units)
        errs = session(pw, be, ALICE, s1, width=390, clock=SAT); check('no page errors (import)', not errs, errs)

        # ---- 2. a library exercise you already have, with no logged sets, is switched to kg so the history shows
        be = Backend()
        be.docs.append({'path': 'yc/exercises/leg-extension', 'data': {'name': 'Leg extension', 'group': 'Legs', 'category': 'strength', 'unit': 'stack', 'better': 'higher', 'library_id': 'l45', 'rest_s': 75}})
        def s2(page):
            import_history(page, csv('Leg Extension (Machine)'))
            check('import: your empty pin exercise becomes kg', until(lambda: (doc(be, 'yc/exercises/leg-extension') or {}).get('unit') == 'kg'), doc(be, 'yc/exercises/leg-extension'))
            check('import: and the history lands on it, no second exercise', until(lambda: len(under(be, 'yc/sessions/')) == 2) and len(under(be, 'yc/exercises/')) == 1 and all(st['ex'] == 'leg-extension' for d in under(be, 'yc/sessions/') for st in d['data']['sets'].values()))
        errs = session(pw, be, ALICE, s2, width=390, clock=SAT); check('no page errors (empty pin)', not errs, errs)

        # ---- 3. merging two copies
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        be.docs.append({'path': 'yc/exercises/imp-leg-extension-machine', 'data': {'name': 'Leg Extension (Machine)', 'group': 'Legs', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        be.docs.append({'path': 'yc/exercises/leg-extension', 'data': {'name': 'Leg extension', 'group': 'Legs', 'category': 'strength', 'unit': 'stack', 'better': 'higher', 'library_id': 'l45', 'rest_s': 75}})
        be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        be.docs.append({'path': 'yc/templates/legs', 'data': {'name': 'Legs', 'order': 1, 'kind': 'Legs', 'focus': '', 'items': [
            {'ex': 'leg-extension', 'order': 1, 'sets': 3, 'reps': '10', 'target': '', 'target_at': TODAY, 'rest_s': 75, 'note': None},
            {'ex': 'imp-leg-extension-machine', 'order': 2, 'sets': 3, 'reps': '10', 'target': '', 'target_at': TODAY, 'rest_s': 75, 'note': None},
            {'ex': 'bench', 'order': 3, 'sets': 3, 'reps': '8', 'target': '', 'target_at': TODAY, 'rest_s': 90, 'note': None}]}})
        kg = lambda ex, n: {'ex': ex, 'n': n, 'order': n, 'kind': 'work', 'reps': 10, 'load': 25, 'rir': None, 'note': None, 'done': True, 'at': 0, 'ticked_at': 0, 'unit': 'kg:total'}
        for day in ('2026-10-05', '2026-10-12'):
            be.docs.append({'path': 'yc/sessions/' + day, 'data': {'date': day, 'source': 'import', 'template': None, 'split': 'Legs', 'label': 'Imported', 'note': None, 'started_at': 0, 'sets': {'imp-leg-extension-machine_%d' % n: kg('imp-leg-extension-machine', n) for n in (1, 2, 3)}}})
        be.docs.append({'path': 'yc/sessions/2026-11-05', 'data': {'date': '2026-11-05', 'template': 'legs', 'split': 'Legs', 'label': 'Legs', 'note': None, 'started_at': 1, 'finished_at': 2, 'sets': {
            'leg-extension_1': {'ex': 'leg-extension', 'n': 1, 'order': 1, 'kind': 'work', 'reps': 15, 'load': 25, 'rir': None, 'note': None, 'done': True, 'at': 1, 'ticked_at': 1, 'unit': 'stack:'},
            'bench_1': {'ex': 'bench', 'n': 1, 'order': 2, 'kind': 'work', 'reps': 8, 'load': 60, 'rir': None, 'note': None, 'done': True, 'at': 1, 'ticked_at': 1, 'unit': 'kg:total'}}}})
        be.docs.append({'path': 'yc/notes/2026-11-05_imp-leg-extension-machine', 'data': {'text': 'seat on 4', 'about': 'imp-leg-extension-machine', 'about_label': 'Leg Extension (Machine)', 'date': '2026-11-05', 'at': 'x', 'status': 'new'}})
        def s3(page):
            page.wait_for_selector('#tab-exercises', state='attached')
            page.evaluate("document.querySelector('#tab-exercises').click()"); page.wait_for_selector('#xl-list .xl-row', timeout=8000)
            page.fill('#xl-search', 'leg extension'); page.wait_for_timeout(300)
            rows = page.locator('#xl-list .xl-row:visible')
            names = rows.all_inner_texts()
            check('the two copies show as one row, with both counted', any(t.upper().startswith('LEG EXTENSION') and '3 workouts' in t for t in names), names)
            rows.filter(has_text='Leg extension').first.click()
            check('it says they look like the same exercise', until(lambda: 'Leg Extension (Machine), which looks like the same exercise' in page.text_content('#xl-list')), page.text_content('#xl-list')[:300])
            page.click('#xl-merge-open')
            check('the other copy is preselected', page.eval_on_selector('#xl-merge-from', 'e => e.value') == 'imp-leg-extension-machine')
            check('kg is preselected, because most sets were logged in it', page.eval_on_selector('#xl-merge-measure', 'e => e.value') == 'kg:total')
            page.click('#xl-merge-go')
            check('it asks first and says what happens', until(lambda: page.is_visible('#xl-merge-yes')) and 'cannot be undone' in page.text_content('#xl-list'))
            page.click('#xl-merge-yes')
            check('the duplicate is gone', until(lambda: doc(be, 'yc/exercises/imp-leg-extension-machine') is None))
            ex = doc(be, 'yc/exercises/leg-extension')
            check('the kept exercise is counted in kg', ex['unit'] == 'kg' and ex.get('library_id') == 'l45', ex)
            old = [st for d in under(be, 'yc/sessions/') for st in d['data']['sets'].values() if st['ex'] == 'imp-leg-extension-machine']
            check('no set points at the old exercise', not old, old)
            mine = {d['path'].split('/')[-1]: sorted(st['n'] for st in d['data']['sets'].values() if st['ex'] == 'leg-extension') for d in under(be, 'yc/sessions/')}
            check('the imported sets moved, numbered after the existing ones', mine['2026-10-05'] == [1, 2, 3] and mine['2026-10-12'] == [1, 2, 3] and mine['2026-11-05'] == [1], mine)
            kept = doc(be, 'yc/sessions/2026-11-05')['sets']['leg-extension_1']
            check('a pin set keeps its own measure, so it is not mixed into the kg trend', kept['unit'] == 'stack:' and kept['reps'] == 15)
            items = [it['ex'] for it in doc(be, 'yc/templates/legs')['items']]
            check('the training day lists it once, in order', items == ['leg-extension', 'bench'] and [it['order'] for it in doc(be, 'yc/templates/legs')['items']] == [1, 2], items)
            note = doc(be, 'yc/notes/2026-11-05_leg-extension')
            check('the note moved with it', note and note['about'] == 'leg-extension' and note['text'] == 'seat on 4' and doc(be, 'yc/notes/2026-11-05_imp-leg-extension-machine') is None, note)
            # the history now shows as Previous in a workout
            page.click('#tab-train'); page.wait_for_selector('#btn-start', timeout=8000)
        errs = session(pw, be, ALICE, s3, width=390, clock=SAT); check('no page errors (merge)', not errs, errs)

        # ---- 4. Previous shows after the merge
        def s4(page):
            page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start')
            page.wait_for_selector('.set', timeout=8000); page.wait_for_timeout(500)
            first = page.evaluate("document.querySelector('.set').innerText.replace(/\\s+/g, ' ').trim()")
            check('the first workout after the merge shows the old weights as Previous', '10 @ 25' in first, first)
        errs = session(pw, be, ALICE, s4, width=390, clock=SAT); check('no page errors (previous)', not errs, errs)

        # ---- 5. the pin note and a blocked merge
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        be.docs.append({'path': 'yc/exercises/a', 'data': {'name': 'Row', 'group': 'Back', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        def s5(page):
            page.evaluate("document.querySelector('#tab-exercises').click()"); page.wait_for_selector('#xl-new', timeout=8000)
            page.click('#xl-new'); page.select_option('#xl-f-unit', 'stack')
            check('choosing pin says what pin is', 'not kg' in page.inner_text('#xl-unit-note') and page.is_visible('#xl-unit-note'), page.inner_text('#xl-unit-note'))
            page.select_option('#xl-f-unit', 'kg')
            check('and the note goes away for kg', not page.is_visible('#xl-unit-note'))
            page.fill('#xl-search', 'row'); page.wait_for_timeout(200)
            page.locator('#xl-list .xl-row:visible').filter(has_text='Row').first.click()
            check('a lone exercise has nothing to merge into', page.locator('#xl-merge-open').count() == 0)
        errs = session(pw, be, ALICE, s5, width=390, clock=SAT); check('no page errors (pin note)', not errs, errs)

        # ---- 6. the confirmation is translated, with the exercise names kept as they are
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        be.docs.append({'path': 'yc/exercises/a', 'data': {'name': 'Zottman curl', 'group': 'Arms', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        be.docs.append({'path': 'yc/exercises/b', 'data': {'name': 'Zottman curls', 'group': 'Arms', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        def s6(page):
            page.evaluate("document.querySelector('#tab-exercises').click()"); page.wait_for_selector('#xl-list .xl-row', timeout=8000)
            page.fill('#xl-search', 'zottman'); page.wait_for_timeout(300)
            page.locator('#xl-list .xl-row:visible').first.click()
            page.click('#xl-merge-open'); page.click('#xl-merge-go')
            until(lambda: page.is_visible('#xl-merge-yes'))
            t = page.text_content('#xl-list')
            check('French: the question is in French and names the exercises', 'Fusionner Zottman' in t and 'Impossible d\'annuler' in t and 'Make a Full backup' not in t, t[-420:])
        errs = session(pw, be, ALICE, s6, width=390, clock=SAT, lang='fr'); check('no page errors (French merge)', not errs, errs)
finally:
    server.terminate()
done()
