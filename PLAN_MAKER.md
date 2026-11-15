# Plan maker: how to fix it

How Yes Coach should build a training plan (with or without an AI), check it, and keep it working. This follows from a review of the current code: the progression engine is sound, but the plan around it has no volume model, no frequency rule, fixed reps that break double progression, and AI plans that are barely checked.

## 0. After review (one reviewer with full context, one cold)
Both reviews agreed on the big problems; this version follows them.

- **Muscle data first.** The library's muscle fields are free text (about 70 variants, "Front and side delts", "shoulders", "Legs"). A fixed list of muscles and a mapping for every entry comes before any counting; each muscle is credited at most once per exercise. Your own and imported exercises fall back to their body part and are shown as "not counted" instead of raising volume warnings.
- **Rules in tiers.** Two 45-minute sessions cannot hold 13 patterns and full volume bands. Must-haves every week: a knee-dominant lift, a hinge, a push and a pull. The rest (vertical press, leg curl, arms, delts, calves, core) fills in while the time budget allows. Volume below the band because of time is information, not a warning.
- **Goal and person.** Bands follow the three experience levels onboarding already asks (new, some, years) and the goal; "new" and the lose-weight goal get a lower band. 1 day a week: one full-body day. 7 days: 6 lifting days and an easy day. Shoulder limits use the library's own flags (skip is an error, careful a warning), not English note text.
- **Warm-up flag is a bug today.** The app's plan save and the connector drop the warm-up mark, so a day replaced by Claude loses warm-up marks set by hand. Fixed first, on its own.
- **No surprise changes.** Existing plans are never rewritten automatically. The check shows at most 3 findings (errors first, then "+N more"); "Fix my plan" is offered only for errors or a missing must-have and goes through the existing adjust flow with undo.
- **Web users paste.** The automatic fix round only exists where the page can call Claude itself. On the website the findings come with a "Copy fix request". Fixes that need no judgement (fixed reps to a range by role, rest clamped, warm-up flag, isolation after compounds) are done by the app before the preview.
- **Effort tap only when it matters.** Asked per exercise only when every set reached the top of the range (the only case where it changes the next weight), skipped when the per-set RIR box is on, and stored on the last working set relative to the planned effort.
- **Big jumps** apply to kg and assisted exercises only, need extra reps by the size of the jump (about 1 rep per 3%, at most 4), worked out in the rule with nothing stored.
- **The connector repeats the check.** The Edge Function cannot import from the app, so the check is written once (`plancheck.js`) and copied into the function by a sync script, with a test that the copy matches. `get_plan` and `save_training_day` return it, so Claude sees it in a chat too.
- **Cut:** the AI's own set count, a separate Fix with Claude button, "suggest a weighted version" (the engine already says add weight), and a general warm-up item by default.
- **Calibrate before showing it.** The check card is shown to the owner first (an email list in config, like Strava), and only to everyone once the built-in plans pass it.
- **Easier week** is a card with a Start button on the week view, never automatic; its sessions are tagged and left out of the next-weight rule. It comes last.

## 1. What a good plan does

1. **Frequency.** Every major muscle is trained at least twice a week when there are 3 or more sessions a week. Two sessions a week: full body twice.
2. **Volume.** Weekly hard sets per muscle sit in a band that fits the person (table in 3.2). Too little and nothing happens; far too much and recovery suffers.
3. **Balance.** At least as many pulling sets as pushing sets. Quads and the back of the legs both trained. Arms, side delts, rear delts and calves get direct work.
4. **Coverage.** Each week has a squat or leg press, a hinge, a leg curl, a horizontal and a vertical press, a horizontal and a vertical pull, and core.
5. **Rep ranges, not fixed reps.** Double progression needs a range: add reps until every set reaches the top, then add one weight step.
6. **Planned effort.** Each exercise has a target of reps in reserve (RIR). The first two weeks are for finding weights.
7. **Warm-ups apart from work.** Warm-up exercises and ramp sets are marked as warm-up and are never counted or progressed.
8. **Fits the session.** The estimated time fits the session length.
9. **Notes are cues.** Notes say how to do it ("elbows to your hips"), never numbers or dates that go stale.

## 2. The parts to build

### 2.1 Plan check (new, pure module `plancheck.js`, like `progression.js`)
One function, `check(plan, ctx)`, used everywhere: the starter builder, the AI loop, the Plan page and the connector.

Input: the days with their items, the weekly schedule (sessions a week, rotation or fixed days), the exercise library (primary and secondary muscles per exercise, already in the library), the person (experience, goal, session length, place, shoulder note).

It works out:
- **Sets per muscle per week.** A working set counts 1 for each primary muscle and 0.5 for each secondary muscle. With a rotation, a day counts `sessions a week / days in the rotation` times a week.
- **Sessions per muscle per week** (a muscle counts for a session when it gets 2 or more sets there).
- **Time per session:** per working set 40 s plus its rest; warm-up sets 60 s each; 5 min general warm-up.
- **Pattern coverage** and **push/pull ratio**.

