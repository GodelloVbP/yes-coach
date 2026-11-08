# Yes Coach! design audit: every screen and menu, labelled

Rules applied: `DESIGN_RULES.md` (R1 to R11). Labels:

- **REMOVE**: take it out.
- **ADJUST**: keep the function, change how it looks, reads or where it sits.
- **KEEP**: leave as it is.

Nothing in the app was changed for this audit. It is a list to decide from.

How it was done: every screen was opened in a browser with realistic data (390 px wide, English), and the visible text, word counts and controls were listed. Words in brackets are the length of a note. Rules are named by number, for example R4 is the text budget.

**Not captured, so not judged:** the connector section in Settings (hidden unless connected), the sign-in form and the share picture on the finish screen as rendered, the copy-and-paste step of the plan wizard, desktop layout, and other languages.

---

## The patterns behind most of the labels

These repeat across screens. Fixing them once fixes many rows below.

| # | Pattern | Rule | Where |
|---|---|---|---|
| G1 | **Three looks for one job.** Choosing one option appears as slanted chips, as a boxed segment bar and as underlined tabs. | R1 | Chips: Plan, onboarding. Segments: period buttons in Progress and Food. Underlined tabs: miss-a-day, Appearance, body part, chart metric. |
| G2 | **A note under almost every control.** At least 25 different notes in the app are longer than 14 words, and many restate the control above them. | R4 | See the "(Nw)" markers in the tables. |
| G3 | **Rare actions look as important as common ones.** Move up, move down and remove sit next to the main button at the same weight. | R3, R7 | Workout exercise card, Plan day cards, lift detail. |
| G4 | **Inconsistent names for one thing.** Feedback, Request, Requests, Ticket and "Feedback & Requests" all name the same page. Workout, session, day and training day mix in the workout. | R9, R10 | Nav, More, Home, page titles, buttons. |
| G5 | **Empty screens still draw every block.** Progress with no data shows four empty sections. | R5, R7 | Progress, Your own foods. |
| G6 | **Copy bug.** "1 sets logged." (no singular). | R10 | Train, day sheet. |
| G7 | **Data that is the same on every row.** "Shoulder: go light" is on 27 of the 34 chest exercises and 89 of 304 overall. | R4, R5 | Exercises list. |

---

## 1. Bottom bar

| Element | Label | Rule | Notes |
|---|---|---|---|
| Train, Plan, Progress, Food, More | KEEP | | Short, fit in all six languages (tested). |
| Request (tab) | ADJUST | R9 | The label is "Request" but the page is "Feedback and requests". Pick one noun for the tab, the page title and the More row. |

## 2. Home (start page)

