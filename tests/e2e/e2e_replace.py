"""Remove / Replace on an exercise card: the confirm opens under the title (above the Target block), offers Remove, Keep and Replace; Replace
opens the exercise list in the same place and swaps the exercise in that spot for today only, with one Undo."""
import datetime, subprocess, time, re
from playwright.sync_api import sync_playwright
from harness import *

TD = datetime.date.today()
TODAY = TD.isoformat()
WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][TD.weekday()]

def seed(be):
    be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
    for k, nm in (('a', 'Bench press'), ('b', 'Row'), ('c', 'Squat'), ('d', 'Curl')):
        be.docs.append({'path': 'yc/exercises/' + k, 'data': {'name': nm, 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
    be.docs.append({'path': 'yc/templates/a', 'data': {'name': 'Upper A', 'order': 1, 'kind': 'Other', 'focus': '', 'weekday': WD, 'items': [
        {'ex': k, 'order': i, 'sets': 3, 'reps': '10', 'target': '60', 'target_at': '2026-01-01', 'rest_s': 60, 'note': 'Shoulders down' if k == 'b' else None} for i, k in enumerate('abcd')]}})

def doc(be, path): return next((d['data'] for d in reversed(be.docs) if d['path'] == path), {}) or {}
def names(page): return [t.strip().split('\n')[0].lower() for t in page.locator('.fchip').all_inner_texts()]

server = serve()
try:
    with sync_playwright() as pw:
        be = Backend(); seed(be)
        def s1(page):
            page.set_viewport_size({'width': 390, 'height': 844})
            page.goto(BASE); page.wait_for_selector('text=Start Upper A', timeout=8000); page.click('text=Start Upper A')
            page.wait_for_selector('#f-a_1-load', state='visible'); page.wait_for_timeout(400)
            page.locator('.fchip').nth(1).click(); page.wait_for_selector('#f-b_1-load', state='visible'); page.wait_for_timeout(300)
            check('four exercises, Row second', [n[:3] for n in names(page)] == ['ben', 'row', 'squ', 'cur'], names(page))
            card = page.locator('.ex:not(.off)').first
            card.locator('.ex-x').click(); page.wait_for_selector('.ex:not(.off) .ex-rm:not([hidden])')
            g = page.evaluate("""() => { const c = document.querySelector('.ex:not(.off)'); const r = c.querySelector('.ex-rm').getBoundingClientRect(); const b = c.querySelector('.ex-brief').getBoundingClientRect(); const h = c.querySelector('.ex-head').getBoundingClientRect();
                return { rmTop: r.top, rmBottom: r.bottom, briefTop: b.top, headBottom: h.bottom }; }""")
            check('the confirm opens under the title', abs(g['rmTop'] - g['headBottom']) < 40, g)
            check('and above the Target / Last time block, not under it', g['rmBottom'] <= g['briefTop'] + 1, g)
            btns = card.locator('.ex-rm button').all_inner_texts()
            check('Remove, Keep and Replace', [b.strip().lower() for b in btns] == ['remove', 'keep', 'replace'], btns)
            card.locator('.ex-rm button:has-text("Keep")').click()
            check('Keep closes it and keeps the exercise', until(lambda: card.locator('.ex-rm').is_hidden()) and names(page)[1].startswith('row'))

            # Replace
            card.locator('.ex-x').click(); page.wait_for_selector('.ex:not(.off) .ex-rm:not([hidden])')
            card.locator('.ex-rm button:has-text("Replace")').click()
            check('Replace opens the exercise list, under the title', until(lambda: card.locator('.ex-replace-pk .pk-search').is_visible()))
            top = lambda sel: page.evaluate("(s) => document.querySelector('.ex:not(.off) ' + s).getBoundingClientRect().top", sel)
            check('the list sits above the Target block too', top('.ex-replace-pk') < top('.ex-brief'), (top('.ex-replace-pk'), top('.ex-brief')))
            card.locator('.ex-replace-pk .pk-search').fill('lateral raise'); page.wait_for_timeout(500)
            card.locator('.ex-replace-pk .pk-item:visible').first.locator('.pk-go').click()
            check('Row is replaced by the pick, in the same spot', until(lambda: [n[:3] for n in names(page)] == ['ben', 'lat', 'squ', 'cur']), names(page))
            check('and says so, with Undo', 'Replaced Row with' in page.inner_text('#toast-text') and page.is_visible('#toast-undo'), page.inner_text('#toast-text'))
            d = doc(be, 'yc/sessions/' + TODAY)
            check('the day is changed, the plan is not', (d.get('skipped') or {}).get('b') is True and any(v for v in (d.get('added') or {}).values()) and [i['ex'] for i in doc(be, 'yc/templates/a')['items']] == list('abcd'), d)
            check('the new exercise has the same number of rows as Row had', page.locator('.ex:not(.off) .set').count() == 3, page.locator('.ex:not(.off) .set').count())
            page.click('#toast-undo')
            check('Undo brings Row back in its place and takes the pick out', until(lambda: [n[:3] for n in names(page)] == ['ben', 'row', 'squ', 'cur']), names(page))

            # a pick that is already in the workout
            page.locator('.fchip').nth(1).click(); page.wait_for_timeout(300)
            card = page.locator('.ex:not(.off)').first
            card.locator('.ex-x').click(); page.wait_for_selector('.ex:not(.off) .ex-rm:not([hidden])')
            card.locator('.ex-rm button:has-text("Replace")').click(); page.wait_for_selector('.ex:not(.off) .ex-replace-pk .pk-search')
            card.locator('.ex-replace-pk .pk-search').fill('squat'); page.wait_for_timeout(500)
            check('your own exercises that are already in today are not offered', card.locator('.ex-replace-pk .pk-item:has-text("From your log")').count() == 0, card.locator('.ex-replace-pk .pk-item').all_inner_texts()[:3])
            card.locator('.ex-replace-pk .pk-item').filter(has=page.locator('.pk-name', has_text=re.compile(r'^Squat$'))).first.locator('.pk-go').click()
            check('an exercise that is already in today is refused in plain words', until(lambda: 'already in today' in page.inner_text('#toast-text')), page.inner_text('#toast-text'))
            check('and nothing changed', [n[:3] for n in names(page)] == ['ben', 'row', 'squ', 'cur'], names(page))

            # Remove still works
            card = page.locator('.ex:not(.off)').first
            if card.locator('.ex-rm').is_hidden() or card.locator('.ex-rm').count() == 0:
                card.locator('.ex-x').click(); page.wait_for_selector('.ex:not(.off) .ex-rm:not([hidden])')
            card.locator('.ex-rm button:has-text("Remove")').click()
            check('Remove still removes', until(lambda: [n[:3] for n in names(page)] == ['ben', 'squ', 'cur'] and 'Removed Row' in page.inner_text('#toast-text')), names(page))
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors', not errs, errs)

        be = Backend(); seed(be)
        def s3(page):
            page.wait_for_selector('#today-card .skew', timeout=8000); page.locator('#today-card .skew').first.click()
            page.wait_for_selector('.ex:not(.off) .ex-x', timeout=8000)
            page.locator('.ex:not(.off) .ex-x').click(); page.wait_for_selector('.ex:not(.off) .ex-rm:not([hidden])')
            t = page.locator('.ex:not(.off) .ex-rm').inner_text().lower()
            check('Dutch: the choices are translated', 'vervang' in t and 'houden' in t or 'laten' in t, t)
        errs = session(pw, be, ALICE, s3, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
