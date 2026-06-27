# Allegro — spike plan

Hands-free, voice-driven cooking coach. This doc is the living plan. The PASS/FAIL
table in [`../phase1-kitchen-test.md`](../phase1-kitchen-test.md) is the spec; the
invariants in [`../CLAUDE.md`](../CLAUDE.md) are non-negotiable.

## The unifying idea: one declarative pipeline graph

Model-swapping (paid ↔ OSS) and the eventual visual editor are the **same thing viewed
two ways** — swapping is editing a config by hand; the visual editor is a GUI over that
identical config. Nail the schema now and the visual layer is front-end work later, not
a re-architecture.

```yaml
# allegro.pipeline.yaml — single source of truth.
# Hand-edited in Phase 0; the xyflow editor edits THIS exact file in Phase 3.
transport: { type: webrtc }                 # phone browser, no cloud account
nodes:
  vad:   { provider: silero,    params: { confidence: 0.7, stop_secs: 0.5 } }  # OSS · stock
  stt:   { provider: deepgram,  model: nova-3 }            # PAID  → swap: faster-whisper (OSS)
  coach: { type: builtin }                                 # ★ in-house, NOT swappable
  llm:   { provider: anthropic, model: claude-haiku-4-5 }  # PAID  → swap: ollama / vllm (OSS)
  tts:   { provider: cartesia,  model: sonic-2 }           # PAID  → swap: kokoro (OSS)
```

- A **provider registry** maps `provider` → adapter. Each adapter implements its leg's
  interface. **Swapping a model = one line. Adding a provider = one adapter + one
  register call.** Paid vs. OSS is just which adapter you point at.
- `coach` is the **fixed spine** — state machine, intent classifier, timers, safety
  guardrail, turn log. It is *not* a swappable node. Everything bought plugs in around it.

## Phasing

### Phase 0a — Spine, bill-safe ($0)
`mock` LLM (zero network calls) + local STT/TTS (faster-whisper, kokoro). Build the
`coach` spine + turn log. Validate silence / noise / advancement logic against the
A/B/C/E cases with the mock (logic only — real A1–A5 acoustics are a 0b/live-rig
question). **Regression test: assert the LLM is called 0 times** on the no-LLM cases.
Cost: **$0**. See [`billing.md`](./billing.md).

### Phase 0b — Honest baseline (spend-capped)
Switch to the real stack: Pipecat + Deepgram + Cartesia + Haiku, `SmallWebRTC` web client
in the phone browser. **Do the billing pre-flight first** (Console key, spend cap, alerts).
**Honest defaults, no tuning** — interruptions ON, stock VAD. Run the A–F table once and
record FAIL counts. **Output = the baseline turn log, not a working coach.** (~$0.30/session.)

### Phase 1 — Pass the kitchen test
Tune VAD against A1–A5 first. Barge-in OFF (half-duplex). Drive advancement from the
intent classifier, not Pipecat's turn-detector. Harden C/D/E. Gate: **A+B 100% PASS** and
a clean F1 cook. VAD-gating here also halves the STT bill — kill criterion and cost lever
are the same lever.

### Phase 2 — Model-swap hardening
Local STT/TTS (faster-whisper, kokoro) land in 0a; what remains here is the OSS **LLM**
swap (Ollama/vLLM) behind the same interface, plus the scale-time migration. Each OSS
swap must **re-pass the A/B table** before it counts. Write the cost-migration triggers
into the README.

### Phase 3 — Visual plug-and-play (xyflow)
A React/xyflow editor where each node is a graph node, the provider is a dropdown from
the registry, params are a node inspector, and **the graph serializes back to
`allegro.pipeline.yaml`.** No separate runtime; the YAML stays the source of truth.

## Cost model (per ~30-min cook, hosted)

| Leg | Basis | Cost |
|---|---|---|
| STT (Deepgram Nova-3, $0.0077/min) | VAD-gated ~5 min sent | ~$0.04 (continuous open mic: ~$0.23) |
| TTS (Cartesia, ~$35/M chars) | ~5,000 chars spoken | ~$0.18 |
| LLM (Haiku 4.5, $1 in / $5 out per MTok) | ~20 turns, recipe re-injected | ~$0.06 |

**~$0.30/session** once VAD gates the mic; ~$0.47 streaming continuously. STT-gating is
the biggest cost lever; TTS is the first leg to migrate to self-hosted Kokoro at scale;
Haiku is noise — don't optimize it.

**Migration triggers:** swap TTS→Kokoro at ~1k sessions/mo; STT→faster-whisper when its
bill clears a box (gated on re-passing A/B); keep LLM on Haiku.

## Scope guardrail

In Phase 0 the "graph" is just the YAML + interfaces + a registry dict — **not** a plugin
framework. Earn the declarative schema (which serves both model-swap and xyflow) without
building either system yet.
</content>
</invoke>
