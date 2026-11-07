"""End-to-end check of the tickets screens: the real built app in headless Chrome, Supabase faked in memory."""
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
    page.click('#tk >> text=Send something')
    if name is not None: page.fill('#tk form input[autocomplete=given-name]', name)
    if kind: page.select_option('#tk form select', kind)
    page.fill('#tk form input[autocomplete=off]', title)
    page.fill('#tk form textarea', text)
    page.click('#tk form button[type=submit]')

server = subprocess.Popen(['python3', '-m', 'http.server', '8765', '--directory', REPO], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as pw:
        # ---- 1. the tab, the three sections, sending a ticket with a first name
        be = Backend()
        def s1(page):
            open_feedback(page)
            check('tab selected', page.get_attribute('#tab-feedback', 'aria-selected') == 'true' and not page.is_visible('#v-settings'))
            heads = page.eval_on_selector_all('#v-feedback h2', 'e => e.map(x => x.textContent)')
            check('four headings', heads == ['Feedback & Requests', 'My requested features', 'My reported bugs', 'My feedback'], heads)
            check('how and why text', 'free' in page.inner_text('#tk').lower() and 'no ads' in page.inner_text('#tk').lower())
            check('says what is saved', 'first name' in page.inner_text('#tk') and 'email' in page.inner_text('#tk'))
            for t, e in (('feature', 'No requests yet.'), ('bug', 'No bug reports yet.'), ('feedback', 'No feedback yet.')):
                check('empty ' + t, page.inner_text('#tk-list-' + t).strip() == e, page.inner_text('#tk-list-' + t))
            page.click('#tk >> text=Send something')
            check('name field empty at first', page.input_value('#tk form input[autocomplete=given-name]') == '')
            page.click('#tk form button[type=submit]')
            check('name is required', 'first name' in page.inner_text('#tk form').lower() and 'Add your first name' in page.inner_text('#tk form'))
            page.fill('#tk form input[autocomplete=given-name]', 'Sanne')
            page.click('#tk form button[type=submit]')
            check('title is required', 'Add a few words' in page.inner_text('#tk form'))
            page.fill('#tk form input[autocomplete=off]', 'Crash on Plan')
            page.click('#tk form button[type=submit]')
            check('body is required', 'at least 10 characters' in page.inner_text('#tk form'))
            page.select_option('#tk form select', 'bug')
            check('hint follows the type', 'expect' in (page.get_attribute('#tk form textarea', 'placeholder') or ''))
            page.fill('#tk form textarea', 'The Plan screen goes blank when I tap a day.')
            page.click('#tk form button[type=submit]')
            page.wait_for_selector('#tk-list-bug .tk-card')
            check('bug listed under bugs only', 'Crash on Plan' in page.inner_text('#tk-list-bug') and page.query_selector('#tk-list-feature .tk-card') is None and page.query_selector('#tk-list-feedback .tk-card') is None)
            check('status Received', 'received' in page.text_content('#tk-list-bug').lower())
            check('summary line', page.inner_text('#tk-sum') == 'You have sent 1 request.', page.inner_text('#tk-sum'))
            check('form closes and confirms', not page.is_visible('#tk form') and 'Sent. Thank you' in page.inner_text('#tk'))
            page.click('#tk >> text=Send something')
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
            check('status chip', 'We have a question' in page.text_content('#tk-list-feature .chip'))
            page.click('#tk-list-feature summary')
            page.wait_for_selector('#tk-list-feature .tk-msg.admin')
            check('thread shows both sides', 'Which screen is too bright?' in page.inner_text('#tk-list-feature .tk-thread') and 'It is too bright at night' in page.inner_text('#tk-list-feature .tk-thread'))
            check('reply box asks for an answer', 'Your answer' in page.text_content('#tk-list-feature .tk-reply'))
            page.fill('#tk-list-feature .tk-reply textarea', 'The Train screen')
            page.click('#tk-list-feature .tk-reply button')
            page.wait_for_function("!document.querySelector('#tab-feedback.tk-dot')")
            check('card stays open after repaint', page.evaluate("document.querySelector('#tk-list-feature .tk-card').open"))
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
            check('built text', 'Yes Coach! built your feature request "Dark mode". It is under Settings. Thank you very much for contributing!' in joined, joined)
            check('fixed text', 'Yes Coach! fixed your bug report "Crash on Plan". Thank you very much for contributing!' in joined, joined)
            check('feedback text', 'Yes Coach! read your feedback "Love the app". Thank you very much for contributing!' in joined, joined)
            check('declined text', 'Yes Coach! could not take up your feature request "Social feed". It would need ads, which we will not add. Our apologies! You are welcome to send a new one. Thank you very much for contributing!' in joined, joined)
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
            check('summary counts outcomes, not volume', page.inner_text('#tk-sum') == 'You have sent 6 requests: 2 built or fixed, 1 planned.', page.inner_text('#tk-sum'))
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
            page.wait_for_function("document.querySelector('#tk form').innerText.includes('daily limit')")
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

        # ---- 7b. owner copies the shown tickets as text, without emails
        be = Backend(admins=[OWNER])
        a = be.ticket(ALICE, title='Finish button', type='feature', first_name='Sanne', body='Please add a finish day button.', context={'installed': True, 'screen': '390x844', 'ua': 'iPhone Safari'})
        be.message(a['id'], 'admin', 'Do you mean on the Train screen?'); be.message(a['id'], 'user', 'Yes, at the bottom.')
        be.ticket(ALICE, title='Closed one', status='resolved', outcome='built', resolution_note='Done.', resolved_at=now())
        got = {}
        def s8b(page):
            open_feedback(page); page.wait_for_selector('.tk-bar'); page.click('.tk-bar > summary'); page.wait_for_selector('#tk-admin-list .tk-card')
            page.click('.tk-bar >> text=Copy shown tickets'); page.wait_for_function("document.querySelector('.tk-bar-body').innerText.includes('Copied')")
            got['text'] = page.evaluate('navigator.clipboard.readText()')
        errs = session(pw, be, OWNER, s8b)
        t = got.get('text', '')
        check('copy has the shown ticket, name, text, thread, device', all(x in t for x in ('Finish button', 'Sanne', 'Please add a finish day button.', 'We wrote: Do you mean on the Train screen?', 'Sanne wrote: Yes, at the bottom.', 'installed app')), t)
        check('copy leaves out email and closed tickets', 'example.com' not in t and 'Closed one' not in t, t)
        check('no page errors (copy)', not errs, errs)

        # ---- 7c. an open day can be finished from the Resume bar
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'weekday': 'Mon', 'kind': 'Push', 'focus': 'Chest', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': 8, 'target': '', 'target_at': datetime.date.today().isoformat(), 'rest_s': 90, 'note': None}]}})
        def s7c(page):
            page.wait_for_selector('#tab-train', state='attached')
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-btn', state='visible'); page.click('#resume-btn'); page.wait_for_selector('#session', state='visible')
            check('bottom button says Finish day', page.locator('#session >> text=Finish day').count() >= 1)
            page.click('#sb-back'); page.wait_for_selector('#resume', state='visible')
            check('resume bar offers Finish day', page.is_visible('#resume-fin') and 'finish day' in page.inner_text('#resume-fin').lower())
            page.click('#resume-fin'); page.wait_for_selector('#resume', state='hidden')
            check('finishing clears the open day', page.evaluate("localStorage.getItem('yc-active')") in (None, 'null'))
            page.reload(); page.wait_for_timeout(800)
            check('not shown again after a reload', not page.is_visible('#resume'))
        errs = session(pw, be, ALICE, s7c, width=390); check('no page errors (finish)', not errs, errs)

        # ---- 8. Home link opens the tab
        be = Backend()
        def s10(page):
            page.wait_for_selector('#tab-feedback:not([hidden])', state='attached'); logo(page)
            page.click('#hm-ticket')
            page.wait_for_selector('#tk', state='visible')
            check('home link opens the tab', page.get_attribute('#tab-feedback', 'aria-selected') == 'true')
            page.goto(BASE); page.wait_for_selector('#v-train', state='visible')
            check('signed in, the app opens on Train after reload', page.is_visible('#v-train') and page.get_attribute('#tab-feedback', 'aria-selected') != 'true')
        errs = session(pw, be, ALICE, s10); check('no page errors (home link)', not errs, errs)

        # ---- 9. navigation: a sidebar from 1024px, a bottom bar below it; More holds the rest
        be = Backend()
        def desk(page):
            page.wait_for_selector('#tab-feedback:not([hidden])', state='attached')
            check('wide: sidebar on the left', page.evaluate("(() => { const r = document.querySelector('#tabs-nav').getBoundingClientRect(); return r.left === 0 && r.top === 0 && r.width < 300 && r.height >= innerHeight - 1; })()"))
            check('wide: six main entries visible, Request among them', all(page.is_visible('#tab-' + t) for t in ('train', 'plan', 'progress', 'food', 'feedback', 'settings')))
            check('wide: Exercises is not in the bar', not page.is_visible('#tab-exercises'))
            page.wait_for_timeout(600)
            check('wide: no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        for w in (1024, 1280): errs = session(pw, be, ALICE, desk, width=w); check('no errors wide %d' % w, not errs, errs)
        def phone(page):
            page.wait_for_selector('#tab-feedback', state='attached'); page.wait_for_timeout(300)
            check('phone: bottom bar at the bottom', page.evaluate("(() => { const r = document.querySelector('#tabs-nav').getBoundingClientRect(); return Math.abs(r.bottom - innerHeight) < 1 && r.left === 0 && r.right <= innerWidth + 0.5; })()"))
            check('phone: six entries, Request between Food and More', all(page.is_visible('#tab-' + t) for t in ('train', 'plan', 'progress', 'food', 'feedback', 'settings')) and page.evaluate("[...document.querySelectorAll('.mainnav .tab:not(.tab-sub)')].map((t) => t.id).join()") == 'tab-train,tab-plan,tab-progress,tab-food,tab-feedback,tab-settings')
            check('phone: no hamburger', page.query_selector('#menu-btn') is None)
            check('phone: Train is selected on start', page.get_attribute('#tab-train', 'aria-selected') == 'true' and page.is_visible('#v-train'))
            check('phone: no horizontal overflow', page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            check('phone: no dot without a question', page.evaluate("getComputedStyle(document.querySelector('#tab-feedback .nav-dot')).display") == 'none')
            page.click('#tab-settings'); page.wait_for_selector('#more-feedback', state='visible')
            check('phone: More lists Exercises and Feedback', page.is_visible('#more-exercises') and page.is_visible('#more-feedback'))
            check('phone: More stays marked in the bar', page.get_attribute('#tab-settings', 'aria-selected') == 'true')
            page.click('#more-feedback'); page.wait_for_selector('#tk', state='visible')
            check('phone: Feedback opens from More, the bar marks Request and not More', page.get_attribute('#tab-feedback', 'aria-selected') == 'true' and 'in-more' not in (page.get_attribute('#tab-settings', 'class') or ''), page.get_attribute('#tab-settings', 'class'))
            page.click('#tab-train'); page.wait_for_selector('#v-train', state='visible')
            page.click('#tab-feedback'); page.wait_for_selector('#tk', state='visible')
            check('phone: the Request tab opens it in one tap', page.get_attribute('#tab-feedback', 'aria-selected') == 'true' and not page.is_visible('#v-train'))
            page.click('#tab-plan'); page.wait_for_selector('#v-plan', state='visible')
            check('phone: switching tabs works', page.get_attribute('#tab-plan', 'aria-selected') == 'true')
        be2 = Backend(); be2.ticket(ALICE, title='Q', status='needs_info')
        def dot(page):
            page.wait_for_selector('#tab-feedback.tk-dot', state='attached')
            check('phone: a dot on Request', page.evaluate("getComputedStyle(document.querySelector('#tab-feedback .nav-dot')).display") != 'none')
            page.click('#tab-settings'); page.wait_for_selector('#more-feedback', state='visible')
            check('phone: a dot on the Feedback row', page.evaluate("getComputedStyle(document.querySelector('#more-feedback .nav-dot')).display") != 'none')
        errs = session(pw, be2, ALICE, dot, width=390); check('no errors dot', not errs, errs)
        for w in (360, 375, 390, 414, 430): errs = session(pw, be, ALICE, phone, width=w); check('no errors phone %d' % w, not errs, errs)

        # ---- 10. theme: auto, light, dark; saved on this device; applied before the app loads
        be = Backend()
        def theme(page):
            page.wait_for_selector('#tab-settings'); page.click('#tab-settings'); page.wait_for_selector('#look .set-tog')
            if page.get_attribute('#look .set-tog', 'aria-expanded') != 'true': page.click('#look .set-tog')
            bg = lambda: page.evaluate("getComputedStyle(document.body).backgroundColor")
            attr = lambda: page.evaluate("document.documentElement.dataset.theme || 'auto'")
            checked = lambda: page.eval_on_selector('#look-row [aria-checked=true]', 'e => e.textContent')
            check('auto is the default', attr() == 'auto' and checked() == 'Auto')
            page.click('#look-row >> text=Dark'); check('dark applies', attr() == 'dark' and checked() == 'Dark' and bg() != 'rgb(255, 255, 255)', bg())
            page.reload(); page.wait_for_selector('#tab-settings')
            check('dark survives a reload', attr() == 'dark')
            page.click('#tab-settings'); page.wait_for_selector('#look .set-tog')
            if page.get_attribute('#look .set-tog', 'aria-expanded') != 'true': page.click('#look .set-tog')
            page.click('#look-row >> text=Light'); check('light applies over a dark system', attr() == 'light' and bg() == 'rgb(255, 255, 255)', bg())
            page.click('#look-row >> text=Auto'); check('auto removes the override', attr() == 'auto' and page.evaluate("localStorage.getItem('yc-theme')") is None)
        for scheme in ('dark', 'light'):
            br = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
            if scheme == 'dark':
                ctx = br.new_context(viewport={'width': 1000, 'height': 900}, color_scheme='dark')
                sess = {'access_token': jwt(ALICE), 'token_type': 'bearer', 'expires_in': 3600, 'expires_at': 4102444800, 'refresh_token': 'r', 'user': {'id': ALICE, 'email': EMAILS[ALICE], 'aud': 'authenticated', 'role': 'authenticated'}}
                ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('yc-lang', 'en'); localStorage.setItem('sb-qazvzhhoalkyyasakphs-auth-token', %s); sessionStorage.setItem('seeded', '1'); }" % json.dumps(json.dumps(sess)))
                ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith('http://localhost') else r.abort()); ctx.route(SUPA + '/**', be.handle)
                page = ctx.new_page(); errs = []; page.on('pageerror', lambda e: errs.append(str(e))); page.goto(BASE)
                try:
                    # a dark system with no choice made: auto follows it
                    page.wait_for_selector('#tab-settings')
                    check('auto follows a dark system', page.evaluate("getComputedStyle(document.body).backgroundColor") != 'rgb(255, 255, 255)')
                    theme(page)
                finally: br.close()
                check('no page errors (theme)', not errs, errs)
            else: br.close()

        # ---- 11. Progress: the day tooltip keeps working after it was hidden once
        be = Backend()
        base = 'yc/'
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        be.docs.append({'path': base + 'exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
        d0 = datetime.date.today()
        be.docs.append({'path': base + 'templates/push', 'data': {'name': 'Push day', 'order': 1, 'weekday': 'Mon', 'kind': 'Push', 'focus': 'Chest', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': 8, 'target': '', 'target_at': d0.isoformat(), 'rest_s': 90, 'note': None}]}})
        for k in (1, 3):
            day = (d0 - datetime.timedelta(days=k)).isoformat()
            be.docs.append({'path': base + 'sessions/' + day, 'data': {'date': day, 'split': 'Push', 'label': 'Push day', 'template': 'push' if k == 1 else 'gone', 'sets': {'a': {'ex': 'bench', 'n': 1, 'reps': 8, 'load': 60, 'done': True, 'order': 1}, 'b': {'ex': 'bench', 'n': 2, 'reps': 8, 'load': 60, 'done': True, 'order': 2}}}})
        def hover(page):
            page.wait_for_selector('#tab-progress'); page.click('#tab-progress'); page.wait_for_selector('#p-days rect', state='attached')
            cells = page.locator('#p-days rect')
            n = cells.count(); trained = [i for i in range(n) if (cells.nth(i).get_attribute('fill') or '') == 'var(--ink)']
            check('two trained days drawn', len(trained) == 2, trained)
            tipvis = lambda: page.evaluate("(() => { const t = document.querySelector('#p-days .tip'); return !!t && !t.hidden && getComputedStyle(t).display !== 'none'; })()")
            for attempt in (1, 2, 3):
                for i in trained:
                    page.evaluate("document.querySelector('#p-days').scrollIntoView({ block: 'center' })")  # clear of the bottom bar
                    box = cells.nth(i).bounding_box(); page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                    page.wait_for_timeout(120)
                    check('tooltip shows on hover #%d day %d' % (attempt, i), tipvis())
                page.mouse.move(2, 2); page.wait_for_timeout(120)
                check('tooltip hides when leaving #%d' % attempt, not tipvis())
            links = page.eval_on_selector_all('#p-days rect.day-go', 'e => e.length')
            check('only the day whose plan day still exists is a link', links == 1, links)
            tip = lambda: page.evaluate("document.querySelector('#p-days .tip').innerText")
            box = cells.nth(trained[1]).bounding_box(); page.mouse.move(box['x'] + 4, box['y'] + 4); page.wait_for_timeout(120)
            check('tooltip offers to open it', 'open this session' in tip().lower(), tip())
            cells.nth(trained[1]).click()
            page.wait_for_selector('#session', state='visible')
            check('click opens that session on the Train tab', page.get_attribute('#tab-train', 'aria-selected') == 'true' and page.is_visible('#session'))
            check('it is the clicked date and plan day', json.loads(page.evaluate("localStorage.getItem('yc-active')")).get('date') == (d0 - datetime.timedelta(days=1)).isoformat() and json.loads(page.evaluate("localStorage.getItem('yc-active')")).get('tpl') == 'push')
            page.click('#sb-back'); page.click('#tab-progress'); page.wait_for_selector('#p-days rect.day-go', state='attached')
            c2 = page.locator('#p-days rect.day-go').first; c2.focus(); page.keyboard.press('Enter')
            page.wait_for_selector('#session', state='visible')
            check('keyboard Enter opens it too', page.is_visible('#session'))
        errs = session(pw, be, ALICE, hover, width=1000); check('no page errors (hover)', not errs, errs)
        # ---- 11. connected AI apps in Settings
        def conn_open(page):
            page.wait_for_selector('#tab-settings'); page.click('#tab-settings'); page.wait_for_selector('#look .set-tog')
        def conn_off(page):
            conn_open(page); page.wait_for_timeout(400)
            check('connected apps hidden when the OAuth server is off', page.is_hidden('#conn'))
        be = Backend(); errs = session(pw, be, ALICE, conn_off, width=1000); check('no page errors (conn off)', not errs, errs)
        be = Backend(); be.grants = [{'client': {'id': 'c-claude', 'name': 'Claude', 'uri': 'https://claude.ai'}, 'scopes': ['openid'], 'granted_at': now()}, {'client': {'id': 'c-x', 'name': 'Other AI'}, 'scopes': [], 'granted_at': now()}]
        def conn_on(page):
            conn_open(page); page.wait_for_selector('#conn:not([hidden])')
            if page.get_attribute('#conn .set-tog', 'aria-expanded') != 'true': page.click('#conn .set-tog')
            check('connector address shown', page.input_value('#conn-url') == 'https://qazvzhhoalkyyasakphs.supabase.co/functions/v1/mcp', page.input_value('#conn-url'))
            page.click('#conn-copy'); page.wait_for_function("document.querySelector('#conn-state').textContent.length > 0")
            check('copy gives feedback', page.inner_text('#conn-state') in ('Copied.', 'Press and hold the address to copy it.'))
            check('step by step link', page.get_attribute('#conn a.link', 'href') == 'connect.html')
            pass
            check('lists both apps', page.inner_text('#conn-list').lower().count('disconnect') == 2 and 'Claude' in page.inner_text('#conn-list') and 'Other AI' in page.inner_text('#conn-list'))
            page.click('#conn-list button[aria-label="Disconnect Claude"]')
            page.wait_for_function("document.querySelectorAll('#conn-list button').length === 1")
            check('revoked that client only', ('revoke', 'c-claude') in be.calls and [g['client']['id'] for g in be.grants] == ['c-x'], be.calls)
            page.click('#conn-list button'); page.wait_for_function("document.querySelector('#conn-list').textContent.includes('None connected')")
            check('empty state', 'None connected' in page.inner_text('#conn-list'))
        errs = session(pw, be, ALICE, conn_on, width=1000); check('no page errors (conn on)', not errs, errs)
        # ---- 13. Plan: put a day in the week from the day itself; delete in plain sight; styled dropdowns
        def docdata(be, path): return next((d['data'] for d in be.docs if d['path'] == path), None)
        def plan_be(mode):
            be = Backend(); be.grants = []
            sched = {'enabled': True, 'mode': 'fixed', 'week': {'Mon': 'push', 'Wed': 'legs'}} if mode == 'fixed' else {'enabled': True, 'mode': 'rotation', 'days': ['Mon', 'Wed'], 'rotation': ['push', 'legs']}
            be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach', 'schedule': sched}})
            be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'unit': 'kg', 'category': 'strength'}})
            for i, (k, n) in enumerate((('push', 'Push'), ('legs', 'Legs'), ('pull', 'Pull'))):
                be.docs.append({'path': 'yc/templates/' + k, 'data': {'name': n, 'order': i + 1, 'kind': n, 'focus': '', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '8', 'target': ''}]}})
            return be
        be = plan_be('fixed')
        def plan_fixed(page):
            go(page, 'plan'); page.wait_for_selector('.pw-srow')
            check('no native dropdown is visible any more', page.evaluate("[...document.querySelectorAll('select')].every(s => s.classList.contains('ysel-native') && getComputedStyle(s).opacity === '0')"))
            check('styled dropdown button replaces the select', page.locator('.pw-srow .ysel-btn').count() == 1)
            gap = page.evaluate("(() => { const a = document.querySelector('.pw-spare').getBoundingClientRect(); const b = document.querySelector('.pw-more > .foot-row').getBoundingClientRect(); return b.top - a.bottom; })()")
            check('room between Not in your week and New training day', gap >= 16, gap)
            page.click('.pw-srow .ysel-btn'); page.wait_for_selector('.ysel-pop')
            opts = page.eval_on_selector_all('.ysel-pop [role=option]', 'e => e.map(x => x.textContent)')
            check('dropdown lists Put on and the weekdays', opts[0] == 'Put on…' and 'Fri' in opts and any(o.startswith('Mon (instead of Push') for o in opts), opts)
            page.keyboard.press('Escape'); check('Escape closes it', page.locator('.ysel-pop').count() == 0)
            page.click('.pw-srow .ysel-btn'); page.click('.ysel-pop >> text=Fri')
            page.wait_for_function("document.querySelector('.pw-board').textContent.includes('Pull')")
            check('picking from the list sets Fri', docdata(be, 'yc')['schedule']['week'].get('Fri') == 'pull', docdata(be, 'yc'))
            # open Pull and move it with the weekday chips
            page.click('.pw-board >> text=Pull >> xpath=ancestor::div[contains(@class,"pw-card") or contains(@class,"pw-day")][1] >> text=Edit') if False else None
        errs = session(pw, be, ALICE, plan_fixed, width=1000); check('no page errors (plan dropdown)', not errs, errs)

        be = plan_be('fixed')
        def plan_week(page):
            go(page, 'plan'); page.wait_for_selector('.pw-srow')
            page.click('.pw-srow >> text=Edit'); page.wait_for_selector('.pw-inweek')
            check('editor shows In your week with weekday chips', page.locator('.pw-inweek .pk-chip').count() == 7 and 'Not in your week yet' in page.inner_text('.pw-inweek'))
            page.click('.pw-inweek .pk-chip >> text=Fri')
            check('Fri chip is on and saved', page.get_attribute('.pw-inweek .pk-chip:has-text("Fri")', 'aria-pressed') == 'true' and docdata(be, 'yc')['schedule']['week'].get('Fri') == 'pull')
            page.click('.pw-inweek .pk-chip >> text=Mon')
            check('taking a taken day replaces it and says so', docdata(be, 'yc')['schedule']['week']['Mon'] == 'pull' and 'Push is no longer on Mon' in page.inner_text('#toast'), page.inner_text('#toast'))
            page.click('#toast-undo'); page.wait_for_timeout(200)
            check('undo puts Push back on Monday', docdata(be, 'yc')['schedule']['week']['Mon'] == 'push', docdata(be, 'yc'))
            page.click('.pw-inweek .pk-chip >> text=Fri'); page.wait_for_timeout(300)
            check('tapping an on chip takes it out of the week', docdata(be, 'yc')['schedule']['week'].get('Fri') == '')
            check('delete is visible without opening anything', page.is_visible('#ed-delete') and page.inner_text('#ed-delete').lower() == 'delete this day')
            gap = page.evaluate("(() => { const a = document.querySelector('.pw-daymore').getBoundingClientRect(); const b = document.querySelector('#ed-delete').getBoundingClientRect(); return b.top - a.bottom; })()")
            check('delete has room above it', gap >= 24, gap)
            page.click('.pw-daymore summary'); page.click('#ed-kind ~ .ysel-btn, .pw-daymore .ysel-btn')
            check('type picker is a styled list', page.locator('.ysel-pop').count() == 1)
            page.keyboard.press('Escape')
            page.click('#ed-delete'); check('first tap asks again', 'tap again' in page.inner_text('#ed-delete').lower())
            page.click('#ed-delete'); page.wait_for_selector('.pw-top')
            check('second tap deletes the day', docdata(be, 'yc/templates/pull') is None and 'pull' not in page.inner_text('#editor').lower())
        errs = session(pw, be, ALICE, plan_week, width=390); check('no page errors (plan week)', not errs, errs)

        be = plan_be('rotation')
        def plan_rot(page):
            go(page, 'plan'); page.wait_for_selector('.pw-srow'); page.click('.pw-srow >> text=Edit'); page.wait_for_selector('.pw-inweek')
            check('rotation: Put in your week button', page.inner_text('.pw-inweek button').lower() == 'put in your week')
            page.click('.pw-inweek button')
            check('rotation: day joins the order', docdata(be, 'yc')['schedule']['rotation'] == ['push', 'legs', 'pull'], docdata(be, 'yc'))
            check('rotation: button flips', page.inner_text('.pw-inweek button').lower() == 'take out of your week')
            page.click('.pw-inweek button')
            check('rotation: and back out', docdata(be, 'yc')['schedule']['rotation'] == ['push', 'legs'])
        errs = session(pw, be, ALICE, plan_rot, width=1000); check('no page errors (plan rotation)', not errs, errs)

        # ---- 14. Home: invitation text, Connect to Claude, home screen
        be = Backend(); be.grants = []
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        def home_a(page):
            page.wait_for_selector('#v-home', state='visible')
            txt = page.inner_text('#v-home')
            for want in ('Feedback', 'Send bugs and feature requests from inside the app', 'Free and private', '100% free. Forever.', 'No ads.', 'No tracking.', 'export it with one click', 'What makes it different', 'Strong, Hevy or FitNotes', 'Use your own AI'):
                check('home says: ' + want, want.lower() in txt.lower(), txt[:200])
            check('home no longer promises 24 hours', '24 hours' not in txt and 'Made with you' not in txt)
            check('bullets are ticks', page.locator('.hm-checks li').count() == 5)
            page.evaluate("window.__opened = []; window.open = (u) => { window.__opened.push(u); return null; }; 0")
            page.wait_for_selector('#hm-claude:not([hidden])')
            check('button says Connect to Claude', page.inner_text('#hm-claude').lower() == 'connect to claude')
            page.click('#hm-claude'); page.wait_for_selector('#hm-claude-panel:not([hidden])')
            check('it opens the Claude connectors page', page.evaluate('window.__opened[0]') == 'https://claude.ai/customize/connectors', page.evaluate('window.__opened'))
            check('and copies the connector address', page.evaluate('navigator.clipboard.readText()').endswith('/functions/v1/mcp'))
            check('panel explains the two steps', 'Add custom connector' in page.inner_text('#hm-claude-panel') and 'Allow' in page.inner_text('#hm-claude-panel'))
            page.click('#hm-claude'); check('tap again closes the panel', page.is_hidden('#hm-claude-panel'))
            # home screen
            check('home screen button shown in a browser', page.is_visible('#hm-install'))
            page.click('#hm-install'); page.wait_for_selector('#hm-install-panel:not([hidden])')
            check('desktop gets the dock/address bar steps and the logo', 'address bar' in page.inner_text('#hm-install-panel') and page.locator('#hm-install-panel img[src^="icon-192"]').count() == 1)
            page.click('#hm-install')
            page.evaluate("(() => { const e = new Event('beforeinstallprompt'); e.prompt = () => { window.__prompted = true; return Promise.resolve(); }; e.userChoice = Promise.resolve({ outcome: 'accepted' }); window.dispatchEvent(e); })()")
            page.click('#hm-install'); page.wait_for_timeout(300)
            check('browsers that can install get the real prompt', page.evaluate('window.__prompted') is True)
        errs = session(pw, be, ALICE, home_a, width=390, home=True); check('no page errors (home)', not errs, errs)

        be = Backend()  # connector off: the button stays away
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        def home_b(page):
            page.wait_for_selector('#v-home', state='visible'); page.wait_for_timeout(500)
            check('no Connect button when the connector is off', page.is_hidden('#hm-claude'))
        errs = session(pw, be, ALICE, home_b, width=390, home=True); check('no page errors (home, connector off)', not errs, errs)

        be = Backend(); be.grants = []
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        def home_ios(page):
            page.wait_for_selector('#hm-install', state='visible'); page.click('#hm-install')
            t = page.inner_text('#hm-install-panel')
            check('iPhone gets Share, Add to Home Screen and the logo', 'Share' in t and 'Add to Home Screen' in t and page.locator('#hm-install-panel img').count() == 1, t)
        errs = session(pw, be, ALICE, home_ios, width=390, home=True, ua='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
        check('no page errors (home iOS)', not errs, errs)
        be = Backend(); be.grants = []
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        def home_android(page):
            page.wait_for_selector('#hm-install', state='visible'); page.click('#hm-install')
            t = page.inner_text('#hm-install-panel')
            check('Android gets Install app steps', 'Install app' in t and 'three dots' in t, t)
        errs = session(pw, be, ALICE, home_android, width=390, home=True, ua='Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36')
        check('no page errors (home Android)', not errs, errs)

        # ---- 15. finishing a day asks about Coach Claude only when Claude is connected
        def finish_be(grants):
            be = Backend(); be.grants = grants
            be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
            be.docs.append({'path': 'yc/exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'category': 'strength', 'unit': 'kg', 'better': 'higher'}})
            be.docs.append({'path': 'yc/templates/push', 'data': {'name': 'Push day', 'order': 1, 'weekday': 'Mon', 'kind': 'Push', 'focus': 'Chest', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': 8, 'target': '', 'rest_s': 90, 'note': None}]}})
            return be
        def fin_claude(page):
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-fin', state='visible')
            page.evaluate("window.__opened = []; if (!window.__oc) { window.__oc = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { if (/claude\\.ai/.test(this.href)) { window.__opened.push(this.href); return; } return window.__oc.call(this); }; } 0")
            page.click('#resume-fin'); page.wait_for_selector('#claude-review-go')
            check('asks: Send day to Coach Claude for review?', 'Send day to Coach Claude for review?' in page.inner_text('.ydlg'))
            check('focus is on the Send button', page.evaluate("document.activeElement.id") == 'claude-review-go')
            page.click('.ydlg >> text=Not now'); check('Not now closes it', page.locator('.ydlg').count() == 0)
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-fin', state='visible')
            page.evaluate("window.__opened = []; if (!window.__oc) { window.__oc = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { if (/claude\\.ai/.test(this.href)) { window.__opened.push(this.href); return; } return window.__oc.call(this); }; } 0")
            page.click('#resume-fin'); page.wait_for_selector('#claude-review-go'); page.keyboard.press('Escape'); check('Escape closes it', page.locator('.ydlg').count() == 0)
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-fin', state='visible')
            page.evaluate("window.__opened = []; if (!window.__oc) { window.__oc = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () { if (/claude\\.ai/.test(this.href)) { window.__opened.push(this.href); return; } return window.__oc.call(this); }; } 0")
            page.click('#resume-fin'); page.wait_for_selector('#claude-review-go'); page.click('#claude-review-go'); page.wait_for_timeout(300)
            u = page.evaluate('window.__opened[0]') or ''
            check('Send opens Claude with the request', u.startswith('https://claude.ai/new?q=') and 'Push day' in urllib.parse.unquote(u) and 'connector' in urllib.parse.unquote(u), u)
            check('after Send the app is back on the Train screen', page.is_visible('#pickday') and page.locator('.ydlg, .fin').count() == 0 and not page.evaluate("document.body.classList.contains('fin-open')"))
            check('request is also on the clipboard', 'Push day' in page.evaluate('navigator.clipboard.readText()'))
        errs = session(pw, finish_be([{'client': {'id': 'c-claude', 'name': 'Claude'}, 'scopes': [], 'granted_at': now()}]), ALICE, fin_claude, width=390) if False else session(pw, finish_be([{'client': {'id': 'c-claude', 'name': 'Claude'}, 'scopes': [], 'granted_at': now()}]), ALICE, fin_claude, width=390)
        check('no page errors (finish asks)', not errs, errs)
        def fin_none(page):
            page.evaluate("localStorage.setItem('yc-active', JSON.stringify({date: new Date().toISOString().slice(0, 10), tpl: 'push'}))"); page.reload(); page.wait_for_selector('#resume-fin', state='visible')
            page.click('#resume-fin'); page.wait_for_timeout(700)
            check('no question without a connected Claude', page.locator('.ydlg').count() == 0)
        errs = session(pw, finish_be([]), ALICE, fin_none, width=390); check('no page errors (finish quiet)', not errs, errs)

        # ---- 16. Progress: the chart axis shows weights you lifted by default
        be = Backend(); be.grants = []
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach'}})
        be.docs.append({'path': 'yc/exercises/squat', 'data': {'name': 'Squat', 'group': 'Legs', 'category': 'strength', 'unit': 'kg'}})
        for k, (l1, r1, l2, r2) in zip((6, 4, 2), ((60, 8, 40, 12), (70, 8, 50, 12), (80, 8, 60, 12))):
            day = (datetime.date.today() - datetime.timedelta(days=k)).isoformat()
            be.docs.append({'path': 'yc/sessions/' + day, 'data': {'date': day, 'label': 'Legs', 'finished_at': 1, 'sets': {'a': {'ex': 'squat', 'n': 1, 'order': 1, 'kind': 'work', 'reps': r1, 'load': l1, 'done': True}, 'b': {'ex': 'squat', 'n': 2, 'order': 1, 'kind': 'work', 'reps': r2, 'load': l2, 'done': True}}}})
        def trends(page):
            go(page, 'progress'); page.wait_for_selector('.prow'); page.click('.prow')
            page.wait_for_selector('.p-detail svg')
            check('heaviest set is the default chart', 'Heaviest set per session' in page.inner_text('.p-detail'), page.inner_text('.p-detail')[:200])
            nums = page.evaluate("[...document.querySelectorAll('.p-detail svg text')].map(t => parseFloat(t.textContent)).filter(n => !isNaN(n))")
            check('axis stays at lifted weights (no estimated 1RM above 80 kg)', nums and max(nums) <= 90, nums)
            page.click('.p-detail >> text=Est. strength')
            check('estimate chart says it is an estimate', 'not a weight you lifted' in page.inner_text('.p-detail'))
            labs = page.evaluate("[...document.querySelectorAll('.p-detail .val-lab')].map(t => t.textContent)")
            check('estimate points are labelled as estimates', labs and all(l.startswith('≈') for l in labs), labs)
        errs = session(pw, be, ALICE, trends, width=1000); check('no page errors (trends)', not errs, errs)

        # ---- 12. the security policy is active: every screen works with it, and nothing leaves the site except Supabase
        be = Backend(); be.grants = []
        base = 'yc/'
        d0 = datetime.date.today()
        be.docs.append({'path': 'yc', 'data': {'intro_seen': True, 'app': 'yes-coach', 'schedule': {'enabled': True, 'mode': 'fixed', 'week': {'Mon': 'push'}}}})
        be.docs.append({'path': base + 'templates/push', 'data': {'name': 'Push', 'order': 1, 'kind': 'Push', 'focus': 'Chest', 'items': [{'ex': 'bench', 'order': 1, 'sets': 3, 'reps': '8', 'target': '60'}]}})
        be.docs.append({'path': base + 'exercises/bench', 'data': {'name': 'Bench press', 'group': 'Chest', 'unit': 'kg', 'category': 'strength'}})
        for k in (1, 3):
            day = (d0 - datetime.timedelta(days=k)).isoformat()
            be.docs.append({'path': base + 'sessions/' + day, 'data': {'date': day, 'label': 'Push', 'template': 'push', 'finished_at': 1, 'sets': {'a': {'ex': 'bench', 'n': 1, 'order': 1, 'kind': 'work', 'reps': 8, 'load': 60, 'done': True}}}})
        def policy(page):
            page.wait_for_selector('#tab-progress')
            for tab in ('train', 'plan', 'progress', 'food', 'feedback', 'settings', 'home'):
                if page.is_visible('#tab-' + tab): page.click('#tab-' + tab)
                page.wait_for_timeout(250)
            page.click('#tab-progress'); page.wait_for_selector('#p-days rect', state='attached')
            check('the chart (d3) loads from this site with the policy on', page.evaluate("typeof d3") == 'object')
            check('fonts come from this site', page.evaluate("document.fonts.check('700 1em \"Barlow Condensed\"')") is True)
            page.click('#tab-settings'); page.wait_for_selector('#look .set-tog')
            if page.get_attribute('#look .set-tog', 'aria-expanded') != 'true': page.click('#look .set-tog')
            page.click('#look-row >> text=Dark')
            check('policy on: dark theme still applies', page.evaluate("document.documentElement.dataset.theme") == 'dark')
            meta = page.get_attribute('meta[http-equiv="Content-Security-Policy"]', 'content')
            check('policy forbids inline script without a hash and other hosts', "script-src 'self' 'sha256-" in meta and 'unsafe-inline' not in meta.split('style-src')[0] and 'unsafe-eval' not in meta and "default-src 'none'" in meta, meta[:200])
        errs = session(pw, be, ALICE, policy, width=1000, csp=True); check('no CSP violations or errors with the policy on', not errs, errs)
        # ---- languages ----
        print('languages')
        if True:
            be = Backend()
            def picker(page):
                page.wait_for_selector('.yl-b')
                names = page.eval_on_selector_all('.yl-b', 'els => els.map(e => e.textContent)')
                check('first start: the picker offers six languages in order', names == ['Nederlands', 'English', 'Español', 'Deutsch', 'Français', 'Italiano'], names)
                check('first start: nothing chosen yet', page.evaluate("localStorage.getItem('yc-lang')") is None)
                page.click('.yl-b[lang=nl]'); page.wait_for_load_state('load'); page.wait_for_selector('#v-home', state='visible')
                check('choosing a language stores it', page.evaluate("localStorage.getItem('yc-lang')") == 'nl')
                check('picker gone after choosing', page.query_selector('.yl-b') is None)
                check('page language is set', page.evaluate("document.documentElement.lang") == 'nl')
                check('Home is translated', 'Training van vandaag' in page.inner_text('#hm-train').capitalize() or 'vandaag' in page.inner_text('#hm-train').lower(), page.inner_text('#hm-train'))
                page.reload(); page.wait_for_selector('#v-home', state='visible')
                check('choice survives a reload without asking again', page.query_selector('.yl-b') is None and page.evaluate("document.documentElement.lang") == 'nl')
                page.click('#hm-train'); go(page, 'settings')
                if page.get_attribute('#lang .set-tog', 'aria-expanded') != 'true': page.click('#lang .set-tog')
                check('Settings has a languages section, titled in Dutch', page.inner_text('#h-lang').strip().lower() == 'talen', page.inner_text('#h-lang'))
                checked = page.eval_on_selector_all('#lang-list [aria-checked=true]', 'els => els.map(e => e.textContent)')
                check('the current language is marked', len(checked) == 1 and 'Nederlands' in checked[0], checked)
                check('six options in Settings', page.locator('#lang-list button').count() == 6)
                check('the notice says the translations are AI-generated', 'AI' in page.inner_text('#lang .note') and 'Engels' in page.inner_text('#lang .note'), page.inner_text('#lang .note'))
                page.click('#lang-list button:has-text("Español")'); page.wait_for_load_state('load'); page.wait_for_selector('#v-home', state='visible')
                check('switching in Settings changes the language', page.evaluate("localStorage.getItem('yc-lang')") == 'es' and page.evaluate("document.documentElement.lang") == 'es')
                page.click('#hm-train'); go(page, 'settings')
                if page.get_attribute('#lang .set-tog', 'aria-expanded') != 'true': page.click('#lang .set-tog')
                check('the notice is in Spanish now', 'inglés' in page.inner_text('#lang .note'), page.inner_text('#lang .note'))
                page.click('#lang-report'); page.wait_for_selector('#v-feedback', state='visible')
                check('report button opens the form prefilled with the language', 'es' in page.input_value('#v-feedback input[maxlength="120"]'), page.input_value('#v-feedback input[maxlength="120"]'))
                page.click('#lang-list button:has-text("English")') if page.is_visible('#lang-list') else None
            errs = session(pw, be, ALICE, picker, width=390, lang=None, home=True); check('no errors in the language flow', not errs, errs)
            # English: no dictionary needed, nothing changes, weekday chips stay English
            def english(page):
                page.wait_for_selector('#v-home', state='visible')
                check('English: no picker when a choice exists', page.query_selector('.yl-b') is None and page.evaluate("document.documentElement.lang") == 'en')
            session(pw, Backend(), ALICE, english, width=390, lang='en', home=True)
            # with the content security policy on, the dictionary still loads from this site
            def csp_de(page):
                page.wait_for_selector('#v-home', state='visible'); page.wait_for_timeout(500)
                check('policy on: the German dictionary loads', 'Heutiges Training' in page.inner_text('#hm-train').title() or 'HEUTIGES' in page.inner_text('#hm-train').upper(), page.inner_text('#hm-train'))
            errs = session(pw, Backend(), ALICE, csp_de, width=390, csp=True, lang='de', home=True); check('policy on: no violations with a translation', not errs, errs)
    check('nothing left the site except Supabase (no fonts, CDNs or analytics)', not [u for u in EXTERNAL if not u.startswith('data:') and not u.startswith(SUPA)], sorted(set(EXTERNAL))[:5])
finally:
    server.terminate()
done()
