# Yes Coach! text audit: every string, checked against the design rules

Rules: `DESIGN_RULES.md`. Labels: **REMOVE**, **ADJUST**, **KEEP**. Nothing in the app was changed.

## Result

| | Strings |
|---|---|
| Checked | 1,576 |
| KEEP | 1420 |
| ADJUST | 142 |
| REMOVE | 14 |

**Correction after a second pass (see the last section):** the KEEP count below is too high. At least 14 more strings should be flagged, and about 80 release notes are a class of problem the first pass treated one by one. The figures in this table are the first pass only.

About 10% of all strings were flagged in the first pass. Roughly 400 to 500 of the 1,576 are not text people read on screen (prompts written for an AI, code, file names, key names, fragments that are glued into sentences), so the share of what people actually read is closer to 15 to 20%. Most of the text is already short; the problems are concentrated in a few places, listed next.

**How it was checked:** every string was extracted from the source, 5 reviewers each took a fifth in source order and judged it against the rules reading the code around it, and I then read all 156 flags myself. The "My verdict" column shows where I accepted, amended or rejected the reviewer's proposal. Proposals keep every placeholder and none is more than 3 words longer than the original.

## Decisions I need from you: the vocabulary

Most flags are the same few naming problems. Decide these once and about 40 rows follow from them (marked V1 to V4 in the tables below).

| # | The problem | Today | Proposal | Rows |
|---|---|---|---|---|
| V1 | One thing, four names | workout, session, training day, day. About 90 strings use two or more of them. | Say "workout" for what you do. Keep "training day" only for the weekday you train. Keep "Session log" only if you want a second word, otherwise "Workout log". Open question: a plan item such as "Push day" is also called a training day. I suggest "workout" there too. | 7 |
| V2 | The AI helper has five names | "your coach", "AI coach", "Coach Claude", "Claude", "your AI". "Coach" also names the app and the person's own notes ("Note for Coach"). | "Claude" for the built-in helper (only on claude.ai). "Your AI" for the copy-and-paste chat. Never "coach" for the AI, never "coach" for your notes. The product name "Yes Coach!" stays. | 16 |
| V3 | One page, five names | Feedback, Request, Requests, Ticket, "Feedback & Requests". "Request" also means the text you copy for an AI. | "Feedback" for the page, the tab, the More row and the home page button. "Request" stays the word for what you send. Call the AI text "the text you copy", never "request". | 3 |
| V4 | Internal model words | "in the order", "move it up", "rolling", "rotation" | "Your week" and "Move to next day", "Repeats on". | 14 |

Smaller conflicts (decide as you go): "the copy-and-paste way" becomes "copy and paste instead" (6 strings); "Settings" versus "More" name the same place; "climb" versus "altitude gain"; "Forget" a food versus Delete and Remove (proposal: Delete); "machine" versus "equipment"; "here" versus "this view" versus "this page"; "PR" versus "personal record"; "plan" versus "schedule" versus "week".

## What to remove (14 strings)

| Area | Text | Why | My verdict |
|---|---|---|---|
| Home, finish, connect | No workout planned today. | Restates the "Rest day" heading directly above it. | Accept  |
| More and settings | Most people know an exercise by its English name, so the names stay in English. Switch this on to see them translated. | The label 'Translate exercise names' already says it. | Accept  |
| More and settings | Build a plan from a few answers, and bring your history over from another app. | Restates the 'Get a plan or import' heading. | Accept  |
| Plan and week | It is skipped: each weekday keeps its own training day. | Label 'Skip it' already says this. | Accept  |
| Plan and week | It moves up: your days repeat in this order on your training days, so nothing is skipped. | With a clear label, note about 'this order' is internal and redundant. | Needs V4  |
| Plan and week | Every day you can train is a training day. Pick how many sessions a week you want, and they are spread over those days. | Restates the picker; says nothing when all days are on. | Accept  |
| Plan and week | Every day you can train is a training day. | True for every setting; tells nothing. | Accept  |
| Plan wizard and AI | Saving your plan… | Restates the heading 'Saving your plan' directly above; only the progress count adds anything. | Accept  |
| Plan wizard and AI | Undo puts your old schedule back. | Toast already has an Undo button; sentence restates it. | Accept  |
| Request | What happened, and on which screen | Restates the form hint for the same kind. | Decide The tile hints help you choose before the form exists. The form hint helps while typing. Different moments. Keep the tile hints. |
| Request | Something you want it to do | Restates the form hint for the same kind. | Decide Same as above. |
| Request | What you like, what feels off | Restates the form hint for the same kind. | Decide Same as above. |
| What's new | The labels in the bottom bar get a little smaller on a phone so all six fit, in every language. | Font-size detail nobody needs. | Accept  |
| What's new | Tap I ate something to save the time in one tap and fill it in later. Fill in swaps it for what you add. | "Tap... in one tap" repeats; say what is saved. | Remove The whole entry is about "I ate something", which no longer exists. |
| What's new | Smoother screens and clearer feedback on every tap. | "Smoother screens" and "clearer feedback" tell the person nothing. | Accept  |

