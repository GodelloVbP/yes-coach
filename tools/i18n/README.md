# Translations

The app is written in English. `i18n/<code>.json` (nl, es, de, fr, it) are generated from the files here and loaded by `i18n.js`.

- `ui_in.json`, `lib_in.json`: the English strings, position = key (`extract.mjs` rebuilds the list from the source; needs `npm install` here for acorn).
- `tr/<code>_ui.json`, `tr/<code>_lib.json`: the translations by position. `RULES.md` and `gloss_<code>.md` are the instructions a translator (or an AI) follows.
- `extra.json`: strings added after the first pass, with all five languages inline. **New strings go here.**
- `python3 tools/i18n/make_dicts.py` rebuilds `i18n/*.json`. Run it, then `python3 build.py`.
- `python3 tools/i18n/validate.py <english.json> <translation.json> ui|lib` checks placeholders and keys.