It returns findings with a level:
- **error** (must be fixed): unknown exercise, equipment not at their place, an exercise marked hard on shoulders when their notes mention a shoulder, a session more than 20% over its length, a heavy compound for the same muscle on consecutive days.
- **warning:** a major muscle trained once a week while there are 3 or more sessions; weekly sets outside the band; pull sets below push sets; a missing pattern; isolation before compounds; fixed reps on a weighted exercise; a note with numbers or dates; a warm-up drill not marked as warm-up.

### 2.2 Starter plans without AI (rewrite of `localPlan`)
- Splits by sessions a week:
  - 2: Full body A, B
  - 3: Full body A, B, C
  - 4: Upper A, Lower A, Upper B, Lower B
  - 5: Upper, Lower, Push, Pull, Legs
  - 6: Push, Pull, Legs, twice
- Every exercise slot has a role: **main** (first heavy compound), **secondary** (compound), **isolation**, **core**. Reps, RIR and rest come from the role (3.3), not from the library's single default.
- Volume is cut to the band for their experience by the number of sets, not by dropping patterns.
- A 5-minute general warm-up item, marked warm-up.
- Every combination (sessions 2 to 6, gym/home/bodyweight, short/medium/long, new/experienced: 90 plans) is generated in a test and must pass the check with no errors and no frequency, balance or coverage warnings.

### 2.3 Plans by an AI
- The prompt carries the rules in section 3 (the template is in section 4).
- The answer is run through the check. On errors or warnings, the AI gets one more turn: "Fix these: ..." with the findings. Whatever is left is shown in the preview as plain lines ("Biceps: 3 sets a week, the range is 6 to 12").
- The AI also returns its own count of sets per muscle per week. The check compares it with its own count; a big gap means the AI did not reason about volume, which is a finding too.

### 2.4 Plan page
- A **Plan check** card: sets per muscle per week as a short bar list with the band, sessions per muscle, the time per session, and the findings in plain words.
- **Fix with Claude** sends the findings with the plan (only when an AI is connected).

### 2.5 Progression engine (`progression.js`)
- **Ranges by default.** Fixed reps stay only for timed holds and "max".
- **Big jumps.** When one weight step is more than 10% of the load (8 to 10 kg dumbbells), the top of the range goes up by 2 reps before the weight goes up: "Big jump next: 2 more reps first".
- **Effort in one tap.** After the last set of an exercise: Easy / Right / Hard (stored as RIR 3, 1, 0). Hard at the top of the range holds the weight; that rule exists already but has no input today.
- **Planned easier week.** After 6 weeks of training since the plan started or the last easier week, or when 40% or more of the exercises stalled in the last two weeks, the app offers an easier week: same weights, half the sets, 3 to 4 reps in reserve.
- **Switch to an easier or harder variant.** Bodyweight with under 5 reps for two sessions: suggest the assisted version. 15 or more reps on every set: suggest a weighted version.

### 2.6 Connector
- `save_training_day` gets `warmup: true` per exercise (stored as kind warmup).
- `get_plan` returns the check: sets and sessions per muscle per week, time per session, findings. Claude sees it in reviews and plan changes.
- The descriptions say what a range does; the instructions stay descriptive.

## 3. The rules

### 3.1 Splits and frequency
As in 2.2. With a rolling week, the rotation alternates so the same muscles are not trained on two days in a row (Upper, Lower, Upper, Lower; never two lower days next to each other when there is room).

### 3.2 Weekly hard sets per muscle
Counting a primary muscle 1 and a secondary muscle 0.5. A hard set is a working set with 0 to 3 reps in reserve.

| Experience | Major muscles (chest, back, quads, hamstrings, glutes) | Small muscles (biceps, triceps, side delts, rear delts, calves) |
|---|---|---|
| New (under 6 months) | 6 to 10 | 4 to 8 |
| Some experience | 10 to 16 | 6 to 10 |
| Experienced | 12 to 20 | 8 to 14 |

Per session: at most 10 hard sets for one muscle; in total about 12 to 16 (45 min), 16 to 20 (60 min), 20 to 26 (90 min).

### 3.3 Reps, effort and rest by role

| Role | Reps | RIR | Rest |
|---|---|---|---|
| Main compound | 5 to 8 (new: 6 to 10) | 2 to 3 | 150 to 180 s |
| Secondary compound | 8 to 12 | 1 to 2 | 90 to 120 s |
| Isolation | 10 to 15 (calves and side delts 12 to 20) | 0 to 2, last set close to failure | 60 to 90 s |
| Core | 10 to 15, or 30 to 45 s | 1 to 2 | 45 to 60 s |

Weeks 1 and 2 of a new plan: 3 reps in reserve on everything, to find the weights.

