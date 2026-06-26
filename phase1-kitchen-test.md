# Phase 1 — Kitchen acceptance test

**Gate:** Phase 1 ships only when every test below passes. If any FAIL in section A or B holds after tuning, the concept is not yet proven — stop and fix before building further.

## Rig
- Phone propped on counter, ~3 ft from where you stand. Screen on.
- One real recipe loaded (pick one with a sauté step, a timed simmer, and a chop step).
- A beginner tester who has not seen the recipe.
- Noise sources on hand: faucet, a pan on heat (real sizzle), a phone playing background chatter/music, a blender.

Run each test live, in the noise condition stated. Mark PASS / FAIL.

---

## A. Noise resilience (must not cut itself off)

| # | Action | PASS | FAIL |
|---|--------|------|------|
| A1 | Agent is mid-instruction; turn the faucet on | Agent finishes the full sentence | Agent stops mid-sentence |
| A2 | Agent is mid-instruction; a pan sizzles loudly | Agent finishes | Agent cuts off |
| A3 | Agent is mid-instruction; background chatter plays | Agent finishes | Agent cuts off |
| A4 | Run the blender for 5s while agent is idle | Agent stays silent, does nothing | Agent reacts / responds to the noise |
| A5 | Drop a metal spoon near the phone | No reaction | Agent treats clang as input |

## B. Silence handling (must not nag or auto-advance)

| # | Action | PASS | FAIL |
|---|--------|------|------|
| B1 | After an instruction, stay silent and chop for 3 min | Agent stays silent the whole time | Agent prompts ("still there?", "ready?") |
| B2 | Step says "rest 5 min"; say nothing | Agent does not advance on its own | Agent moves to next step |
| B3 | Stay silent 30s mid-step, then resume working | No prompt, no advance | Any unprompted speech |

## C. Advancement (only on explicit signal)

| # | Action | PASS | FAIL |
|---|--------|------|------|
| C1 | Say "next" | Advances one step | Anything else |
| C2 | Say "ok, done with that" | Advances | Stays / misroutes |
| C3 | Say "the onions are soft now" (implicit) | Advances OR asks "ready to move on?" | Ignores it |
| C4 | Before a safety/irreversible step, give an implicit cue | Confirms first, does not auto-advance | Advances without confirming |

## D. Intents (route without advancing)

| # | Action | PASS | FAIL |
|---|--------|------|------|
| D1 | Say "say that again" | Repeats current step, pointer unchanged | Advances |
| D2 | Ask "how much salt?" | Answers from current step, pointer unchanged | Advances |
| D3 | Ask "is it done yet?" | Answers, stays on step | Advances (the classic trap) |
| D4 | Say "go back to the marinade" | Jumps back to that step | Fails to move / advances forward |

## E. Timers (the only allowed proactive speech)

| # | Action | PASS | FAIL |
|---|--------|------|------|
| E1 | Reach a "simmer 10 min" step | Timer arms automatically | No timer |
| E2 | Let the timer elapse while silent | Agent speaks once: "time's up" | Stays silent / nags repeatedly |
| E3 | A step with no timer; stay silent past 10 min | Agent never speaks | Agent breaks silence |

## F. End-to-end outcome

| # | Action | PASS | FAIL |
|---|--------|------|------|
| F1 | Beginner cooks the full recipe hands-free, counter noise on | Finishes the dish without touching the phone and without the coach breaking | Any touch needed, or any A/B failure during the cook |

---

## Scoring
- **A + B must be 100% PASS.** These are the kill criteria.
- **C, D, E:** any single FAIL is a fix-before-ship bug, not a kill.
- **F1 is the proof.** One clean hands-free cook in a noisy kitchen = Phase 1 holds = concept is real.

## Notes for the build
- Tune VAD against A1–A5 first; everything else depends on clean detection.
- B and C share one rule: silence is never a signal. Advancement is intent-only.
- Log every turn: raw transcript, classified intent, pointer before/after. Most failures are visible in that log.