## Rewrites by area

Verdicts: **Accept** (take the proposal), **Needs V1 to V4** (a pure vocabulary swap that follows from your decision above), **Amend** (my change to the proposal), **Reject** (leave the original), **Decide** (needs you). Area comes from where the string sits in the source, so it is approximate.

### What's new (33)

**Bigger point:** the changelog has 43 entries across 6 dates and most of what is flagged here is release-note wording. Showing the latest five with an "Older" fold would remove more text than rewriting these 34 would. Several notes describe internals (tints, font sizes) or features that are gone.

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Request: pick what you want to send, and the form opens under it. A question from us waits at the top, and your messages are grouped below. | Pick what you want to send and the form opens under it. A question from us waits at the top, and your messages are grouped below. | R9 | Needs V3 |
| In Settings, a tap or hover on a section now covers the whole bar. | "In More, tapping anywhere on a section bar now opens it." | R9 | Amend |
| Progress, the exercise suggestions and the home page say less. Suggestions no longer say what you like or tell you how to feel about them. | Progress, exercise suggestions and the home page have less text. | R4 | Accept |
| While you log, the bar at the bottom says Next exercise, and the Finish button is no longer shown twice. | While you log, the bottom bar says Next exercise. Finish is no longer shown twice. | R4 | Accept |
| Food: what you ate comes before Your own foods, and the suggested targets sit in Daily targets instead of above your day. | Food: what you ate now comes before Your own foods. Suggested targets moved into Daily targets. | R10 | Accept |
| Train and the plan preview say less: the first workout gets its date, and Add to calendar is no longer the loudest button. | Train and the plan preview have less text. The first workout shows its date, and Add to calendar is a quieter button. | R4 | Accept |
| Feedback and requests has its own tab at the bottom, next to More, instead of being hidden in More. A dot shows there when we have asked you something. | Feedback has its own tab at the bottom, next to More. A dot shows when we have asked you something. | R4,R9 | Accept |
| Calories that do not fit the protein, carbs and fat get flagged, which catches a per-serving number slipped in for a per-100 g one. | Calories that do not match the protein, carbs and fat get flagged. This catches per-serving numbers entered as per 100 g. | R4 | Accept |
| Every part of a page now sits in its own block, and blocks next to each other take turns between a cool and a warm tint. On Train: today, your week, and the month ahead. | Every part of a page now sits in its own block, in alternating cool and warm tints. On Train: today, your week and the month ahead. | R4 | Accept |
| New here? Three questions, one per screen, and your plan is ready: how often, where, and how long you have trained. A tap answers and moves on. | New here? Answer three questions, one per screen: how often, where, and how long you have trained. Your plan is ready. | R10 | Accept |
| Leave setup half way, or go copy something to your AI, and it picks up where you were. | If you leave setup half way, it picks up where you were. | R4 | Accept |
| On the web, Build my plan goes straight to the copy-and-paste step, and the request is shorter: only exercises for where you train, and the answer comes in your language. | On the web, Build my plan goes straight to the copy-and-paste step, and the text you copy is shorter: only exercises for where you train. The answer comes in your language. | R9 | Accept |
| Plan: the days you tick are the days you can train. Set how many sessions a week you want, and they are spread over those days. | Plan: tick the days you can train and set how many sessions a week you want. | R10 | Accept |
| Every custom workout is its own day, shows in the week and the month while it is in progress, and can be continued from there. | Each custom workout is its own day. It shows in the week and month while in progress, and you can continue it from there. | R4 | Accept |
| Foods that come out the same, like the different eggs or apples, now show as one result. Tap +2 almost the same to see the others. | Near-identical foods, like different eggs or apples, now show as one result. Tap +2 almost the same to see the rest. | R4 | Accept |
| Runs track distance, altitude gain and where you ran: outside or on a treadmill. The pace per km is worked out for you. | Runs track distance, climb and where you ran: outside or on a treadmill. The pace is worked out for you. | R4,R9 | Accept |
| Reaching your protein target is enough: more is never shown as above. | Reaching your protein target is enough. Going over it is no longer shown as above. | R10 | Decide The agent's rewrite is longer and still vague. Check what this release note describes before rewording. |
| Calories get a band: within 10% of your target counts as on target. | Calories within 10% of your target now count as on target. | R9 | Accept |
| Results that only match an old synonym no longer crowd the list. | Foods that only match an old name no longer crowd the list. | R9 | Accept |
| Save a meal you eat often and log it again with one tap. In your day, open a meal with several foods and tap Save as a meal. | Save a meal you eat often and log it again in one tap. Open a meal with several foods and tap Save as a meal. | R4 | Accept |
| The start page for visitors now shows the app on three screens and what makes it different. Pick your language with the button at the top. | The start page for visitors now shows the app on three screens. Pick your language with the button at the top. | R10 | Accept |
| Tap + Warm-up on an exercise for a ramp to your working weight: the empty bar, then about half, 70% and 85% of it. It appears from 40 kg. | Tap + Warm-up on an exercise to add ramp-up sets: the empty bar, then about half, 70% and 85% of your weight. Shown from 40 kg. | R4,R9 | Accept |
| Progress charts now show the weights you lifted by default. The estimated strength chart is one tap away and says it is an estimate. | Progress charts now show the weights you lifted. The estimated strength chart is one tap away. | R4 | Accept |
| Put a day in your week right where you edit it: tap the weekdays on the day itself. Delete is now in plain sight at the bottom. | Choose a training day's weekdays right where you edit it. Delete is now easy to find at the bottom. | R10 | Accept |
| Dutch foods now offer RIVM's household measures: 1 beschuit (10 g), 1 snee (35 g), 1 glas (200 ml), 1 eetlepel and more, with 2 and 3 of them one tap away. | Dutch foods now offer RIVM's household measures, like 1 beschuit (10 g) or 1 eetlepel, with 2 and 3 of them one tap away. | R5,R4 | Accept |
| Search, pick a food, tap how much. Food is per 100 g and drinks per 100 ml. Do not know the weight? Tap a portion: for Dutch foods these are RIVM's own household measures (Portie-online versie 2026/2. | Search, pick a food, tap how much. Food is per 100 g and drinks per 100 ml. Do not know the weight? Tap a portion, like 1 beschuit or 1 eetlepel for Dutch foods. | R4 | Accept |
| Tap the weekdays you train, and choose what a missed day does: skip it, or move it up. | Tap the weekdays you train, and choose what happens to a missed day: skip it or move it to the next day. | R9 | Needs V4 |
| Ask your AI coach | Ask your AI | R9 | Needs V2 |
| Ask your AI coach right from Plan to adjust your plan: you see what changes before anything does. | Ask your AI from Plan to adjust your plan. You see what changes before anything does. | R9,R10 | Needs V2 |
| Want to count? Switch on calories in Settings, Food: log calories, protein, carbs and fat, get a suggested daily target from your goal, and see averages and a chart over 1 to 12 months. | Want to count? Switch on calories in Settings, Food. Log calories, protein, carbs and fat, get a daily target from your goal and see averages over 1 to 12 months. | R5,R10 | Accept |
| Your own account, with your log and plan in sync between phone and laptop. | Your own account, so your log and plan are the same on phone and laptop. | R9 | Accept |
| Starting weights come from your history; starting fresh, week one finds your weights. | Starting weights come from your history. If you start fresh, week one finds your weights. | R10 | Accept |
| Log sets with a rest timer, plan your week with drag and drop, notes for your coach, and export for an AI review. | Log sets with a rest timer, plan your week with drag and drop, add notes, and export for an AI review. | R9 | Needs V2 |

