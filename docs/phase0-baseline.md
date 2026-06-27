# Phase 0 — baseline results

Fill this in during the **first live cook** on the real rig. The point is not to pass —
it's to record *how badly stock defaults fail* the kitchen test, as the before-picture
that Phase 1 tuning is measured against. A messy result here is a successful Phase 0.

> Spec: [`../phase1-kitchen-test.md`](../phase1-kitchen-test.md). Plan & phasing:
> [`spike-plan.md`](./spike-plan.md). Turn-by-turn evidence comes from
> `logs/session.jsonl`.

## Run metadata

| Field | Value |
|---|---|
| Date | _____ |
| Tester (beginner, unseen recipe) | _____ |
| Recipe | `weeknight_skillet` (chop · sauté · raw-protein · timed simmer) |
| Commit | `git rev-parse --short HEAD` → _____ |
| Log file | `logs/session.jsonl` |

## Config under test (stock defaults — DO NOT tune)

| Node | Setting | Value |
|---|---|---|
| VAD | provider / confidence / stop_secs | silero / 0.7 / 0.5 (stock) |
| Interruptions | `runtime.allow_interruptions` | **true** (barge-in ON) |
| STT | provider / model | deepgram / nova-3 |
| LLM | provider / model | anthropic / claude-haiku-4-5 |
| TTS | provider / model | cartesia / sonic-2 |

> Record any deviation (different keys, a `# VERIFY` item that had to change to boot) here:
> _____

## Results

Mark **PASS / FAIL** per the spec. Paste the relevant `logs/session.jsonl` line(s) as
evidence — per the spec, most failures are visible directly in the log.

### A. Noise resilience — *kill criterion, must be 100% PASS*

| # | Case | Result | Log evidence / what happened |
|---|------|--------|------------------------------|
| A1 | Faucet on mid-instruction | _____ | |
| A2 | Pan sizzle mid-instruction | _____ | |
| A3 | Background chatter mid-instruction | _____ | |
| A4 | Blender 5s while idle | _____ | |
| A5 | Metal spoon dropped near phone | _____ | |

### B. Silence handling — *kill criterion, must be 100% PASS*

| # | Case | Result | Log evidence / what happened |
|---|------|--------|------------------------------|
| B1 | Silent + chopping 3 min | _____ | |
| B2 | "rest 5 min", say nothing | _____ | |
| B3 | Silent 30s mid-step, then resume | _____ | |

### C. Advancement (only on explicit signal)

| # | Case | Result | Log evidence |
|---|------|--------|--------------|
| C1 | "next" | _____ | |
| C2 | "ok, done with that" | _____ | |
| C3 | "the onions are soft now" (implicit) | _____ | |
| C4 | Implicit cue before the raw-chicken step | _____ | |

### D. Intents (route without advancing)

| # | Case | Result | Log evidence |
|---|------|--------|--------------|
| D1 | "say that again" | _____ | |
| D2 | "how much salt?" | _____ | |
| D3 | "is it done yet?" (the trap) | _____ | |
| D4 | "go back to the marinade" / browning | _____ | |

### E. Timers (only allowed proactive speech)

| # | Case | Result | Log evidence |
|---|------|--------|--------------|
| E1 | Reach the simmer step → timer arms | _____ | |
| E2 | Timer elapses while silent → speaks once | _____ | |
| E3 | Untimed step, silent past 10 min → never speaks | _____ | |

### F. End-to-end

| # | Case | Result | Notes |
|---|------|--------|-------|
| F1 | Full hands-free cook, counter noise on | _____ | |

## Tally & verdict

- A passes: __ / 5   ·   B passes: __ / 3   → **kill criteria met?** ☐ yes ☐ no
- C: __ / 4   ·   D: __ / 4   ·   E: __ / 3   ·   F1: ☐ pass ☐ fail

**Expected at baseline:** A largely FAILS — with `allow_interruptions: true`, kitchen noise
should cut the agent off mid-sentence (A1–A3) and possibly trigger reactions (A4–A5). That
failure is the data that justifies the Phase 1 work: barge-in OFF + VAD tuning against A1–A5.

**Top failures to fix first (ranked):**
1. _____
2. _____
3. _____
