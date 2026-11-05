# Yes Coach! web app

A free, ad-free workout tracker. Static site on GitHub Pages, accounts and data in Supabase.

## Files

| File | What it is |
|---|---|
| `index.html` | The app. Built from `src/yes-coach.html` by `build.py`; do not edit by hand. |
| `web.js` | Sign-in screen and the storage layer (Supabase behind the app's data interface). |
| `config.js` | Your Supabase project URL and public key, the app address and a contact email. |
| `schema.sql` | The database: one table, row-level security, merge and delete-account functions. |
| `tickets.sql` | Feedback & Requests tab: tickets, thread, owner functions and their row-level security. Run after `schema.sql`. |
| `connector.sql` | Run last. Keeps a connected AI app inside its bounds in the database itself. |
| `connect.html` | Public setup and usage page for the connector (the directory listing links to it). |
| `consent.html` | The screen where a person allows or denies an AI app (the connector's sign-in step). |
| `supabase/functions/mcp/` | The connector: an MCP server, one file, deployed as a Supabase Edge Function. `supabase/tests/mcp.test.mjs` tests it. |
| `demo.js` | The sample workout: a small plan and two earlier sessions. `web.js` loads them into memory when the page is opened with `?demo` (the "See a sample workout" buttons on the start page). Nothing is written to the database or the device. |
| `tickets.js` | The Feedback & Requests tab: send, follow, the "done" pop-up, and the owner's ticket bar. |
| `vendor/` | The Supabase client library and d3 (charts), so the app has no runtime dependency on a CDN. |
| `fonts/` | Barlow and Barlow Condensed (SIL Open Font License), served from this site instead of Google Fonts. |
| `manifest.webmanifest`, `icon-*.png` | Install to home screen. |
| `privacy.html` | Privacy page, linked from sign-in and Settings. |

## One-time setup

1. **Supabase** (supabase.com, free plan): New project, region *Central EU (Frankfurt)*, any strong database password.
   - SQL Editor → New query → paste all of `schema.sql` → Run.
   - Authentication → Sign In / Providers → Email: enabled; turn **Confirm email off** (the free plan sends only a few emails an hour; with it off, sign-up needs no email).
   - Authentication → URL Configuration: Site URL = your app address; add the same address under Redirect URLs.
   - Project Settings → API: copy the Project URL and the publishable key (`sb_publishable_…`, or the legacy `anon` key) into `config.js`. Never put the secret key anywhere in this app.
   - Then run all of `tickets.sql` the same way. After you have created your own account in the app, make yourself the owner (this unlocks the Tickets bar at the top of the Feedback & Requests tab):
     `insert into public.admins (user_id) select id from auth.users where email = 'you@example.com';`
   - Updating an existing install: run `tickets.sql` again. It is safe to repeat and adds anything new.
2. **GitHub**: repository `yes-coach` (public). Push these files to `main`. Settings → Pages → Deploy from a branch → `main` / root.
3. Fill in `appUrl` (for example `https://<you>.github.io/yes-coach/`) and `contactEmail` in `config.js`.
4. Open the app, create your account, Settings → Backup and restore → pick your backup file.

## Security

What the code enforces:
- **Data access:** row-level security on every table (`schema.sql`, `tickets.sql`); a connected AI app is limited further by `connector.sql`. Functions that run with owner rights pin their `search_path` and check who is calling.
- **Pages:** `build.py` gives `index.html`, `consent.html`, `connect.html` and `privacy.html` a content security policy (inline scripts only by hash, connections only to this site and Supabase) and a frame guard so the consent screen cannot be framed. The only outside host is Cloudflare Turnstile, and only on the sign-in and consent screens (site key in `config.js`, secret in Supabase). Re-run `python3 build.py` after changing any inline script; it recomputes the hashes.
- **Limits:** 256 KB per document and 20,000 documents per account (`schema.sql`); the connector refuses requests over 200 KB.
- **Tests:** `sh tests/run.sh` runs all of them (see Tests below), among them the check that the deep merge cannot pollute `Object.prototype` and the connector tests.

Set in the Supabase dashboard (code cannot do these):
- Authentication, Attack Protection: turn on CAPTCHA with provider Cloudflare Turnstile and the secret key. The app already sends the token (`captcha.js`). Sign-up is open and email confirmation is off, so bots can create accounts.
- Authentication, Providers, Email: minimum password length 8 or more.
- Authentication, URL Configuration: only your app address under Redirect URLs, no wildcards.
- Advisors, Security Advisor: run it after each SQL change and fix anything it flags. What stays flagged on purpose: `is_admin`, `admin_set_ticket`, `admin_reply`, `admin_delete_ticket`, `delete_me` and `user_count` are callable because the app calls them that way (`user_count` also by people who are not signed in: the sign-in screen shows the number) (the admin ones check `is_admin()` inside, `delete_me` only touches the caller's own rows). "Leaked password protection" needs the Pro plan.
- Keep the secret (`service_role`) key out of this repo, the app and the function. Only the public key is used.

## Shipping an update

Change `src/yes-coach.html` (the same file runs the claude.ai version), run `python3 build.py`, commit and push. GitHub Pages serves it within a minute or two; people get it on their next load.

## Before the public launch

- Add a contact email in `config.js` (`contactEmail`); the privacy page shows it.
- Set up a custom email sender (see below) and consider turning Confirm email back on.

## Connector (an AI app reads your data and changes your plan)

People connect their own AI app (Claude, for example) to their Yes Coach! account. The AI can read the plan, log and notes, and change training days, the weekly schedule and exercises, and answer notes. It can not touch logged sets. Sign-in is Supabase's OAuth server; each person allows an app on `consent.html`.

One-time setup, in this order:

1. **Database.** Run `schema.sql` again, then `tickets.sql` again, then `connector.sql` (all safe to repeat). `connector.sql` is what makes "can not" true: Supabase gives an OAuth token the user's full access unless policies say otherwise, so a connected app is limited to reading, and to writing the plan and notes, in the database itself.
2. **Supabase OAuth server** (beta). Authentication → OAuth Server: enable it, switch on **Allow dynamic OAuth apps** (Claude registers itself), and set the **Authorization Path** to `consent.html` (with Site URL = your app address). Open `https://<project>.supabase.co/.well-known/oauth-authorization-server/auth/v1` once; it should show JSON. After the first connect attempt, check where the browser lands: it must be `<appUrl>consent.html?authorization_id=…`. If the path or Site URL join comes out wrong (for example without `/yes-coach/`), adjust the path until it matches.
3. **Function.** With the Supabase CLI (`npm i -g supabase`, `supabase login`): `supabase functions deploy mcp --project-ref <project> --no-verify-jwt`. (Dashboard alternative: Edge Functions → Deploy a new function → name `mcp`, paste `supabase/functions/mcp/index.ts`, and switch **Verify JWT** off.) If tools answer "The database said no (401)", add a secret `YC_ANON_KEY` with the publishable key from `config.js`.
4. **Add it in Claude.** Settings → Connectors → Add custom connector → URL `https://<project>.supabase.co/functions/v1/mcp`. Claude sends you to `consent.html`; sign in, Allow. Ask: "What is in my Yes Coach plan?"

People disconnect an app in the app under Settings, Connected AI apps. Tests: `node --experimental-strip-types --no-warnings supabase/tests/mcp.test.mjs`.

## Later

- Before many people use *Forgot password*: add a custom email sender (Authentication → Emails → SMTP, for example Resend's free plan), because the built-in one is limited to a few emails an hour.

## Food data

Food search loads `foods-nevo.json` and `foods-usda.json` the first time someone searches in Food.

- NEVO: NEVO online version 2025/9.0, RIVM, Bilthoven. Values used unchanged; the app shows the required line "Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources". Conditions: no charging users, replace with each new NEVO release.
- USDA FoodData Central, SR Legacy (public domain).

Rebuild after a new release: `python3 tools/build_foods.py <NEVO20xx.csv> <USDA sr_legacy csv folder>` (keep the raw NEVO files out of this repo).
- Portie-online versie 2026/2.0, RIVM, Bilthoven: household measures per NEVO code in `portions-nevo.json` (used unchanged, packaging sizes left out). Full table: `Portie-online 2026-2.0.xlsx` in the Yes Coach folder.

## Tests

```bash
sh tests/run.sh
```

It checks that the built files are current (`python3 build.py --check`), rebuilds, runs the unit tests (merge, plates, progression, and the connector in `supabase/tests/`), then every end-to-end suite in `tests/e2e/`, and exits 1 if any of them fails. The end-to-end suites drive the built app in headless Chrome with Playwright, with Supabase faked in memory (`harness.py`: fake backend, local web server, browser launch; `signedout.py`: the signed-out pages and the Turnstile stand-in). They need Python with `playwright` and Node 22. Chrome is expected at `/usr/bin/google-chrome`; set `CHROME` to use another binary. One suite alone: `cd tests/e2e && python3 e2e_train.py`.

Translations: see `tools/i18n/README.md`.