### Plan wizard and AI (21)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| {0} leaves your week (it stays under Not in your week) | {0} moves to Not in your week | R10 | Accept |
| First time: pick a weight you could lift 2 or 3 more times than the reps. | First time: pick a weight that leaves 2 or 3 reps in reserve. | R9 | Accept |
| Yes Coach was not allowed to use Claude. Allow it in this page's permissions and try again, or use the copy-and-paste way. | Yes Coach is not allowed to use Claude. Allow it in this page's permissions and try again, or copy and paste instead. | R9 | Needs V2 |
| Claude is not available in this view. Open Yes Coach signed in to claude.ai, or use the copy-and-paste way. | Claude is not available here. Open Yes Coach while signed in to claude.ai, or copy and paste instead. | R9 | Needs V2 |
| Use the copy-and-paste way | Copy and paste instead | R9 | Accept |
| Your history is too large to send in one go. Use the copy-and-paste way and attach the file instead. | Your history is too large to send at once. Copy and paste instead, and attach the file. | R9 | Accept |
| This file needs an AI to read it. Build a plan with your AI, or use the copy-and-paste way in Settings. | This file needs an AI to read it. Build a plan with your AI, or copy and paste from Settings. | R9 | Accept |
| Your coach is building your plan… | Claude is building your plan… | R9 | Needs V2 |
| Your coach is changing the plan… | Claude is changing the plan… | R9 | Needs V2 |
| Saving stopped part way ({0}). Check your connection and press Try again; what was saved is not saved twice. | Saving stopped part way ({0}). Check your connection and press Try again. Nothing is saved twice. | R10 | Accept |
| Restoring stopped part way ({0}). Press Back and Restore my data again; what is already restored is skipped. | Restoring stopped part way ({0}). Press Back and Restore my data again. Nothing is restored twice. | R10 | Accept |
| Your coach gets your current plan, your progress over the last 3 months and your notes about your body. Say what you want changed, or leave it empty for a check-up. | Keep it exact about what is shared: "Claude sees your plan, your progress over the last 3 months and your notes about your body. Say what to change, or leave it empty for a check-up." | R4,R9 | Amend |
| Ask my coach | Ask my AI | R9 | Needs V2 |
| You ask your own AI chat: Yes Coach writes the request, you paste the answer back. Nothing changes until you apply it. | Yes Coach writes the request, you paste your AI's answer back. Nothing changes until you apply it. | R4 | Accept |
| Days a week. You can change it any time. | Days a week | R4 | Accept |
| Two steps with your own AI (Claude, ChatGPT or another chat): copy the request below into a new chat, then paste its whole answer back here. | Works with Claude, ChatGPT or any other AI chat. | R4,R9 | Needs V2 |
| 1. Copy the change request | 1. Copy the request | R9 | Accept |
| {0} kB of text, ready to paste. | {0} kB, ready to paste. | R9 | Accept |
| This answer has no plan data in it. Ask your AI: "Please give the plan as JSON, in the shape the request asks for", then paste that answer here. | No plan found in this answer. Ask your AI to give the plan in the shape the request asks for, then paste it here. | R9 | Needs V2 |
| Nothing: your coach keeps your plan as it is. | Nothing. Your plan stays as it is. | R9 | Needs V2 |
| Applying updates your days in place. Logged sessions stay exactly as they were, and Your week can bring back the old week. | Your logged sessions stay as they are. You can bring back the old week from Your week. | R4,R10 | Accept |

