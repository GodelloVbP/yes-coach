# Translating Yes Coach! (free workout tracker web app) from English

Audience: gym-goers using a phone. Voice: friendly, direct, plain; informal "you" (tu/je/du/tú as the language's glossary says). No marketing fluff, no exclamation marks that the English does not have.

## Input / output
- Input is a JSON array of English strings; the position in the array is the key.
- Output is ONE JSON object file: {"<position>": "<translation>", ...}. UTF-8, valid JSON. Write it with the Write tool, then run the validate script given in your task and fix every problem it reports.
- UI task: OMIT an entry (leave it out of the output) when it is not text a person reads in the app: code, CSS, file names, instructions written for an AI chat (e.g. "Please review this workout as my coach..."), or exports meant for another program. When unsure, translate.
- Library task: translate EVERY entry, no omissions.

## Must-keep
- Placeholders `{0}`, `{1}`, ... must appear in the translation exactly as many times as in the English; you may move them for grammar. They are replaced at run time by numbers, names or other (still English) fragments.
- Keep: Yes Coach!, Coach Claude, Claude, ChatGPT, Strong, Hevy, FitNotes, Fitbod, JEFIT, Apple Calendar, Google Calendar, Outlook, Supabase, USDA, RIVM, NEVO, kg, g, kcal, cm, min, RPE, RIR (translate "Reps in reserve" in words), 1RM, symbols such as … · → ✓ ▲ ▼ “ ” and straight quotes.
- Case: sentence case exactly like the English (the interface uppercases some labels by CSS, so never write ALL CAPS yourself).
- Length: buttons and labels at most about 1.4x the English length. They sit in small phone buttons.
- Fragments: many strings are pieces that get glued into bigger sentences at run time (they start/end with a space, a comma, are lowercase, or are only a word like "on this day"). Translate the piece so it works as a neutral fragment. Do not add capital letters or final full stops that the English piece does not have. Keep leading/trailing spaces and punctuation of the English piece when the piece is not a standalone sentence.
- Plurals: "{0} session" and "{0} sessions" are two separate entries; translate each correctly for the language.
- Dates and weekday/month names are handled by the app. Do not invent them.
- Units and numbers stay as they are. No Markdown.
- Quote style: keep “ ” where the English has them.

## Quality
This ships to real users. Prefer the wording people use in gym apps in that language. Keep one term for one thing: follow the glossary exactly. If the English is clumsy, translate the meaning, not the clumsiness.
