# Yes Coach! web app

A free, ad-free workout tracker. Static site on GitHub Pages, accounts and data in Supabase.

## Files

| File | What it is |
|---|---|
| `index.html` | The app. Built from `src/yes-coach.html` by `build.py`; do not edit by hand. |
| `web.js` | Sign-in screen and the storage layer (Supabase behind the app's data interface). |
| `config.js` | Your Supabase project URL and public key, the app address and a contact email. |
| `schema.sql` | The database: one table, row-level security, merge and delete-account functions. |
| `vendor/` | The Supabase client library, so the app has no runtime dependency on a CDN for it. |
| `manifest.webmanifest`, `icon-*.png` | Install to home screen. |
| `privacy.html` | Privacy page, linked from sign-in and Settings. |

## One-time setup

1. **Supabase** (supabase.com, free plan): New project, region *Central EU (Frankfurt)*, any strong database password.
   - SQL Editor → New query → paste all of `schema.sql` → Run.
   - Authentication → Sign In / Providers → Email: enabled; turn **Confirm email off** (the free plan sends only a few emails an hour; with it off, sign-up needs no email).
   - Authentication → URL Configuration: Site URL = your app address; add the same address under Redirect URLs.
   - Project Settings → API: copy the Project URL and the publishable key (`sb_publishable_…`, or the legacy `anon` key) into `config.js`. Never put the secret key anywhere in this app.
2. **GitHub**: repository `yes-coach` (public). Push these files to `main`. Settings → Pages → Deploy from a branch → `main` / root.
3. Fill in `appUrl` (for example `https://<you>.github.io/yes-coach/`) and `contactEmail` in `config.js`.
4. Open the app, create your account, Settings → Backup and restore → pick your backup file.

## Shipping an update

Change `src/yes-coach.html` (the same file runs the claude.ai version), run `python3 build.py`, commit and push. GitHub Pages serves it within a minute or two; people get it on their next load.

## Before the public launch

- Add a contact email in `config.js` (`contactEmail`); the privacy page shows it.
- Set up a custom email sender (see below) and consider turning Confirm email back on.

## Later

- Before many people use *Forgot password*: add a custom email sender (Authentication → Emails → SMTP, for example Resend's free plan), because the built-in one is limited to a few emails an hour.
- A Yes Coach connector, so a user's own AI can read and update their plan without copy and paste.

## Food data

Food search loads `foods-nevo.json` and `foods-usda.json` the first time someone searches in Food.

- NEVO: NEVO online version 2025/9.0, RIVM, Bilthoven. Values used unchanged; the app shows the required line "Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources". Conditions: no charging users, replace with each new NEVO release.
- USDA FoodData Central, SR Legacy (public domain).

Rebuild after a new release: `python3 tools/build_foods.py <NEVO20xx.csv> <USDA sr_legacy csv folder>` (keep the raw NEVO files out of this repo).