### Plan and week (21)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Chest/shoulder and back work on {0} {1} and {2} {3} with no rest day between. Leave a rest day between them. | Chest/shoulder and back on {0} {1} and {2} {3}, back to back. Leave a rest day between. | R10 | Accept |
| Remove {0} from {1} {2}? Your plan stays the same. Only this week changes. | Remove {0} from {1} {2}? Only this week changes, not your plan. | R4 | Accept |
| Rest. Nothing is planned. | Rest day. | R4 | Accept |
| No schedule. Planned days follow each training day's weekday. | Each training day stays on its own weekday. | R9 | Accept |
| Rolling on {0}: {1}. | Repeats on {0}: {1}. | R9 | Needs V4 |
| Days you already trained and past dates are left out. If you move days later, download again and delete the old events, because some calendars add a second copy. | Past dates and days you already trained are left out. After changing your days, delete the old events first: some calendars add duplicates. | R10 | Accept |
| Missed days now move up: your days repeat in this order. | Missed days now move to the next training day. | R9 | Needs V4 |
| Your coach gets your plan, your progress and your notes, and answers with a plan you can check before it changes anything. | Your AI gets your plan, progress and notes, and answers with a plan you check before anything changes. | R9 | Needs V2 |
| Your {0} a week are spread over the {1} days you can train. They can land on different weekdays as the weeks go. | {0} a week, spread over your {1} days, so they can land on different weekdays. | R10,R9 | Accept |
| That is {0} a week but only {1} you can train. Pick more days, or fewer sessions. | {0} a week, but only {1} you can train. Pick more days or fewer sessions. | R4 | Accept |
| Move it up | Move to next day | R9 | Needs V4 |
| Earlier in the order | Move earlier | R9 | Needs V4 |
| Later in the order | Move later | R9 | Needs V4 |
| {0} from the order | {0} from your week | R9 | Needs V4 |
| No days in the order yet. Add one below. | No training days in your week yet. Add one below. | R9 | Needs V4 |
| Add to the order | Add to your week | R9 | Needs V4 |
| Add a day to the order again | Add a day again | R9 | Needs V4 |
| Repeat a day in the order… | Repeat a day… | R9 | Needs V4 |
| Tapping a day that is taken puts this day there instead. | Tapping a taken day replaces what is on it. | R4 | Accept |
| Not in your order yet. | Not in your week yet. | R9,R10 | Needs V4 |
| In your order, on {0}. Change the order in Your week. | On {0}. Change this in Your week. | R9,R10 | Needs V4 |

