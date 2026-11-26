"""End-to-end check, part of the old tickets file: sending and answering tickets, the pop-ups, the owner bar, Home link, resume bar. The real built app in headless Chrome, Supabase faked in memory."""
import subprocess, time, datetime, json
from playwright.sync_api import sync_playwright
from harness import *
from harness import EXTERNAL

def card_of(page, title, root='#tk-admin-list'):
    return page.locator(root + ' .tk-card').filter(has=page.locator('.tk-title', has_text=title))

def go(page, tab):
    if tab in ('feedback', 'exercises'):
        page.click('#tab-settings'); page.click('#more-' + tab)
    else: page.click('#tab-' + tab)

def open_feedback(page):
    page.wait_for_selector('#tab-feedback:not([hidden])', state='attached')
    page.click('#tab-settings'); page.click('#more-feedback')
    page.wait_for_selector('#v-feedback #tk', state='visible')

def logo(page):
    page.locator('#mark:visible, #mark2:visible').first.click()

def send_form(page, title, text, name=None, kind=None):
    page.click('#tk .tk-type[data-type=%s]' % (kind or 'bug'))
    if name is not None: page.fill('#tk form input[autocomplete=given-name]', name)
    page.fill('#tk form input[autocomplete=off]', title)
    page.fill('#tk form textarea', text)
    page.click('#tk form button[type=submit]')