### 3.4 Order of a session
1. General warm-up, 5 minutes (marked warm-up).
2. Main lift: the app adds the ramp sets.
3. Secondary compounds.
4. Isolation. Antagonist pairs (biceps and triceps, chest fly and rear delt) may be a superset, also to save time.
5. Core, at most 2 exercises.
Never two heavy compounds in a superset.

### 3.5 Loads (as today)
With history: about 90% of the recent best set at the planned reps. Without: no guess; the note is a calibration cue. Rounded to the person's weight step.

### 3.6 Notes
One short cue on how to do the exercise. No weights, reps, dates or "hold until": those live in the target, the reps and the progression.

## 4. Template: the rules for the AI

This replaces the `## Rules` section of `planPrompt` (and is the basis for the connector's plan guidance). `{...}` are filled in by the app.

```
## Rules
Build the plan so that it passes these checks. The app checks your answer and sends back what fails.

Split, from the sessions a week ({n}):
- 2: two full-body days. 3: three full-body days (experienced: upper, lower, full body).
- 4: upper, lower, upper, lower. 5: upper, lower, push, pull, legs. 6: push, pull, legs, twice.
- Every major muscle at least twice a week when there are 3 or more sessions.
- Never the same muscles heavy on two days in a row in the order of the days.

Weekly volume, in hard sets per muscle (primary muscle counts 1, secondary 0.5), for {experience}:
- major muscles (chest, back, quads, hamstrings, glutes): {major_band}
- small muscles (biceps, triceps, side delts, rear delts, calves): {small_band}
- at most 10 hard sets for one muscle in one session.
- pulling sets at least equal to pressing sets.

Each week has: a squat or leg press, a hinge, a leg curl, a horizontal press, a vertical press (leave it out if their notes mention a shoulder), a horizontal pull, a vertical pull, direct biceps, triceps, side delt and rear delt work, calves, and core.

Each session ({length}): {exercise_range} exercises, about {set_range} hard sets, in this order: main compound, secondary compounds, isolation, core.
Start every day with a 5-minute general warm-up item with "warmup": true. Never write warm-up sets as working sets.

Reps, effort and rest by role:
- main compound: reps "{main_reps}", 2 to 3 reps in reserve, rest_s 150 to 180
- secondary compound: reps "8 to 12", 1 to 2 in reserve, rest_s 90 to 120
- isolation: reps "10 to 15" ("12 to 20" for calves and side delts), last set close to failure, rest_s 60 to 90
- core: "10 to 15" or "30 to 45 s"
Use a range for every weighted exercise ("8 to 12"), never a single number: the app adds reps before weight.
The first two weeks are for finding weights: say so in the summary.

Loads: {load_rule}

Notes: one short cue on how to do the exercise, or null. No weights, reps, dates or "hold until" in notes.

Only exercise ids from the list, only equipment they have, nothing marked hard on shoulders if their notes mention a shoulder.

Before you answer, count the hard sets per muscle per week and the sessions per muscle, and fix the plan until the rules hold.

Answer with JSON only:
{"summary": "...", "days": [{"name": "Upper A", "kind": "Other", "focus": "...", "items": [{"ex": "l04", "sets": 3, "reps": "6 to 8", "target": "60", "rest_s": 150, "note": "...", "warmup": false}]}],
 "weekdays": [...], "weekly_sets": {"chest": 12, "back": 14, ...}, "mapping": {...}}
```

## 5. Order of work (after review)

| # | Work |
|---|---|
| 1 | Warm-up flag kept in the app's plan save and in the connector (bug fix) |
| 2 | Muscle list, mapping for every library entry, body-part fallback; test that every entry maps |
| 3 | `plancheck.js` (tiers, time budget, bands by experience and goal, rotation by unique days), its copy in the connector with a sync test, `get_plan` and `save_training_day` return the check |
| 4 | Built-in plans rewritten by role and range for 1 to 7 days; every combination passes |
| 5 | AI rules template, app-side fixes, check after the answer, one automatic fix round in the page, Copy fix request on the web; blind-agent plans scored before and after |
| 6 | Plan check card (owner first), Fix my plan for errors only |
| 7 | Progression: big-jump rule, effort tap, assisted-variant hint |
| 8 | Easier week card |

## 6. Decisions taken
1. **Experience:** the three levels onboarding already asks (new, some, years), guessed from imported history; changeable in Settings.
2. **Existing plans:** the check is shown; Fix my plan is offered only for errors or a missing must-have, with undo.
3. **Easier week:** a card with a Start button, never automatic.
4. **Effort tap:** only when every set reached the top of the range, and only when the per-set RIR box is off.

## 7. Where the numbers come from
The bands and rules follow the broad agreement of recent reviews on resistance training: more weekly sets help up to roughly 10 to 20 per muscle with diminishing returns; training a muscle twice a week is at least as good as once at the same volume and easier to recover from; sets taken to within about 0 to 3 reps of failure are what counts; rep ranges from about 5 to 30 all build muscle when effort is high, heavier ranges suit strength. They are starting points to tune with the blind-agent test and real logs, not fixed truths.