### Food (17)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Leave empty for no target. Targets show as a line on the chart and in the day meter. | Leave empty for no target. Targets appear on the chart and day meter. | R4 | Accept |
| {0} added. Open it to put it in a training day. | {0} added. Open it to add it to a workout. | R9 | Needs V1 |
| Your goal is to lose weight, so this is about 15% under what you burn: slow enough to keep your energy for training. More protein helps you keep your muscle. | Your goal is to lose weight, so this is about 15% under what you burn. Extra protein helps you keep muscle. | R4,R10 | Accept |
| Your goal is to gain muscle, so this is a little over what you burn, with plenty of protein to build with. | Your goal is to gain muscle, so this is a little over what you burn, with plenty of protein. | R4 | Accept |
| Your goal is both, so this is a little under what you burn, with extra protein so muscle can still grow. | Your goal is to lose fat and gain muscle, so this is a little under what you burn, with extra protein. | R10 | Accept |
| You have not picked a goal, so this is about what you burn. Pick one in Settings, About you, to tailor it. | No goal picked, so this is about what you burn. Pick one in Settings, About you. | R4 | Accept |
| Suggested targets are for adults. Growing bodies need enough food: if you want a target, ask your doctor or a dietitian. | Suggested targets are for adults. If you are still growing, ask your doctor or a dietitian about a target. | R10 | Accept |
| Without sex filled in, it uses the middle between the female and male formula. | With sex left blank, it uses the average of the female and male formulas. | R10 | Accept |
| It is an estimate: bodies differ. Use it for two or three weeks, see how your training and energy feel, and adjust by about 150 kcal if needed. | It is an estimate. Try it for two or three weeks, then adjust by about 150 kcal if needed. | R4 | Accept |
| Calories per 100 {0} are a number up to 900. | Calories per 100 {0} must be a number up to 900. | R10 | Accept |
| Forget | Delete | R9 | Accept |
| The list of your foods is full. Forget one first. | The list of your foods is full. Delete one first. | R9 | Accept |
| Forgot {0}. Entries you already logged stay as they are. | Deleted {0}. Entries you already logged stay as they are. | R9 | Accept |
| Forget this food | Delete this food | R9 | Accept |
| Grams are numbers, or leave them empty. | Enter grams as numbers, or leave them empty. | R10 | Accept |
| Targets are numbers, or leave them empty. | Enter targets as numbers, or leave them empty. | R10 | Accept |
| You are reviewing the training of a lifter who coaches himself. Read the context, the training days and the log below, then answer with: | You are reviewing the training of a lifter who coaches themselves. Read the context, the training days and the log below, then answer with: | R10 | Accept |

