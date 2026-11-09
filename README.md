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
| `push.sql`, `push.js`, `sw.js` | Rest alerts (optional): the tables, the web app's side, and the service worker that shows the notification. `supabase/functions/rest-push/` sends it; `tools/vapid.mjs` makes the keys. |
| `connect.html` | Public setup and usage page for the connector (the directory listing links to it). |
| `consent.html` | The screen where a person allows or denies an AI app (the connector's sign-in step). |
| `supabase/functions/mcp/` | The connector: an MCP server, one file, deployed as a Supabase Edge Function. `supabase/tests/mcp.test.mjs` tests it. |
| `tickets.js` | The Feedback & Requests tab: send, follow, the "done" pop-up, and the owner's ticket bar. |
| `vendor/` | The Supabase client library and d3 (charts), so the app has no runtime dependency on a CDN. |
| `fonts/` | Barlow and Barlow Condensed (SIL Open Font License), served from this site instead of Google Fonts. |
| `manifest.webmanifest`, `icon-*.png` | Install to home screen. |
| `privacy.html` | Privacy page, linked from sign-in and Settings. |
| `CONTRIBUTING.md` | How to work on the app: what to edit, the build, the tests, design and translation rules, the connector deploy. |

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
- **Tests:** `node tests/merge.test.mjs` (deep merge cannot pollute `Object.prototype`), `node --experimental-strip-types --no-warnings supabase/tests/mcp.test.mjs` (connector).

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

## Connector (an AI app reads your data, changes your plan and logs your food)

People connect their own AI app (Claude, for example) to their Yes Coach! account. The AI can read the plan, log and notes, change training days, the weekly schedule and exercises, answer notes, add sets to the log and remove sets from it, and log meals and remove food entries. It can not edit a set or delete a session.

The weekly schedule in rotation mode (`schedule: { mode: "rotation", days, rotation, per_week }`) treats `days` as the weekdays the person can train and `per_week` (optional, else the profile's `days_per_week`) as how many sessions a week; with fewer sessions than days they are spread evenly over the days, so the same weekdays are not needed every week. `set_schedule` takes `sessions_per_week`. Custom workouts (Train, Change today's workout) start blank and are logged under a hidden training day `yc/templates/custom-<date>` with `adhoc: true`; it names the session but is never part of the plan, so `get_plan` leaves it out. Run sets (exercises named run or jog, and the library's Treadmill run and Outdoor run) also carry `km`, `elev` (altitude gain in m) and `where` (`outdoor` or `treadmill`); `get_sessions` returns them with the pace.

Food: the AI searches the same NEVO and USDA tables the app uses (`search_foods`) and logs meals as food ids with grams or a portion (`log_meals`); the nutrients are read from those tables, never typed by the AI. Foods that are not in the tables (home-made, branded) are the person's own: numbers per 100 g or 100 ml, saved by the person in the app (Food, Create your own food) or by the AI (`save_custom_food`: the numbers on the package, or on the product's own page when the person asks it to look a product up on the internet; the connector does not search the web, the AI does, and the page goes in `source`) as `yc/myfoods/own-<name>` = `{ food: "own:<name>", name, own: { kcal, p, c, f, u }, source, aka, portions, n, last }`. Calories that are far from what the macros add up to come back with a `check` note, since that is what a per-serving number looks like. They are searched, logged and remembered like any table food, with `src: "own"` on the entry. A meal with several foods is one entry with an `items` list. Foods that get logged are remembered (`yc/myfoods/<id>`: how often, the words the person used, their own portion sizes) and a search lists them first; usual meals are saved as `yc/meals/<id>` (`save_meal`, logged again by id or with one tap in the app). Forgetting or removing one writes `{ gone: true }`, since a connected app cannot delete a row. Without a date, "today" is the person's own day: the app saves the device's time zone in `settings.tz`, and the connector asks for a date until the app has saved it (it has no guess of its own). New days are created only when missing and then merged into, and a removed entry is set to `null` in one merge, so parallel calls and the app writing at the same moment never lose an entry. The function fetches `foods-nevo.json`, `foods-usda.json` and `portions-nevo.json` from the app's own site once per running copy; set the secret `YC_SITE_URL` if the app lives anywhere other than `https://godellovbp.github.io/yes-coach/`. Sign-in is Supabase's OAuth server; each person allows an app on `consent.html`.

One-time setup, in this order:

1. **Database.** Run `schema.sql` again, then `tickets.sql` again, then `connector.sql` (all safe to repeat). `connector.sql` is what makes "can not" true: Supabase gives an OAuth token the user's full access unless policies say otherwise, so a connected app is limited to reading, and to writing the plan, notes, food entries (`yc/food/`) and the person's own foods and saved meals (`yc/myfoods/`, `yc/meals/`), in the database itself. It can overwrite a day's food document but never delete a row; removing an entry is an update. Run `connector.sql` again whenever it changes: until then food writes are refused.
2. **Supabase OAuth server** (beta). Authentication → OAuth Server: enable it, switch on **Allow dynamic OAuth apps** (Claude registers itself), and set the **Authorization Path** to `consent.html` (with Site URL = your app address). Open `https://<project>.supabase.co/.well-known/oauth-authorization-server/auth/v1` once; it should show JSON. After the first connect attempt, check where the browser lands: it must be `<appUrl>consent.html?authorization_id=…`. If the path or Site URL join comes out wrong (for example without `/yes-coach/`), adjust the path until it matches.
3. **Function.** With the Supabase CLI (`npm i -g supabase`, `supabase login`): `supabase functions deploy mcp --project-ref <project> --no-verify-jwt`. (Dashboard alternative: Edge Functions → Deploy a new function → name `mcp`, paste `supabase/functions/mcp/index.ts`, and switch **Verify JWT** off.) If tools answer "The database said no (401)", add a secret `YC_ANON_KEY` with the publishable key from `config.js`.
4. **Add it in Claude.** Settings → Connectors → Add custom connector → URL `https://<project>.supabase.co/functions/v1/mcp`. Claude sends you to `consent.html`; sign in, Allow. Ask: "What is in my Yes Coach plan?"

People disconnect an app in the app under Settings, Connected AI apps.

### Rest alerts (optional)
A notification when the rest timer ends while the app is in the background. Until the key below is set, the setting does not show.
1. **Database.** Run `push.sql` in the SQL editor (safe to repeat).
2. **Keys.** On your computer: `node tools/vapid.mjs you@example.com`. Put the public key it prints into `config.js` (`vapidPublicKey`), and run the `supabase secrets set` line it prints (that stores the private key in Supabase; do not commit or share it).
3. **Function.** `supabase functions deploy rest-push --project-ref <project> --no-verify-jwt`.
4. Merge the `config.js` change. In the app: Settings, "Alert me when rest is over". On an iPhone the app has to be on the home screen first. Tests: `node --experimental-strip-types --no-warnings supabase/tests/rest-push.test.mjs`. Tests: `node --experimental-strip-types --no-warnings supabase/tests/mcp.test.mjs`.

## Later

- Before many people use *Forgot password*: add a custom email sender (Authentication → Emails → SMTP, for example Resend's free plan), because the built-in one is limited to a few emails an hour.

## Food data

Food search loads `foods-nevo.json` and `foods-usda.json` the first time someone searches in Food.

- NEVO: NEVO online version 2025/9.0, RIVM, Bilthoven. Values used unchanged; the app shows the required line "Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources". Conditions: no charging users, replace with each new NEVO release.
- USDA FoodData Central, SR Legacy (public domain).

Rebuild after a new release: `python3 tools/build_foods.py <NEVO20xx.csv> <USDA sr_legacy csv folder>` (keep the raw NEVO files out of this repo).
- Portie-online versie 2026/2.0, RIVM, Bilthoven: household measures per NEVO code in `portions-nevo.json` (used unchanged, packaging sizes left out). Full table: `Portie-online 2026-2.0.xlsx` in the Yes Coach folder.

## Tests

`tests/run.sh` builds the app and runs everything: the merge unit tests (Node), then the end-to-end suites in `tests/e2e/` (headless Chrome with Playwright, Supabase faked in memory): tickets, sign-in with the human check, the connector consent page, languages (including the exercise-name option), logging a workout (tick, untick, correct, offline retry, draft after reload), and food (search, your own foods and meals, quick food, meals logged by a connected AI). `tests/e2e/harness.py` holds the shared fake backend. The connector has its own suite, which runs the Edge Function against an in-memory database: `node --experimental-strip-types --no-warnings supabase/tests/mcp.test.mjs`.

Translations: see `tools/i18n/README.md`.
