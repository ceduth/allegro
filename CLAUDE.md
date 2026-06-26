# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Phase 0 (baseline spike) scaffolded. The cascaded pipeline is wired on stock defaults to
measure how badly it fails the kitchen test — see `docs/spike-plan.md`. The in-house core
(`allegro/core/`) is pure and fully tested; the Pipecat wiring (`allegro/bot.py`) needs a
live device + API keys to validate.

Commands:
- **Tests** (no keys / no Pipecat needed — core runs on stdlib): `python3 -m pytest -q`
- **Live baseline bot**: `pip install -e ".[live,dev]"`, fill `.env` from `.env.example`,
  then `python -m allegro.bot` and open `http://<computer-ip>:7860/client` on the phone.
- Provider swaps live in `allegro.pipeline.yaml`; adapters/registry in `allegro/adapters/`.

A few Pipecat constructor/event details are version-sensitive and marked `# VERIFY` in
`bot.py` — confirm against the installed `pipecat-ai` on first live run.

## What this is

**Allegro** is a hands-free, voice-driven cooking coach. A user props a phone on the
counter and cooks a recipe by voice while their hands are busy and the kitchen is noisy.
The agent reads out recipe steps, answers questions, runs timers, and advances through
the recipe — all without the user touching the screen.

Phase 1 is a concept-proof gated on a live kitchen acceptance test
(`phase1-kitchen-test.md`). The concept ships only when that test passes. Read that file
before building anything: its PASS/FAIL table *is* the spec.

## Core design invariants (non-negotiable)

These come from the Phase 1 acceptance test and constrain every implementation choice.
They are the "big picture" — get them wrong and the product fails its kill criteria.

- **Silence is never a signal.** The agent must not nag ("still there?"), and must not
  auto-advance when the user goes quiet. A user can chop silently for minutes, or wait
  out a "rest 5 min" step, and the agent stays silent and holds its position. (Test
  sections A/B — these are the *kill criteria*: must be 100% PASS.)

- **Advancement is intent-only.** The recipe pointer moves forward only on an explicit
  user signal ("next", "done with that", or an implicit cue like "the onions are soft").
  Before a safety/irreversible step, the agent confirms first rather than auto-advancing.
  (Test section C.)

- **Intents route without advancing.** "Say that again", "how much salt?", "is it done
  yet?", "go back to the marinade" must answer or re-position *without* moving the pointer
  forward. "Is it done yet?" advancing is called out as the classic trap. (Test section D.)

- **Noise must not cut the agent off.** Faucet, sizzle, background chatter, a dropped
  spoon, a blender — none of these may interrupt the agent mid-sentence or be treated as
  user input. VAD (voice activity detection) tuning against the section-A cases is the
  *first* thing to get right; everything else depends on clean detection. (Test section A.)

- **Timers are the only allowed proactive speech.** A timed step ("simmer 10 min") arms a
  timer automatically; when it elapses the agent speaks exactly once ("time's up"). With
  no timer and no user input, the agent never breaks silence. (Test section E.)

## Implementation guidance from the spec

- **Log every turn**: raw transcript, classified intent, and the pointer position before
  and after. Per the spec, most failures are diagnosable directly from this log — build
  this observability in from the start.
- Model the recipe as a step list with an explicit **pointer**; intents are classified
  against the current step and either answer-in-place, advance, or jump.
- Tune VAD before anything else — it is the foundation the rest of the behavior sits on.

## Architecture (cascaded pipeline)

mic → noise-robust VAD → STT → recipe state machine → LLM → safety guardrail → TTS → speaker

- **Buy off-the-shelf:** STT, TTS, the LLM. Keep the LLM behind a swappable
  interface — do not hardwire one provider.
- **Build in-house (this is the product):** VAD tuning, the recipe state machine,
  the intent classifier, timers, and the safety guardrail.
- **The state machine is the single source of truth for position.** The LLM is
  stateless per turn; re-inject current step + completed steps + skill level every turn.
- **Safety guardrail:** any answer touching doneness, temperature, or raw protein
  routes to curated safety rules. When uncertain, the safe answer wins — never a
  confident invented fix.

## Phase 1 scope

English only. One hardcoded recipe (sauté + timed simmer + chop). No FR-CA voice,
no personalization, no pantry/receipts — later phases. First move: wire the pipeline
with DEFAULT voice settings to baseline how badly defaults fail against kitchen noise,
before tuning anything.