| Element | Label | Rule | Notes |
|---|---|---|---|
| Hero: "Log your sets. Plan your week. See your progress." | KEEP | | Clear from a distance. |
| Tagline (18w): "Free, no ads, on every device. It suggests your next weight, and your own AI can coach you." | ADJUST | R4 | Repeats the "Suggested weights" card, the "Use your own AI" card and the Free and private list. Cut it to one short line. |
| Main button (Today's training / Sign in / Create account) | KEEP | | |
| Three screenshots with captions | ADJUST | | Captions are fine. The pictures show the old wallpaper and the old truncated "Next: Over…" bar. They need new shots. |
| "What makes it different" and its 3 cards | KEEP | | Just reduced to three. |
| "Free and private" with 5 ticks | ADJUST | R4 | "Free" and "no ads" are already in the tagline. Merge to three: free and no ads, no tracking and never sold, export anytime. |
| Privacy page link | KEEP | | |
| Put on home screen / Connect to Claude | KEEP | | Only show when they apply. |
| Feedback block | KEEP | | |
| "Send a ticket" (button) | ADJUST | R9 | "Ticket" is a support-desk word. Use the same noun as the page. |

## 3. Train

| Element | Label | Rule | Notes |
|---|---|---|---|
| Today card: label, "Rest day", "No workout planned today." | KEEP | | |
| Start button on a rest day, and "Change today's workout" | KEEP | | |
| Done card: "Done: Push day" | KEEP | | |
| "{n} sets logged." with n = 1 | ADJUST | R10 | Reads "1 sets logged." Needs the singular. |
| Same "sets logged" line again in the day sheet right below | REMOVE | R4 | The card above already says it. |
| Week header, arrows, week blocks | KEEP | | |
| Hint "Tap a day for details. Drag to reschedule." | KEEP | | |
| Day sheet heading ("Sun 8 Nov · today") | KEEP | | |
| Day sheet "Rest. Nothing is planned." when the day is today | REMOVE | R4 | The Today card already says it. Keep it for other days. |
| "Train on this day" with its picker | KEEP | | |
| "Look back or correct", "Delete day" | KEEP | | Delete has a confirm. |
| "Add to calendar" button | KEEP | | |
| Note under it (11w): "Put your planned days in Apple, Google or Outlook calendar." | REMOVE | R4 | Restates the button. If it is needed, put it in the label: "Add to Apple, Google or Outlook". |
| Calendar panel: Weeks, Start time, Length | ADJUST | R7 | All have defaults. Show only "Download calendar file" and put the three options behind "Options". |
| Calendar note (29w) | ADJUST | R4 | Keep one line: "Download again after moving days, and delete the old events." The first sentence is obvious. |
| Month heading, grid, arrows | KEEP | | |
| Month legend (16w): "• planned · ✓ done · … in progress. Tap a day to open its week." | ADJUST | R4 | Keep the symbols. "Tap a day…" repeats the week hint. |

## 4. Workout (session)

| Element | Label | Rule | Notes |
|---|---|---|---|
| Top bar: back, day name, Today chip, counter, "…" | KEEP | | |
| "…" menu: Change date, Change day, Finish day, Delete day | KEEP | | |
| Exercise chips with n/m counts | KEEP | | |
| "All exercises" / "One at a time" | KEEP | | |
| Exercise name and body-part chip | KEEP | | |
| ↑ ↓ ✕ icon buttons on each exercise | ADJUST | R3, R7, R9 | Three bare icons of equal weight. ✕ sits next to ↓, shows only an icon, and removes the exercise from today. Put reorder and remove in one overflow menu. |
| "Target · Last time" fold | KEEP | | |
| Set rows: number, reps, load, tick | KEEP | | The core of the screen. |
| "+ Set" | KEEP | | |
| "+ Warm-up", "Switch to minutes", "Reverse grip", "−", "✎" | ADJUST | R3, R7, R9 | Six controls of the same weight under every exercise. "−" (remove last set) and "✎" (note) show only an icon; their names exist only for screen readers. Keep "+ Set" and move the rest into a "More" menu. |
| "+ Add exercise" | KEEP | | |
| "Workout note" label | KEEP | | |
| Note placeholder (14w): "How the session went, sleep, energy, anything for Coach. Saves as you type." | ADJUST | R4, R9 | "For Coach" is jargon and the field is for the person. Use "How it went". |
| "Copy workout" button | ADJUST | R7 | A sharing action for a few people, placed between the note and Finish. Move it into the "…" menu. |
| Bar: "Next exercise" and "Finish" | KEEP | | |
| Footer in all-exercises mode: "Finish day" | KEEP | | |
| Note under it (11w): "Ticked sets are already saved; finishing closes the day." | KEEP | | It states a result the person would not guess. |
| Set-type menu (Work, Warm-up, Drop, Test) | KEEP | | |
| Finish screen: date, name, tiles, records, Done | KEEP | | The share picture and its two toggles were not captured. |

## 5. Plan

| Element | Label | Rule | Notes |
|---|---|---|---|
| Page title "Your week" | ADJUST | R9 | The tab is "Plan", the title is "Your week", and Train has "your week" too. Use "Plan". |
| "Ask your AI coach" (coral, at the top) | ADJUST | R3 | The loudest button is an optional AI action. Make it outlined, or move it under the plan. |
| AI panel (22w): "Your coach gets your plan, your progress and your notes…" | ADJUST | R4 | One short line. Explain once, where the AI answers. |
| "Adjust this plan" / "Build a new plan" | KEEP | | |
| "Days you can train" chips | ADJUST | R7, R10 | Defaults to all seven, which makes the next control unclear. Preselect from the person's answers. |
| "Sessions a week" chips 1 to 7 | ADJUST | R8 | Wraps to a row of 5 and a row of 2. Offer 2 to 6 on one row. |
| Sessions note, e.g. "Your 4 sessions a week are spread over the 7 days you can train…" | REMOVE | R2, R4, R10 | Says nothing when all days are available. Show a small preview of the weekdays that will be used. |
| "If you miss a day": "Skip it" / "Move it up" | ADJUST | R1, R7, R9 | Underlined tabs for a setting. "Move it up" does not say where. Use the chip style, label by result, and put it under "Advanced". |
| Note under it (17w): "It moves up: your days repeat in this order…" | REMOVE | R2, R4 | Restates the choice. A preview replaces it. |
| "This week only: …" block | ADJUST | R5, R6 | Prints every stored move as a sentence, repeats, includes past days, sits under permanent settings. Replace with "{n} changes this week. Open this week" at most, or remove it from Plan. |
| "Open this week" link | KEEP | | |
| Day cards: name and exercise list | KEEP | | |
| "Edit day" | KEEP | | |
| ↑ ↓ on each day card | ADJUST | R3, R9 | Reorders the rotation, which the person cannot tell from the icons. Move it into Edit day or drag. |
| ✕ on each day card | ADJUST | R3, R9 | Takes the day out of the order (needs a second tap, so it is guarded). It is an icon only, sits beside the arrows, and "order" is internal language. Use a labelled "Remove from week" in Edit day. |
| "+ New training day" | KEEP | | |
| "Repeat a day in the order…" picker | ADJUST | R7, R9 | Editing the rotation is an expert action. Put it behind "Advanced". |

## 6. Plan: edit a day

| Element | Label | Rule | Notes |
|---|---|---|---|
| Back "‹ Your week", name field | KEEP | | |
| "In your week" label and "Take out of your week" button | ADJUST | R9 | Two near-identical actions on this page ("Take out of your week" and "Delete this day"). Rename by result. |
| Note (14w): "In your order, on Mon, Tue, Thu, Sat. Change the order in Your week." | ADJUST | R4 | Show the weekdays as a value, not a sentence. |
| Exercise rows, "+ Add exercise" | KEEP | | |
| "More: type of day" fold | KEEP | | Good use of disclosure. |
| Type label (14w): "Type (sets its color and helps your AI coach)" | ADJUST | R9 | Label it "Type". |
| "Delete" section, button | KEEP | | |
| Delete note (18w) | KEEP | | A surprising consequence, shown only here. |

## 7. Progress

| Element | Label | Rule | Notes |
|---|---|---|---|
| Body part tabs and period buttons | ADJUST | R1 | Two filters with two different looks (underlined tabs and a boxed bar). See G1. |
| "Your lifts", count, note "Best set per workout. Tap a lift for details." | KEEP | | |
| Lift rows | KEEP | | |
| Lift detail: "Heaviest set" / "Est. strength" tabs | KEEP | | |
| Lift detail note (32w) | ADJUST | R3, R4 | "Best in this period: 84 kg × 8" is the headline fact and is buried in a sentence. Make it a stat. Shorten the dashed-line explanation to a legend. Keep the estimate-versus-lifted explanation. |
| "Start a new trend from 5 Nov" and its note (14w) | ADJUST | R7, R9 | A rare action with a long explanation, shown to everyone. "Trend" is jargon. Move it into an overflow menu. |
| "Training days" block and note | KEEP | | |
| "Volume" note (16w) | ADJUST | R4 | Drop "Sessions per week are listed below the bars." |
| "Session log" fold | KEEP | | |
| Note: "Newest first. Working sets exclude warm-ups." | ADJUST | R4 | Keep the definition. "Newest first" is visible. |
| Empty state: four blocks with their own empty messages, an empty table with headers | ADJUST | R5, R7 | Show one message ("No sessions logged yet…") and hide the empty blocks, as Food now does. |

## 8. Food

| Element | Label | Rule | Notes |
|---|---|---|---|
| Date navigation, day meter | KEEP | | |
| Search field | KEEP | | The Dutch example words ("kwark, banaan") stay in an English interface; fine if intended. |
| Search results (14 to 15 words each) | KEEP | | Dense, but this is the data. |
| "+ Save “rice” as your own food" with 17w hint | ADJUST | R4 | Title plus a four-word hint. |
| "+ Log “rice” once" with 17w hint | ADJUST | R4 | Same. |
| Data credit (17w), shown under the search results | ADJUST | | Required, but it sits mid-page. Move to the end of the page. |
| "Eaten" list, count, × buttons | KEEP | | |
| "Nothing logged today yet." | KEEP | | |
| "Your own foods" block when empty | ADJUST | R5, R7 | A whole block above Trends for something most people use rarely. Collapse to one row until a food exists. |
| Own foods note and "Create a food" | KEEP | | |
| Create form: name, unit, four numbers, Save, Cancel | KEEP | | |
| Create form note (15w): "All numbers are per 100 g, as printed on the package. Use 0 for none." | REMOVE | R4 | Every label already says "per 100 g". "Use 0 for none" is in the placeholder. |
| Trends: period buttons, metric tabs, averages, chart | KEEP | | |
| Trends note (16w): "Each day you logged, in the past month. Set a target below…" | ADJUST | R4, R6 | Points to a collapsed section "below". Shorten. |
| Daily targets (folded) | KEEP | | |
| Targets note (18w): "Leave empty for no target. Targets show as a line on the chart and in the day meter." | ADJUST | R4 | "Leave empty for none." |
| Suggestion text (18w) plus a button with the same words | ADJUST | R4, R10 | A sentence and a button saying the same thing, plus "Or set your own below". Keep the button, label it "Get a suggestion". |
| "Calories are hidden." with "Show calories" | KEEP | | |
| Calorie question on first visit | KEEP | | One-time. |

## 9. Request

| Element | Label | Rule | Notes |
|---|---|---|---|
| "Send us something", lead (21w), three tiles | KEEP | | Just redone. |
| Form: title, message, first name, privacy note (22w), Send, Cancel | KEEP | | The note is about consent. |
| "We have a question" block | ADJUST | R3 | Our question should be the first thing in the card. It shows your own original message first. |
| "Your messages" header and count | KEEP | | |
| Summary "You have sent 2 requests." | ADJUST | R4 | Repeats the count in the header. Keep only the outcomes line ("2 built or fixed, 1 planned"). |
| Group headings, cards, status chips | KEEP | | |
| Open card: message plus an always-open reply box (textarea and Send) | ADJUST | R7 | Every open card carries a form. Put it behind an "Add a message" button. |

## 10. More (the menu)

| Element | Label | Rule | Notes |
|---|---|---|---|
| Group labels and row order | KEEP | | |
| Rows: Account, About you, Appearance, Languages, Logging, Food, Exercises, Get a plan or import, Export for review, Backup and restore, Feedback & Requests, What's new, Privacy | KEEP | | Names are mostly clear. "Feedback & Requests" should match the nav noun (G4). |

## 11. More: Account, About you, Appearance, Languages

| Element | Label | Rule | Notes |
|---|---|---|---|
| Account: "Signed in as …" (11w) | ADJUST | R4 | Drop "Your data syncs between your devices." |
| Sign out | KEEP | | |
| Delete my account | KEEP | | Danger style plus a confirm. Better with more space from Sign out. |
| "Privacy" link inside Account | REMOVE | R4 | Also a row under Help. |
| About you: note (26w) | ADJUST | R4 | "Used for plans, food targets and the text you copy for an AI." |
| About you: ten fields | KEEP | | All optional, all with "Not given". |
| Appearance: note (14w) | ADJUST | R4 | "Auto follows your device." |
| Appearance: Auto / Light / Dark as underlined tabs | ADJUST | R1 | Same chooser as the other single-choice settings (G1). |
| Languages: note (24w) | ADJUST | R4 | "Translations are AI-generated and may contain mistakes." The report button follows. |
| Language list and "Report a translation mistake" | KEEP | | |

## 12. More: Logging, Food, Exercises

| Element | Label | Rule | Notes |
|---|---|---|---|
| "Show a reps-in-reserve (RIR) field on each set" | KEEP | | |
| "Suggest the next weight from your last sessions" | KEEP | | |
| Plate bar select and seven plate checkboxes | ADJUST | R7, R3 | An equipment inventory shown to everyone, with no group label. Fold under "Plate calculator" with a label. |
| Plate note (21w) | ADJUST | R4 | "Barbell exercises get a Plates button." |
| "Show calories in Food" | KEEP | | |
| Calories note (29w) | ADJUST | R4 | Label it "Count calories too". The note shrinks to one line. |
| Exercises library: "For you" with four cards, each with a day select and "Add to day" | ADJUST | R7, R1 | Eight controls for four suggestions. One "Add to a day" action per card is enough, with the day picked after. |
| Library: search, 8 category tabs, sort, "+ Add your own" | ADJUST | R1, R7 | Eight tabs wrap onto two rows. Sort is rarely used. Fold "Sort by". |
| "Shoulder: go light" on most rows | ADJUST | R4, R5 | Printed on 27 of 34 chest exercises, so it stops meaning anything. Show it only when the person said they have a shoulder issue. |
| Library rows | KEEP | | |

## 13. More: Get a plan or import, Export, Backup

| Element | Label | Rule | Notes |
|---|---|---|---|
| "Build my plan or import" (coral) | KEEP | | The main path. |
| Intro note (15w) | REMOVE | R4 | The button says it. |
| "Prefer to work in your own AI chat?" note (23w) | ADJUST | R4, R9 | "The text below gives it what your old app's export means and your details above." is unclear. |
| "Coming from" select (7 options), how-to note (28w), Copy, Download .md, Preview, textarea | ADJUST | R7 | The manual copy-and-paste route duplicates the wizard and shows a large text preview. Put it all under "Use your own AI chat instead". |
| Export: note (30w) | ADJUST | R4 | One sentence. |
| "Notes about your body" field | KEEP | | |
| Copy, Download .md, Download .csv | ADJUST | R3 | Three buttons of the same weight. .md is for an AI review, .csv is the data. Separate them. |
| Preview with "95 lines, 4 kB" and a large textarea | ADJUST | R7 | Collapse. |
| Backup: note (40w) | ADJUST | R4 | Two short lines: what it holds, what restoring does. |
| "Full backup", "Restore from a backup" | KEEP | | |

## 14. What's new

| Element | Label | Rule | Notes |
|---|---|---|---|
| Back link, heading | KEEP | | |
| Entries: 43 since 2 Nov, about 11,600 px tall, many 20 to 35 words | ADJUST | R4, R5 | Show the latest five with an "Older" fold. |
| A date label above every entry | ADJUST | R5 | Six dates for 43 entries, so "5 Nov 2026" repeats 14 times. Group entries under one date. |
| Entries about internals ("every part of a page now sits in its own block…") | REMOVE | R4, R9 | Not something a person can use. |
| Entry titles and bullets | KEEP | | |

## 15. Onboarding

| Element | Label | Rule | Notes |
|---|---|---|---|
| "Welcome to Yes Coach!" and "I will build my own" | KEEP | | |
| Question, 2 to 6 chips, "Next" | KEEP | | |
| Note: "Days a week. You can change it any time." | ADJUST | R4 | Drop "Days a week." |
| "Coming from Strong, Hevy or FitNotes? Import your history" | KEEP | | |
| Import screen: chips, "Pick the app you come from.", Import button, Back | KEEP | | |
| Preview summary, session length, first workout | KEEP | | |
| "First workout / Training days / Missed workouts" lines | KEEP | | |
| Day cards with full exercise lists | KEEP | | Content, not explanation. |
| "Change it with your AI (optional)" fold | KEEP | | Folded by default. |
| "Using Claude? Connect it once…" note (16w) with "How to connect" | ADJUST | R4 | Keep the link with a short label. |
| "Start training", "Change my answers" | KEEP | | |

---

## Counts

| Label | Rows |
|---|---|
| KEEP | 86 |
| ADJUST | 63 |
| REMOVE | 9 |
| Total | 158 |

Most REMOVE rows are notes that restate the control next to them (R4). Most ADJUST rows are the same few patterns in G1 to G7.
