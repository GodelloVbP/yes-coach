"""Requests tab: what is built, fixed or closed sits in one collapsed group, and a moderator account can filter its own messages."""
import subprocess, time
from playwright.sync_api import sync_playwright
from harness import *

def seed(be, who):
    for i, (st, oc, ty) in enumerate([('open', None, 'bug'), ('planned', None, 'feature'), ('resolved', 'built', 'feature'), ('resolved', 'fixed', 'bug'), ('resolved', 'thanks', 'feedback'), ('declined', None, 'feature')]):
        be.ticket(who, title='Item %d' % i, type=ty, status=st, outcome=oc, user_seen_at=now(), resolved_at=now() if st in ('resolved', 'declined') else None)

def open_feedback(page):
    page.wait_for_selector('#tab-feedback:not([hidden])', state='attached')
    page.click('#tab-settings'); page.click('#more-feedback')
    page.wait_for_selector('#v-feedback #tk', state='visible'); page.wait_for_timeout(400)

def count(page, sel): return page.eval_on_selector_all(sel, 'e => e.length')

server = serve()
try:
    with sync_playwright() as pw:
        # an ordinary account: closed ones collapsed together, no filter
        be = Backend(); seed(be, ALICE)
        def s1(page):
            open_feedback(page)
            check('no filter for an ordinary account', page.locator('#tk-mine-filter').count() == 0)
            check('the open and planned ones are listed by kind', count(page, '#tk-list-bug .tk-card') == 1 and count(page, '#tk-list-feature .tk-card') == 1 and count(page, '#tk-list-feedback .tk-card') == 0)
            check('the four finished ones are in one group', count(page, '#tk-closed-list .tk-card') == 4 and not page.evaluate("document.querySelector('#tk-closed').open"))
            check('their cards are not visible until it is opened', not page.is_visible('#tk-closed-list .tk-card >> nth=0'))
            page.click('#tk-closed-sum')
            check('opening shows them, each with its kind and status', page.is_visible('#tk-closed-list .tk-card >> nth=0') and page.locator('#tk-closed-list .tk-kind').count() == 4 and 'built' in page.inner_text('#tk-closed-list').lower())
            page.click('#tk-closed-list .tk-card >> nth=0 >> summary')
            check('a card in it opens as usual', page.locator('#tk-closed-list .tk-card[open]').count() == 1)
            page.click('#tk-closed-sum')
        errs = session(pw, be, ALICE, s1, width=390); check('no page errors (user)', not errs, errs)

        # a moderator account: the filter on its own messages
        be = Backend(admins=[OWNER]); seed(be, OWNER)
        def s2(page):
            open_feedback(page)
            check('a moderator account has the filter, set to All', page.locator('#tk-mine-filter').count() == 1 and page.input_value('#tk-mine-filter') == 'all')
            check('with three choices', page.locator('#tk-mine-filter option').all_text_contents() == ['All', 'Not finished', 'Finished'], page.locator('#tk-mine-filter option').all_text_contents())
            check('All: two active and the group of four, collapsed', count(page, '#tk-mine .tk-group .tk-card') == 2 and count(page, '#tk-closed-list .tk-card') == 4 and not page.evaluate("document.querySelector('#tk-closed').open"))
            page.select_option('#tk-mine-filter', 'active')
            check('Not finished: the two, and no finished group', until(lambda: count(page, '#tk-mine .tk-group .tk-card') == 2 and page.locator('#tk-closed').is_hidden()), page.inner_text('#tk-sum'))
            check('and the line says how many are shown', '2 requests shown' in page.inner_text('#tk-sum'), page.inner_text('#tk-sum'))
            page.select_option('#tk-mine-filter', 'finished')
            check('Finished: only the group, open', until(lambda: page.locator('#tk-closed').is_visible() and page.evaluate("document.querySelector('#tk-closed').open") and count(page, '#tk-closed-list .tk-card') == 4), page.inner_text('#tk-sum'))
            check('and nothing of the active ones', all(page.locator('#tk-group-' + t).is_hidden() for t in ('bug', 'feature', 'feedback')))
            page.select_option('#tk-mine-filter', 'all')
            check('back to All', until(lambda: count(page, '#tk-mine .tk-group .tk-card') == 2 and page.locator('#tk-closed').is_visible()))
            # the owner bar groups its finished tickets too
            page.click('.tk-bar > summary')
            page.select_option('.tk-bar select >> nth=0', 'all')
            check('the owner bar: waiting ones listed, finished ones in a collapsed group', until(lambda: page.locator('#tk-admin-closed').is_visible() and not page.evaluate("document.querySelector('#tk-admin-closed').open") and 'Built, fixed or closed · 4' in page.text_content('#tk-admin-closed-sum')), page.text_content('#tk-admin-closed-sum'))
            page.select_option('.tk-bar select >> nth=0', 'closed')
            check('the owner bar with Closed: the group is open', until(lambda: page.evaluate("document.querySelector('#tk-admin-closed').open") and count(page, '#tk-admin-closed-list .tk-card') == 4))
        errs = session(pw, be, OWNER, s2, width=390); check('no page errors (moderator)', not errs, errs)

        # Dutch
        be = Backend(admins=[OWNER]); seed(be, OWNER)
        def s3(page):
            open_feedback(page)
            t = page.text_content('#tk-closed-sum') + ' ' + ' '.join(page.locator('#tk-mine-filter option').all_text_contents())
            check('Dutch: the group and the filter are translated', 'Gebouwd, opgelost of gesloten · 4' in t and 'Niet afgerond' in t and 'Afgerond' in t and 'Alles' in t, t)
            page.select_option('#tk-mine-filter', 'active')
            check('Dutch: the shown line is translated', until(lambda: '2 verzoeken getoond' in page.inner_text('#tk-sum')), page.inner_text('#tk-sum'))
        errs = session(pw, be, OWNER, s3, width=390, lang='nl'); check('no page errors (nl)', not errs, errs)
finally:
    server.terminate()
done()