### More and settings (13)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Used when a plan is built or adjusted, for food targets, and in the text you copy for an AI. Stored privately in your own account. | Used for your plan, food targets and the text you copy for an AI. Stored privately in your account. | R4,R10 | Accept |
| Auto follows your phone or computer. Your choice is saved on this device only. | Auto follows your device. Saved on this device only. | R4 | Accept |
| Yes Coach! is originally in English. The translations are AI-generated and might contain mistakes. If you find one, please report it in the form. | Yes Coach! is originally in English. The translations are AI-generated and may contain mistakes. | R4 | Accept |
| AI apps you allowed to read your data, change your plan and log your food. Disconnect one and it loses access straight away. | AI apps you allowed to read your data, change your plan and log your food. Disconnecting removes access right away. | R4 | Accept |
| Prefer to work in your own AI chat? The text below gives it what your old app's export means and your details above. | Prefer your own AI chat? Copy the text below. It explains your old app's export and includes your details above. | R9,R10 | Accept |
| One text file with your log, progress, training days and notes. Paste it into any AI chat or send it to a trainer. It starts with instructions for the reviewer. | One text file with your log, progress, training days and notes. Paste it into any AI chat or send it to a trainer. | R4 | Accept |
| A full backup holds everything, your training plan and schedule included. Restoring adds what is missing here, and can put your training plan back the way it was in the backup. It never deletes anythi | A full backup holds everything, including your plan and schedule. Restoring adds what is missing and can bring your plan back as it was. It never deletes anything or edits a logged workout. | R4,R9 | Needs V1 |
| Off by default: Food then tracks what you ate with protein, carbs and fat, without calories. Switch it on to log calories too, with a calorie target and chart. | Off: Food tracks protein, carbs and fat only. On: calories too, with a target and chart. | R2,R4 | Accept |
| Running on a treadmill. Log minutes, distance and climb; the pace is worked out for you. | Log minutes, distance and climb. The pace is worked out for you. | R4 | Accept |
| A run outside. Log minutes, distance and climb; the pace is worked out for you. | Log minutes, distance and climb. The pace is worked out for you. | R4 | Accept |
| Type (sets its color and helps your AI coach) | Type (sets its color; your AI uses it) | R9 | Needs V2 |
| Injuries, pains or anything unusual about your body. For example: right shoulder hurts on heavy pressing. | Injuries or pain. For example: right shoulder hurts on heavy pressing. | R4 | Accept |
| Your training data is not available here. Sign in to claude.ai first. Already signed in? Then this account can only view Yes Coach, so it has no space for its own data: the owner can invite it as Edit | Your training data is not available here. Sign in to claude.ai first. Already signed in? This account can only view Yes Coach. Ask the owner to invite you as Editor in Share. | R4,R9 | Needs V2 |

### Workout (13)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Starts blank. Add what you do today, like a run. | For anything off your plan, like a run. | R4 | Accept |
| Pick what you want to train today. The last time you trained each day is shown, so you can leave sore muscles alone. | Pick today's workout. Each one shows when you last trained it. | R4,R10 | Accept |
| The day was not deleted. Check your connection. | The workout was not deleted. Check your connection. | R10 | Accept |
| Ticked sets are already saved; finishing closes the day. | Ticked sets are already saved. | R4,R10 | Accept |
| Looking ahead to {0} {1}. These are your current targets. Nothing is saved until you tick a set. | Looking ahead to {0} {1}. Nothing is saved until you tick a set. | R4 | Accept |
| Barbell exercises get a Plates button: it shows which plates go on each side, or the nearest weights you can build. | Used by the Plates button on barbell exercises. | R9,R4 | Accept |
| Note for Coach about {0} | Note about {0} | R9 | Needs V2 |
| Measure {0} in {1} instead of {2}? This applies to every day that uses it. Logged sets keep their numbers, Progress starts a new trend, and the reps and target in your plan stay as they are until you  | Measure {0} in {1} instead of {2}? This changes every workout that uses it. Logged sets keep their numbers and Progress starts a new trend. Plan reps and target stay until you edit them. | R4,R10 | Accept |
| Opens that date as its own session. | Opens that date as its own workout. | R9 | Needs V1 |
| Opens that date as its own session. The {0}{1} ticked here stay on {2}. | Opens that date as its own workout. The {0}{1} ticked here stay on {2}. | R9 | Needs V1 |
| How the session went, sleep, energy, anything for Coach. Saves as you type. | How the workout went, sleep, energy, anything else. | R4,R9 | Needs V2 |
| Weights, technique, how it felt. Saves as you type. | Weights, technique, how it felt. | R4 | Accept |
| Session note | Workout note | R9 | Needs V1 |

