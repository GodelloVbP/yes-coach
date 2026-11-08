# Yes Coach! design rules: text, hierarchy and controls

For anyone designing or changing a screen, human or AI. These come from a review of the Plan page. They sit on top of the Design section in CONTRIBUTING.md (tokens, phone first, 44 px targets, blocks).

## Why text is the problem

A lot of text on a phone screen has four costs, and each one is a reason to cut:

1. **Overload.** The person has to work to take it in.
2. **It is not read.** Walls of text are skipped, so the information is lost anyway.
3. **It is not understood.** Long text stacks up terms the person has to decode ("rotation", "moves up").
4. **No hierarchy.** From a distance, a block of same-weight text does not say what it is: a control, a help line or a status.

The test for every screen: **hold it at arm's length.** You should still tell what the title is, what you can change, what the main action is and what is only a status. If you cannot, the screen fails, whatever the text says.

## The rules

### 1. One job, one control pattern
Choosing one of several options always looks the same: the same chip, segment or radio shape wherever it appears. Two different looks for the same job read as two different behaviours. Underlined text pairs look like navigation, never use them for a setting.
*Check:* find every single-choice control on the screen. Do they look alike?

### 2. Show the result, do not describe it
If a choice changes something the person cannot guess, show the outcome (a small preview of the week, the changed number) instead of a sentence about it. A sentence under every control means the control is not clear enough.
*Check:* could the note under this control be replaced by a preview or a better label?

### 3. Hierarchy: label, then value, then help
- The label of a section is stronger than the help text under it, never the other way round.
- Help text is smaller and quieter than what it explains.
- Status is not styled like a warning. Callout boxes are for things that need attention.
*Check:* squint at the screen. Titles and actions must stand out; help must recede.

### 4. Text budget
- A headline and one short line is the default. Anything more has to earn its place.
- Say a thing once, where it is used. Do not restate what the control already says.
- Explain only when the result would surprise the person.
- Never write a sentence about how a sentence works.
*Check:* delete each note. Does anyone lose anything they needed?

### 5. Generated text: cap it, dedupe it, never dump state
Text built from data must have a limit: show three, then "+9 more". Remove repeats. Never print raw stored state (every move, every key) as a sentence. If the list would not read well at 12 items, it must not be a sentence.
*Check:* run it with 0, 1, 3 and 20 items.

### 6. Permanent and temporary do not share a place
Permanent settings and one-off changes (this week only) live in different places. A one-off belongs where the thing is (the week view), not under the settings that look as if they caused it.
*Check:* does anything below a setting look like its consequence when it is not?

### 7. Defaults first, advanced on demand
Pick a sensible default. Show the choice only when most people would change it. Everything else goes behind one tap. A new person should not meet every option on the first visit.
*Check:* what does a first-time user have to decide here? Can the default decide it?

### 8. Pickers that fit
- A picker with seven options is usually wrong. Offer the range people use (2 to 6) or a stepper.
- All chips fit on one row at 360 px, in the longest language. No stranded second row.
- Numbers need their unit in the label, not in a note.
*Check:* 360 px, German.

### 9. Internal names stay internal
The app's model (fixed weekdays, rotation, per_week) is not a UI term. Label the choice by what happens, in the person's words ("Skip missed days" / "Shift them to the next day"). If a label needs a paragraph, the model leaked.
*Check:* read the label aloud to someone who has never seen the app.

### 10. Copy does not contradict itself
Read each sentence as the person would. "4 sessions a week are spread over the 7 days you can train" says nothing when all 7 are available. Mixing two ideas (how many sessions, which days) in one sentence is the cause.
*Check:* one idea per sentence; no sentence that is true for every setting.

### 11. Secondary text is measured
Grey help text on a tinted block is the most common contrast failure. Measure it in light and dark.
*Check:* secondary text meets WCAG AA (4.5:1) on its actual background.

## Before a screen ships

- [ ] Arm's-length test: title, controls, main action and status are all distinguishable.
- [ ] No control has a note that restates it.
- [ ] Same job, same control look.
- [ ] Generated text tested at 0, 1, 3 and 20 items.
- [ ] Nothing temporary sits under a permanent setting.
- [ ] Nothing advanced is shown to a first-time user.
- [ ] Shown at 360 px in German with nothing wrapped badly or cut off.
- [ ] Secondary text measured for contrast.

## Worked example: the Plan page

What it did: a 95-word paragraph listing 12 moves (several repeated, most in the past) under the permanent schedule settings, two grey notes restating the controls, a 1 to 7 picker wrapping to two rows, and two single-choice controls with different looks.

Which rules it broke: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10.

What it should be: a schedule with a sensible default, one clear picker, miss-a-day labelled by its result and previewed, and "3 changes this week. Open this week" at most, placed on the week view.
