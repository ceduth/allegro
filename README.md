# Allegro

Hands-free, voice-driven cooking coach. Prop a phone on the counter, cook by voice in a
noisy kitchen, never touch the screen. See [`docs/spike-plan.md`](docs/spike-plan.md) for
the plan and [`phase1-kitchen-test.md`](phase1-kitchen-test.md) for the acceptance gate.

## Status: Phase 0 — baseline spike

The point of Phase 0 is **not** a working coach. It's to wire the cascaded pipeline on
honest stock defaults and **measure how badly it fails** the A–F kitchen table — the
recorded turn log is the deliverable. No tuning here; tuning is Phase 1.

```
mic → SmallWebRTC → Silero VAD → Deepgram STT → CoachProcessor → Cartesia TTS → speaker
                                                 └ in-house core (the product)
```

## Layout

| Path | What |
|---|---|
| `allegro.pipeline.yaml` | Declarative pipeline — the single source of truth (swap models here) |
| `allegro/core/` | ★ The product: state machine, intents, timers, safety, coach. Pure, tested. |
| `allegro/adapters/` | The "buy" legs behind interfaces: deepgram/cartesia/anthropic + OSS stubs |
| `allegro/registry.py` | provider name → adapter (the swap surface) |
| `allegro/obs/turnlog.py` | per-turn JSONL log (transcript · vad · intent · pointer before/after) |
| `allegro/bot.py` | Pipecat wiring, built from the YAML; FastAPI for the phone browser |
| `tests/test_core.py` | The C/D/E/A/B table as deterministic text-level tests |

## Docs

| Doc | What to expect |
|---|---|
| [`docs/spike-plan.md`](docs/spike-plan.md) | The plan: declarative-pipeline spine, phasing (0a→3), cost model, model-swap + xyflow path. Start here. |
| [`docs/runbook-local.md`](docs/runbook-local.md) | Step-by-step to run the $0 local voice loop on a phone (install, macOS gotchas, model downloads, troubleshooting, teardown). |
| [`docs/phase0-baseline.md`](docs/phase0-baseline.md) | Fill-in A–F results template for the first live cook — the recorded baseline. |
| [`docs/billing.md`](docs/billing.md) | How it's paid for, and how to make an inadvertent LLM bill structurally impossible (mock-first, spend pre-flight). |
| [`docs/cost-model.md`](docs/cost-model.md) | Per-cook token budget, leg-by-leg cost, self-hosted vs cloud. The LLM is the cheap leg; STT/TTS is the spend. |
| [`docs/walkthrough.md`](docs/walkthrough.md) | One cook traced turn by turn — how silence/noise are ignored, where each (tiny) LLM call comes from. |
| [`docs/glossary.md`](docs/glossary.md) | Shared terms (leg, turn, fallback turn, re-injection, …) used across the other docs. |

## Run the tests (no API keys, no Pipecat needed)

```bash
python3 -m pytest -q
```

The core runs on the standard library alone, so the acceptance logic is verifiable
without any provider installed.

## Run the bill-safe local profile first (Phase 0a, $0, no keys)

The `mock` LLM makes a runtime bill structurally impossible (zero network calls); STT/TTS
run locally (faster-whisper + Kokoro, offline after first model download). No API keys.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[live,dev]"
ALLEGRO_PIPELINE=allegro.pipeline.local.yaml python -m allegro.bot
```

Validate the spine + A/B/C/E logic here for free before spending a cent.

## Run the hosted baseline bot (Phase 0b)

Switch to the hosted stack — needs the three API keys. **Do the billing pre-flight in
[`docs/billing.md`](docs/billing.md) first** (Console key, spend cap, alerts).

```bash
cp .env.example .env   # then fill in DEEPGRAM/CARTESIA/ANTHROPIC keys
set -a; source .env; set +a
python -m allegro.bot   # uses allegro.pipeline.yaml (hosted) by default
```

Open `http://<your-computer-ip>:7860/client` in the **phone's** browser (phone and
computer on the same Wi-Fi), allow the mic, and cook. Every turn lands in
`logs/session.jsonl`. Run the A–F table from `phase1-kitchen-test.md` and record the
PASS/FAIL — that's the baseline.

> `bot.py` runs under Pipecat's dev runner (`pipecat.runner.run`), which serves `/start`,
> `/api/offer`, and the `/client` UI — validated against pipecat-ai 1.4.0. The remaining
> unknown is the live voice loop itself (mic → STT → coach → TTS on a real connection).

## Swapping models

Edit the active profile — change a node's `provider`/`model`. Built-in providers:

| Leg | Hosted (paid) | Local (OSS, $0) | Mock |
|---|---|---|---|
| STT | `deepgram` | `faster_whisper` | — |
| TTS | `cartesia` | `kokoro`, `piper` | — |
| LLM | `anthropic` | `ollama` *(Phase 2 stub)* | `mock` |

`ollama` is the only remaining `NotImplementedError` stub (Phase 2). **Cost-migration
triggers** (per `docs/spike-plan.md`): swap TTS → Kokoro at ~1k sessions/mo; STT →
faster-whisper when its bill clears a box (re-pass A/B first); keep the LLM on Haiku.
