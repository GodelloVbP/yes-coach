# Working on Yes Coach!

For anyone changing the app, human or AI. Read this before the first edit. The short version: edit `src/yes-coach.html`, rebuild, run the tests, open a pull request to `main`.

## What to edit and what not to

| Edit this | Never by hand |
|---|---|
| `src/yes-coach.html`: the whole app (markup, CSS, JavaScript) in one file | `index.html`: generated from it by `build.py`. Your edit is lost on the next build |
| `tools/i18n/extra.json`: new translations | `i18n/*.json`: generated from the files in `tools/i18n/` |
| `web.js`, `tickets.js`: sign-in, storage and the feedback tab | |
| `supabase/functions/mcp/index.ts`: the AI connector | |

`src/yes-coach.html` also runs unchanged as a claude.ai artifact, where `window.YC_WEB` is not set and there is no Supabase. Code that only makes sense on the website belongs behind a `window.YC_WEB` check or in `web.js`.

After every change to the source:

```bash
python3 tools/i18n/make_dicts.py
```

```bash
python3 build.py
```

Commit the regenerated `index.html` and `i18n/*.json` with your change. When a merge conflicts in a generated file, do not resolve it by hand: resolve the source files, then regenerate.

## Tests

```bash
sh tests/run.sh
```

It builds, then runs the unit tests (Node 22) and the end-to-end suites in `tests/e2e/` (headless Chrome through Python Playwright, with Supabase faked in memory; Chrome is expected at `/usr/bin/google-chrome`). It must be green before a pull request. One check, `e2e_search` "with an Undo toast", fails now and then on its own; rerun it before treating it as yours.

If you touch `supabase/functions/mcp/`, also run the connector suite, which `run.sh` does not include:

```bash
node --experimental-strip-types --no-warnings supabase/tests/mcp.test.mjs
```

Rules for tests:

- A change that breaks a test is a regression to fix, not a test to delete. Several tests guard the layout on purpose: the bottom bar fitting six labels in all six languages, neighbouring blocks never sharing a tint, nothing scrolling sideways on a phone.
- Tests find things by id and class (`#btn-start`, `#wz-go`, `#tab-feedback`, `.blk`). If you rename one, update the tests in the same change.
- New behaviour gets a test. `tests/e2e/harness.py` has the fake backend and `session(...)`, which also takes a fixed clock and a language.
- No test may reach the internet or a real account. The harness blocks outside requests, and the suites check that none were tried.

## Design

- **Colours come from tokens** at the top of the file (`--bg`, `--paper`, `--ink`, `--ink-soft`, `--line`, `--faint`, `--pop`, `--blk-a`, `--blk-b`, the `--c-*` body-part colours). Do not hard-code hex values in rules. Dark mode has its own values, written twice: in the `prefers-color-scheme` block and in `:root[data-theme="dark"]`. Change both.
- **Phone first.** The bottom bar is used below 64rem and a sidebar from there up. Check 360, 390 and 430 px wide, and at least one other language than English. German and French labels are the longest.
- **Touch targets** are at least 44 px. Controls keep the app's slanted look (`skewX(-14deg)`); text is written in sentence case and uppercased by CSS, so never type labels in capitals.
- **Blocks.** Each function or option on a page sits in a `.blk` panel. `toneBlocks()` alternates the two tints over the visible blocks. A new section is a new `.blk`.
- **Less text.** Say a thing once, where it is used. The onboarding review found screens of 140 to 190 words too long; aim for a headline and one short line.
- **Nothing from outside.** The Content Security Policy only allows this site and Supabase. No CDN scripts, web fonts, remote images or analytics. `build.py` adds the hash for every inline script, so a new inline script needs nothing extra, but an external one will not load.

## Text and translations

The app is written in English and translated on screen by `i18n.js`, by exact string match.

- Every new or reworded string needs nl, es, de, fr and it entries in `tools/i18n/extra.json`, keyed by the English string. Dynamic text uses `{0}`, `{1}`. Follow `tools/i18n/RULES.md`.
- Changing an English sentence orphans its translation, so update the key and the five translations together.
- Strings that are assembled from pieces at run time translate badly. Prefer one complete sentence with placeholders.
- Without translations the string shows in English in the other languages. The build does not fail on this, so check.

## The connector (AI access)

- Tool descriptions are plain statements. The connector test rejects directives (always, never, must, should, call this) and any mention of another tool by name.
- Foods and plans written by an AI go through database policies in `connector.sql`. Changing which paths a connected app may write means changing that file too.
- Merging a pull request only updates the website (GitHub Pages). The connector is a separate Supabase Edge Function. After changing `supabase/functions/mcp/index.ts`, it has to be deployed by the owner:

```bash
supabase functions deploy mcp --project-ref qazvzhhoalkyyasakphs --no-verify-jwt
```

  Changed `connector.sql`, `schema.sql` or `tickets.sql`? They need to be run again in the Supabase SQL editor. Say so at the top of the pull request.

## Pull requests

- Branch from `main`, one topic per pull request, squash-merge into `main`. Pages deploys from `main`.
- Add a line to the `CHANGELOG` in `src/yes-coach.html` (and its translations) for anything a user can see.
- Put anything only the owner can do (a deploy, SQL, a Supabase setting) at the top of the description.
