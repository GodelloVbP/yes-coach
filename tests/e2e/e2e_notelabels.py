"""Every note says what it belongs to: the exercise note (every workout), a note about an exercise in this workout, and the note of the whole
workout, each with its own look. A note from an earlier workout says when it was written."""
import datetime, subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
BACK = (TD - datetime.timedelta(days=5)).isoformat()
MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
BACK_TXT = '%d %s' % (int(BACK[8:10]), MON[int(BACK[5:7]) - 1])
TODAY_TXT = '%d %s' % (TD.day, MON[TD.month - 1])
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be, my_note=None):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    ex = {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}
    if my_note: ex['my_note'] = my_note
    be.docs.append({'path': 'yc/exercises/bench', 'data': ex})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '10', 'target': '', 'target_at': '2026-01-01', 'rest_s': 60, 'note': None}]}})
    be.docs.append({'path': 'yc/notes/%s_bench' % BACK, 'data': {'text': 'Right shoulder clicked on the last rep', 'about': 'bench', 'about_label': 'Bench press', 'date': BACK, 'at': BACK + 'T10:00:00Z', 'status': 'new'}})

def open_day(page):
    page.goto(BASE); page.wait_for_selector('#btn-start', timeout=8000); page.click('#btn-start'); page.wait_for_selector('#f-bench_1-load', state='visible'); page.wait_for_timeout(400)

server = serve()
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be, my_note='Seat on 4, narrow grip')
        def s1(page):
            open_day(page)
            ex = page.locator('.ex').first
            stick = ex.locator('.ex-stick .nt-tag')
            check('the exercise note says it stays with the exercise, in every workout', stick.is_visible() and 'Stays with Bench press, shown in every workout' in stick.inner_text() and 'exercise note' in stick.inner_text().lower(), stick.inner_text())
            last = ex.locator('.ex-lastnote').inner_text()
            check('a note from an earlier workout says when', ('note from %s' % BACK_TXT.lower()) in last.lower() and 'Right shoulder clicked' in last, last)
            check('the ✎ button says which note it opens', 'this workout only' in (ex.get_by_role('button', name='Note about Bench press').get_attribute('title') or ''))
            ex.get_by_role('button', name='Note about Bench press').click(); page.wait_for_timeout(300)
            today = ex.locator('.notebox.nt-in-ex .nt-tag')
            check('the note about the exercise in this workout says so', today.is_visible() and 'this workout' in today.inner_text().lower() and 'About Bench press, today only' in today.inner_text(), today.inner_text())
            day = page.locator('.sess-foot .notebox.nt-in-day .nt-tag')
            check('the workout note says it is the whole workout, with the day and date', day.is_visible() and 'whole workout' in day.inner_text().lower() and ('Upper A · %s' % TODAY_TXT) in day.inner_text(), day.inner_text())
            chip = lambda sel: page.evaluate("(s) => { const c = getComputedStyle(document.querySelector(s)); return c.backgroundColor; }", sel)
            a, b, c = chip('.ex-stick .nt-tag .chip'), chip('.nt-in-ex .nt-tag .chip'), chip('.nt-in-day .nt-tag .chip')
            check('three notes, three looks (orange, outlined, solid blue)', len({a, b, c}) == 3, (a, b, c))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors', not errs, errs)

        be = Backend(); seed(be)
        def s2(page):
            open_day(page)
            check('no exercise note yet: only the add link, no label', page.locator('.ex-stick .nt-tag').is_hidden() and page.locator('.ex-stick-add').is_visible())
        errs = session(pw, be, ALICE, s2, width=390); check('no page errors (empty)', not errs, errs)

        be = Backend(); seed(be, my_note='Seat on 4')
        def s3(page):
            open_day(page)
            t = page.locator('.ex-stick .nt-tag').inner_text()
            check('Dutch: the labels are translated', 'oefeningnotitie' in t.lower() and 'bij elke training zichtbaar' in t, t)
            check('Dutch: the workout note label too', 'hele training' in page.locator('.nt-in-day .nt-tag').inner_text().lower(), page.locator('.nt-in-day .nt-tag').inner_text())
        errs = session(pw, be, ALICE, s3, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