### Exercises and Progress (6)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Nothing matches. Try a muscle like biceps, or a machine like cable. | Nothing matches. Try a muscle like biceps, or equipment like cable. | R10 | Accept |
| No sessions logged yet. Your progress shows up here after your first ticked set. | Nothing logged yet. Progress shows up after your first ticked set. | R10,R4 | Accept |
| Best set per session as an estimated one-rep max (Epley), so more reps at the same load counts. The axis shows that estimate, not a weight you lifted. | Keep the formula name: "Estimated one-rep max (Epley) from your best set each workout, so more reps at the same load score higher. It is not a weight you lifted." | R4,R9 | Amend |
| {0}{1}{2} The dashed line is the trend, so one good or bad day does not decide the change. | {0}{1}{2} The dashed line is the trend. | R4 | Reject The dashed-line explanation is why the trend exists. Keep it. |
| Make a training day in Plan first, then add exercises to it from here. | Make a workout in Plan first, then add exercises to it here. | R9 | Needs V1 |
| Add to day | Add to workout | R9 | Needs V1 |

### Home (4)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Free, no ads, on every device. It suggests your next weight, and your own AI can coach you. | It suggests your next weight, and your own AI can coach you. | R4 | Accept |
| Logging a set: the weight you did last time, the suggested next weight and the reason for it | Logging a set, with last time's weight and the suggested next weight | R4 | Accept |
| Your data is yours: export it with one click. | Your data is yours: export it any time. | R4 | Accept |
| Send a ticket | Send feedback | R9 | Needs V3 |

### Request (4)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Yes Coach! could not take up your {0} "{1}". | "We decided not to go ahead with your {0} "{1}"." | R9 | Amend |
| Our apologies! You are welcome to send a new one. | Sorry about that. You are welcome to send a new one. | R4 | Accept |
| {0}Thank you very much for contributing! | {0}Thank you for contributing. | R4 | Accept |
| That is a lot of messages for one day. Try again tomorrow. | Too many messages for one day. Try again tomorrow. | R4 | Accept |

### Export and import (3)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Downloads are not available in this view. Use Copy instead. | Downloads are not available here. Use Copy instead. | R10 | Accept |
| No file needed. Fill in About you above (days per week and session length matter most), then copy the text below into a chat with an AI coach. | No file needed. Fill in About you above, then copy the text below into a chat with an AI. | R4 | Accept |
| Export whatever your app offers (CSV works best), or paste your notes. Choose the file or paste below. | Export whatever your app offers (CSV works best), or paste your notes. | R4 | Accept |

### Home, finish, connect (2)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Send day to Coach Claude for review? {0} is saved. Claude reads it through your connector and answers in a new chat. | {0} is saved. Claude reads it through your connector and replies in a new chat. | R4 | Accept |
| Two taps in your browser, then it opens like an app: | Add it from your browser, then it opens like an app: | R10 | Accept |

### App shell (1)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| {0} ticket | {0} request | R9 | Needs V3 |

### Exercises (1)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Missing an exercise? Add it here. It shows up in this list, in the exercise picker and in Progress like any other. | Missing an exercise? Add it here. It appears wherever exercises do. | R4 | Accept |

### Sign-in and account (1)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| Signed in as {0}. Your data syncs between your devices. | Signed in as {0}. Your data is the same on all your devices. | R9 | Accept |

### Page title and sign-in (1)

| Now | Proposed | Rule | My verdict |
|---|---|---|---|
| A free, ad-free workout tracker. Your account keeps your log and plan in sync between your devices. | A free, ad-free workout tracker. Your account keeps your log and plan on all your devices. | R9 | Accept |

## Where I disagreed with the reviewers

- **Amend** ("Best set per session as an estimated one-rep max (Epley), so more reps"): Keep the formula name: "Estimated one-rep max (Epley) from your best set each workout, so more reps at the same load score higher. It is not a weight you lifted."
- **Amend** ("Your coach gets your current plan, your progress over the last 3 month"): Keep it exact about what is shared: "Claude sees your plan, your progress over the last 3 months and your notes about your body. Say what to change, or leave it empty for a check-up."
- **Amend** ("Yes Coach! could not take up your {0} "{1}"."): "is not going to do" is blunt. Use: "We decided not to go ahead with your {0} "{1}"."
- **Reject** ("{0}{1}{2} The dashed line is the trend, so one good or bad day does no"): The dashed-line explanation is why the trend exists. Keep it.
- **Remove** ("Tap I ate something to save the time in one tap and fill it in later. "): The whole entry is about "I ate something", which no longer exists.
- **Decide** ("Reaching your protein target is enough: more is never shown as above."): The agent's rewrite is longer and still vague. Check what this release note describes before rewording.
- **Decide** ("What happened, and on which screen"): The tile hints help you choose before the form exists. The form hint helps while typing. Different moments. Keep the tile hints.
- **Decide** ("Something you want it to do"): Same as above.
- **Decide** ("What you like, what feels off"): Same as above.
- **Amend** ("In Settings, a tap or hover on a section now covers the whole bar."): "now works" is weak. Use: "In More, tapping anywhere on a section bar now opens it."