server = serve()
try:
    with sync_playwright() as pw:
        # ---- 1. the tab, the three sections, sending a ticket with a first name
        be = Backend()
        def s1(page):
            open_feedback(page)
            check('tab selected', page.get_attribute('#tab-feedback', 'aria-selected') == 'true' and not page.is_visible('#v-settings'))
            heads = page.eval_on_selector_all('#v-feedback h2', 'e => e.map(x => x.textContent)')
            check('one visible heading, nothing to show yet below it', [x for x in heads if x] == ['Send us something', 'We have a question', 'Your messages'] and page.is_visible('#tk') and not page.is_visible('#tk-ask') and not page.is_visible('#tk-mine'), heads)
            check('one short line of why, no wall of text', len(page.inner_text('#tk .tk-lead').split()) <= 25 and 'one person' in page.inner_text('#tk .tk-lead'), page.inner_text('#tk .tk-lead'))
            tiles = page.eval_on_selector_all('#tk .tk-type', 'e => e.map(x => x.dataset.type)')
            check('three things to send, as the main choice', tiles == ['bug', 'feature', 'feedback'] and not page.is_visible('#tk form'), tiles)
            check('each is big enough to tap', page.evaluate("[...document.querySelectorAll('#tk .tk-type')].every((b) => b.getBoundingClientRect().height >= 44)"))
            page.click('#tk .tk-type[data-type=feature]')
            check('a choice opens the form under it, named for the choice (for screen readers)', page.is_visible('#tk form') and page.get_attribute('#tk form', 'aria-label') == 'A feature I would like' and page.get_attribute('#tk .tk-type[data-type=feature]', 'aria-pressed') == 'true' and page.get_attribute('#tk .tk-type[data-type=bug]', 'aria-pressed') == 'false')
            check('says what is saved, next to Send', 'first name' in page.inner_text('#tk form') and 'email' in page.inner_text('#tk form') and 'training data' in page.inner_text('#tk form'))
            check('there is no second type picker in the form', page.locator('#tk form select').count() == 0)
            check('name field empty at first', page.input_value('#tk form input[autocomplete=given-name]') == '')
            page.click('#tk form button[type=submit]')
            check('title comes first', 'Add a short title.' in page.inner_text('#tk form'))
            page.fill('#tk form input[autocomplete=off]', 'Crash on Plan')
            page.click('#tk form button[type=submit]')
            check('then the message', 'at least 10 characters' in page.inner_text('#tk form'))
            page.fill('#tk form textarea', 'The Plan screen goes blank when I tap a day.')
            page.click('#tk form button[type=submit]')
            check('name is required last', 'Add your first name' in page.inner_text('#tk form'))
            page.fill('#tk form input[autocomplete=given-name]', 'Sanne')
            page.click('#tk .tk-type[data-type=bug]')
            check('switching the choice keeps what you typed and changes the hint', page.input_value('#tk form input[autocomplete=off]') == 'Crash on Plan' and 'expect' in (page.get_attribute('#tk form textarea', 'placeholder') or ''))
            page.fill('#tk form textarea', 'The Plan screen goes blank when I tap a day.')
            page.click('#tk form button[type=submit]')
            page.wait_for_selector('#tk-list-bug .tk-card')
            check('bug listed under bugs only', 'Crash on Plan' in page.inner_text('#tk-list-bug') and page.query_selector('#tk-list-feature .tk-card') is None and page.query_selector('#tk-list-feedback .tk-card') is None)
            check('status Received', 'received' in page.text_content('#tk-list-bug').lower())
            check('summary line', page.inner_text('#tk-sum') == 'Sent 1 request.', page.inner_text('#tk-sum'))
            check('form closes and confirms', not page.is_visible('#tk form') and 'Sent. Thank you' in page.inner_text('#tk'))
            page.click('#tk .tk-type[data-type=feedback]')
            check('name is prefilled next time', page.input_value('#tk form input[autocomplete=given-name]') == 'Sanne')
            check('no owner bar for users', page.query_selector('.tk-bar') is None)
        errs = session(pw, be, ALICE, s1)
        t = be.tickets[0]
        check('sent type, name and fields', (t['type'], t['title'], t['user_id'], t['first_name']) == ('bug', 'Crash on Plan', ALICE, 'Sanne'), t)
        check('device context sent', t['context'].get('screen') and t['context'].get('viewport') and t['context'].get('lang') and 'ua' in t['context'], t['context'])
        check('app version is a build stamp', t['app_version'] not in (None, '', 'dev'), t['app_version'])
        check('no page errors (send)', not errs, errs)

        # ---- 2. a question from the owner, the dot on the tab, the answer
        be = Backend()
        tk = be.ticket(ALICE, title='Night mode', status='needs_info'); be.message(tk['id'], 'user', 'It is too bright at night'); be.message(tk['id'], 'admin', 'Which screen is too bright?')
        def s2(page):
            page.wait_for_selector('#tab-feedback.tk-dot', state='attached')
            check('tab label mentions the question', 'question' in (page.get_attribute('#tab-feedback', 'title') or ''))
            open_feedback(page)
            check('the question waits at the top, in its own block', page.is_visible('#tk-ask') and 'We have a question' in page.text_content('#tk-ask h2') and page.evaluate("document.querySelector('#tk-ask').compareDocumentPosition(document.querySelector('#tk-mine')) & Node.DOCUMENT_POSITION_FOLLOWING") > 0)
            check('the status chip is there but not repeated on screen', 'We have a question' in page.text_content('#tk-ask-list .chip') and not page.is_visible('#tk-ask-list .chip'))
            check('it is not listed twice', page.locator('#tk-list-feature .tk-card').count() == 0)
            check('its card is open already', page.evaluate("document.querySelector('#tk-ask-list .tk-card').open"))
            page.wait_for_selector('#tk-ask-list .tk-msg.admin')
            check('thread shows both sides', 'Which screen is too bright?' in page.inner_text('#tk-ask-list .tk-thread') and 'It is too bright at night' in page.inner_text('#tk-ask-list .tk-thread'))
            check('reply box asks for an answer', 'Your answer' in page.text_content('#tk-ask-list .tk-reply'))
            page.fill('#tk-ask-list .tk-reply textarea', 'The Train screen')
            page.click('#tk-ask-list .tk-reply button')
            page.wait_for_function("!document.querySelector('#tab-feedback.tk-dot')")
            check('answered: the block goes, the request is listed with its kind', until(lambda: not page.is_visible('#tk-ask')) and page.locator('#tk-list-feature .tk-card').count() == 1)
            page.click('#tk-list-feature summary')
            page.wait_for_selector('#tk-list-feature .tk-msg.user >> text=The Train screen')
        errs = session(pw, be, ALICE, s2)
        check('answer stored', be.messages[-1]['body'] == 'The Train screen' and be.messages[-1]['author'] == 'user')
        check('no page errors (question)', not errs, errs)

        # ---- 3. one paged pop-up for everything that is done
        be = Backend()
        be.ticket(ALICE, title='Dark mode', status='resolved', outcome='built', resolution_note='It is under Settings.', resolved_at=now())
        be.ticket(ALICE, title='Crash on Plan', type='bug', status='resolved', outcome='fixed', resolved_at=now())
        be.ticket(ALICE, title='Love the app', type='feedback', status='resolved', outcome='thanks', resolved_at=now())
        be.ticket(ALICE, title='Social feed', status='declined', resolution_note='It would need ads, which we will not add.', resolved_at=now())
        be.ticket(ALICE, title='Old news', status='resolved', outcome='built', resolved_at=now(), user_seen_at=now())
        texts = {}
        def s3(page):
            page.wait_for_selector('.tk-pop')
            check('one pop-up only', page.eval_on_selector_all('.tk-pop', 'e => e.length') == 1)
            check('popup is a dialog', page.get_attribute('.tk-pop-in', 'role') == 'dialog' and page.get_attribute('.tk-pop-in', 'aria-modal') == 'true')
            check('counter starts at 1 of 4', page.inner_text('.tk-count').lower() == '1 of 4', page.inner_text('.tk-count'))
            check('back disabled on first', page.is_disabled('.tk-nav button[aria-label=Previous]') and not page.is_disabled('.tk-nav button[aria-label=Next]'))
            check('focus on close', page.evaluate("document.activeElement.textContent") == 'Close')
            seen_texts = []; heads = []
            for n in range(4):
                seen_texts.append(page.inner_text('.tk-pop-in').replace('\n', ' ')); heads.append(page.inner_text('.tk-pop h2').lower())
                if n < 3: page.click('.tk-nav button[aria-label=Next]')
            check('counter at the end', page.inner_text('.tk-count').lower() == '4 of 4')
            check('next disabled on last, focus moved to Close', page.is_disabled('.tk-nav button[aria-label=Next]') and page.evaluate("document.activeElement.textContent") == 'Close')
            joined = ' | '.join(seen_texts)
            norm = lambda x: ' '.join(x.split())
            joined = norm(joined)
            check('built text', 'Yes Coach! built your feature request "Dark mode". It is under Settings. Thank you for contributing.' in joined, joined)
            check('fixed text', 'Yes Coach! fixed your bug report "Crash on Plan". Thank you for contributing.' in joined, joined)
            check('feedback text', 'Yes Coach! read your feedback "Love the app". Thank you for contributing.' in joined, joined)
            check('declined text', 'We decided not to go ahead with your feature request "Social feed". It would need ads, which we will not add. Sorry about that. You are welcome to send a new one. Thank you for contributing.' in joined, joined)
            check('your request shown in a box with the title and text', page.locator('.tk-pop-sent .tk-pop-st').count() == 1 and page.inner_text('.tk-pop-sent .tk-pop-st') != '' and 'please add dark mode' in page.inner_text('.tk-pop-sent').lower())
            check('label per type', sorted(heads) == ['your bug report:', 'your feedback:', 'your request:', 'your request:'], heads)
            check('already seen not shown', 'Old news' not in joined)
            page.keyboard.press('ArrowLeft')
            check('arrow key goes back', page.inner_text('.tk-count').lower() == '3 of 4')
            page.keyboard.press('Tab'); page.keyboard.press('Tab'); page.keyboard.press('Tab'); page.keyboard.press('Tab')
            check('focus stays in dialog', page.evaluate("!!document.activeElement.closest('.tk-pop')"))
            page.keyboard.press('Escape')
            page.wait_for_selector('.tk-pop', state='detached')
            page.wait_for_timeout(300)
        errs = session(pw, be, ALICE, s3, home=True)
        seen = [t for t in be.tickets if t['user_seen_at']]
        check('all four viewed, so all marked seen', len(seen) == 5, [t['title'] for t in seen])
        def s3b(page):
            page.wait_for_selector('#tab-feedback', state='attached'); page.wait_for_timeout(800)
            check('no popup the next visit', page.query_selector('.tk-pop') is None)
        errs += session(pw, be, ALICE, s3b)
        check('no page errors (popups)', not errs, errs)

        # a single ticket shows no arrows; closing early leaves the unseen ones for next time
        be = Backend()
        be.ticket(ALICE, title='Only one', status='resolved', outcome='built', resolved_at=now())
        def s3c(page):
            page.wait_for_selector('.tk-pop')
            check('single: no arrows or counter', page.query_selector('.tk-nav') is None)
            page.click('.tk-pop >> text=Close'); page.wait_for_selector('.tk-pop', state='detached'); page.wait_for_timeout(300)
        errs = session(pw, be, ALICE, s3c); check('single marked seen', be.tickets[0]['user_seen_at'] is not None)
        be = Backend()
        for n in range(3): be.ticket(ALICE, title='T%d' % n, status='resolved', outcome='built', resolved_at=now())
        def s3d(page):
            page.wait_for_selector('.tk-pop'); page.click('.tk-pop >> text=Close'); page.wait_for_selector('.tk-pop', state='detached'); page.wait_for_timeout(300)
            open_feedback(page)
            page.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); page.wait_for_timeout(500)
            check('skipped ones do not pop up again this visit', page.query_selector('.tk-pop') is None)
        errs = session(pw, be, ALICE, s3d)
        check('closing early only marks the one seen', sum(1 for t in be.tickets if t['user_seen_at']) == 1, [t['user_seen_at'] for t in be.tickets])
        def s3e(page):
            page.wait_for_selector('.tk-pop'); check('the other two come back next visit', page.inner_text('.tk-count').lower() == '1 of 2', page.inner_text('.tk-count'))
        errs = session(pw, be, ALICE, s3e)

        # ---- 4. contribution line and the three lists
        be = Backend()
        for i, (st, oc, ty) in enumerate([('resolved', 'built', 'feature'), ('resolved', 'fixed', 'bug'), ('resolved', 'thanks', 'feedback'), ('planned', None, 'feature'), ('open', None, 'bug'), ('declined', None, 'feature')]):
            be.ticket(ALICE, title='T%d' % i, type=ty, status=st, outcome=oc, user_seen_at=now(), resolved_at=now() if st in ('resolved', 'declined') else None)
        def s4(page):
            open_feedback(page)
            check('summary counts outcomes, not volume', page.inner_text('#tk-sum') == 'Sent 6 requests: 2 built or fixed, 1 planned.', page.inner_text('#tk-sum'))
            n = lambda t: page.eval_on_selector_all('#tk-list-%s .tk-card' % t, 'e => e.length')
            check('cards split by type', (n('feature'), n('bug'), n('feedback')) == (3, 2, 1), (n('feature'), n('bug'), n('feedback')))
            labels = page.eval_on_selector_all('#v-feedback .tk-card .chip', 'els => els.map(e => e.textContent)')
            check('status words', sorted(labels) == sorted(['Built', 'Fixed', 'Thank you!', 'Planned', 'Received', 'Not planned']), labels)
            check('final tickets have no reply box', page.eval_on_selector_all('#v-feedback .tk-card', "els => els.filter(e => e.querySelector('.tk-reply')).length") == 2)
        errs = session(pw, be, ALICE, s4); check('no page errors (summary)', not errs, errs)

        # ---- 5. what a user types is text, never HTML
        be = Backend()
        evil = '<img src=x onerror="window.__xss=1"><b>bold</b>'
        tk = be.ticket(ALICE, title=evil, body=evil); be.message(tk['id'], 'admin', evil)
        def s5(page):
            open_feedback(page)
            page.click('#tk-list-feature summary'); page.wait_for_selector('#tk-list-feature .tk-msg')
            page.wait_for_timeout(300)
            check('html shown as text', evil in page.inner_text('#tk-list-feature .tk-title') and page.query_selector('#v-feedback img') is None and page.query_selector('#tk-list-feature b') is None)
            check('no script ran', page.evaluate('window.__xss') is None)
        errs = session(pw, be, ALICE, s5); check('no page errors (escaping)', not errs, errs)

        # ---- 6. limits and errors reach the user in plain words
        be = Backend(); be.fail_insert = 'too_many_tickets'
        def s6(page):
            open_feedback(page); send_form(page, 'Another one', 'Something else entirely', name='Sanne')
            page.wait_for_function("document.querySelector('#tk form').innerText.includes('Daily limit of 5')")
            check('daily limit message', True); check('form stays open with the text', page.input_value('#tk form input[autocomplete=off]') == 'Another one')
        errs = session(pw, be, ALICE, s6); check('no page errors (limit)', not errs, errs)

        # ---- 7. users do not get the owner bar; the owner does, with name and email
        be = Backend(admins=[OWNER])
        a = be.ticket(ALICE, title='Dark mode', type='feature', first_name='Sanne'); b = be.ticket(ALICE, title='Night mode', type='feature'); be.ticket(ALICE, title='Done already', status='resolved', outcome='built', resolved_at=now())
        be.message(a['id'], 'user', 'please')
        def s8(page):
            open_feedback(page); page.wait_for_selector('.tk-bar')
            check('owner bar title shows waiting count', '2 waiting' in page.inner_text('.tk-bar > summary').lower(), page.inner_text('.tk-bar > summary'))
            check('owner bar starts folded', not page.evaluate("document.querySelector('.tk-bar').open"))
            check("owner's own lists show only own tickets", page.query_selector('#tk-list-feature .tk-card') is None)
            page.click('.tk-bar > summary')
            page.wait_for_selector('#tk-admin-list .tk-card')
            check('owner sees waiting tickets only by default', page.eval_on_selector_all('#tk-admin-list .tk-card', 'e => e.length') == 2, page.inner_text('#tk-admin-sum'))
            page.select_option('.tk-bar select >> nth=0', 'all')
            check('filter shows all', page.eval_on_selector_all('#tk-admin-list .tk-card', 'e => e.length') == 3)
            page.select_option('.tk-bar select >> nth=0', 'open')
            card = card_of(page, 'Dark mode'); card.locator('summary').click()
            info = card.locator('.tk-info').inner_text()
            check('owner sees first name and sign-in email', 'Sanne' in info and 'alice@example.com' in info, info)
            heads = [x.lower() for x in card.locator('.tk-sec > .lab').all_inner_texts()]
            check('owner card has labelled blocks in order', heads[:4] == ['from', 'their device', 'their message', 'conversation'] and heads[-2:] == ['your reply', 'decision'], heads)
            check('their message is shown on its own', 'please add dark mode' in card.locator('.tk-text').first.inner_text())
            page.wait_for_selector('.tk-card[open] .tk-msg.user')
            check('their reply is labelled with their name', 'sanne' in card.locator('.tk-msg.user .lab').inner_text().lower(), card.locator('.tk-msg.user .lab').inner_text())
            card = card_of(page, 'Night mode')
            card.locator('summary').click()
            card.locator('.tk-decide select >> nth=-1').select_option(a['id'])
            check('duplicate locks status and note', card.locator('.tk-decide select >> nth=0').is_disabled() and card.locator('.tk-decide textarea').is_disabled())
            card.locator('button', has_text='Save').click()
            page.wait_for_timeout(300)
            card2 = card_of(page, 'Dark mode')
            check('open card stays open after save', card2.evaluate('e => e.open'))
            card2.locator('.tk-decide select >> nth=0').select_option('resolved')
            check('outcome appears when resolved', card2.locator('.tk-decide select >> nth=1').is_visible())
            check('outcome defaults by type', card2.locator('.tk-decide select >> nth=1').input_value() == 'built')
            card2.locator('.tk-decide textarea').fill('It is in Settings now.')
            card2.locator('button', has_text='Save').click()
            page.wait_for_timeout(400)
        errs = session(pw, be, OWNER, s8)
        saves = [c for c in be.calls if c[0] == 'admin_set_ticket']
        check('duplicate save sent the link', saves and saves[0][1]['p_duplicate_of'] == a['id'] and saves[0][1]['p_id'] == b['id'], saves)
        check('resolve save sent status, outcome and note', len(saves) > 1 and saves[1][1]['p_status'] == 'resolved' and saves[1][1]['p_outcome'] == 'built' and saves[1][1]['p_note'] == 'It is in Settings now.' and saves[1][1]['p_duplicate_of'] is None, saves)
        check('no page errors (owner)', not errs, errs)

        be = Backend(admins=[OWNER]); a = be.ticket(ALICE, title='Fix it', type='bug')
        def s9(page):
            open_feedback(page); page.wait_for_selector('.tk-bar'); page.click('.tk-bar > summary')
            card = page.locator('#tk-admin-list .tk-card'); card.locator('summary').click()
            card.locator('.tk-reply textarea').fill('Which phone do you have?')
            card.locator('button', has_text='Ask a question').click()
            page.wait_for_selector('#tk-admin-list .chip.tk-ask')
            card = page.locator('#tk-admin-list .tk-card')
            card.locator('button', has_text='Delete').click(); check('first tap arms', 'tap again' in card.locator('.tk-decide').text_content().lower())
            card.locator('button', has_text='Tap again').click(); page.wait_for_timeout(400)
        errs = session(pw, be, OWNER, s9)
        check('ask call sent', ('admin_reply', {'p_ticket': a['id'], 'p_body': 'Which phone do you have?', 'p_ask': True}) in be.calls, be.calls)
        check('delete call sent and ticket gone', any(c[0] == 'admin_delete_ticket' for c in be.calls) and not be.tickets)
        check('no page errors (owner ask/delete)', not errs, errs)

finally:
    server.terminate()
done()