## What this did not cover

- **Exercise library:** 854 how-to descriptions (median 3 words, longest 27). Content, not interface text. Not reviewed string by string.
- **About 250 strings** that could not be traced to the current source. Some are old, some are built from pieces at run time, so they were not judged.
- **Strings assembled from pieces in code** are only seen as fragments. Wrong word order or wrong plurals in those (like "1 sets logged.") need the code, not the string list. I found that one by looking at the screen.
- **Privacy page, README and the owner-only ticket admin screens.**
- **The translations.** Every accepted change means five new translations.

## Before you apply any of this

- Every rewrite needs nl, es, de, fr and it versions in `tools/i18n/extra.json`, as CONTRIBUTING.md says. About 140 strings is a day of translation work done properly.
- Several tests check exact wording. They will fail until updated, as they did after the last copy changes.
- I would apply it in this order: the V1 to V4 vocabulary first (most rows, least argument), then the REMOVE list, then the rest.

## Second pass: what the first pass missed

You asked whether the 1,420 KEEP strings could really be clean. They are not. The first pass flagged 8 to 14% against a 20 to 35% guide, and I accepted "the strings are already short" without testing it. I then read the long kept strings (13+ words, 156) and the short kept sentences (5 to 12 words, 162). Findings:

| Now | Proposed | Rule | Why |
|---|---|---|---|
| Put your planned days in Apple, Google or Outlook calendar. (under "Add to calendar") | REMOVE | R4 | Restates the button. |
| Newest first. Working sets exclude warm-ups. | Working sets exclude warm-ups. | R4 | "Newest first" is visible. |
| Saved. Coach reads notes when you ask. | Saved. | R4, R9 | Explains who reads it, and uses "Coach" for the AI (V2). |
| • planned · ✓ done · … in progress. Tap a day to open its week. | • planned · ✓ done · … in progress | R4 | The week hint above already says to tap a day. |
| Spread over your meals works best. Carbs and fat have no target: eat what keeps your training going. | Spread it over your meals. Carbs and fat have no target. | R4 | Coaching filler after the fact. |
| Restore stopped after {0} of {1} items: {2}. Pick the file again to finish; items already restored are skipped. | Restore stopped after {0} of {1} items: {2}. Pick the file again to finish. Nothing is restored twice. | R10 | Same semicolon and "skipped" problem the reviewers flagged in the sibling restore error (id 1002) but kept here. |
| Numbers from the package. Saved, so you can log it again. / Just the calories of this portion, or a rough guess. Not saved for later. | From the label. Saved. / This portion only. Not saved. | R4 | The difference between the two (saved or not) is the useful part. The rest is sentence filler. |
| "Then choose the file here." at the end of the Hevy, FitNotes, Fitbod and JEFIT export instructions (4 strings) | Drop the sentence | R4 | The file button is right below. |
| Save a food using the nutrition values on its label. (under Your own foods) | Decide | R4 | Restates "Create a food", but it is the only place that says what an own food is. Keep or cut, your call. |

**Release notes as a class.** About 80 of the 156 long kept strings are changelog entries (20 to 35 words each). The first pass flagged some one by one. The fix is not 80 rewrites: show the latest five with an "Older" fold and shorten only those five.

**What a string list cannot show.** R2 (show the result, do not describe it) and R3 (hierarchy) depend on what is next to a string: whether a note restates a control, or whether a sentence should be a preview. The screen audit found most of those, but it covered only the 14 screens I opened. Screens I did not open (sign-in, the share picture, the plan wizard's copy step, the connector section, desktop, other languages) have had no context-aware check. The 1,264 kept strings under 13 words were only read as short labels.

**Net effect on the numbers:** at least 14 more strings flagged (about 156 + 14 = 170), plus the changelog class. I would treat "about 11 to 12% flagged, closer to 20% of what people read" as the honest figure, and still as a floor.
