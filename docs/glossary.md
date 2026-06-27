# Glossary

Shared terms used across the docs ([`cost-model.md`](./cost-model.md),
[`walkthrough.md`](./walkthrough.md)) and the invariants in
[`../CLAUDE.md`](../CLAUDE.md).

- **Answer (LLM job) / free-form answer** — asking the LLM to reply to a cook's question
  ("how much oil?") in 1–2 spoken sentences. Output ≈ 40–60 tokens.
- **Cascaded** — a pipeline of separate STT → LLM → TTS stages (vs. one combined model).
- **Classify (LLM job)** — asking the LLM to label an unclear utterance as advance /
  question / repeat / jump / unknown. Output ≈ one word.
- **Fallback turn** — a turn the rule layer couldn't classify, so it pays for an LLM call.
  The only turns the LLM costs anything on.
- **Leg** — one stage of the pipeline that costs money to run: STT, the LLM, or TTS.
- **Native speech-to-speech** — a single audio-in/audio-out model. Simpler wiring, but
  context accumulates internally → ~10× cost. We don't use it.
- **Pointer** — the index of the current recipe step. Held by the state machine; moved
  only by an explicit intent, never by silence.
- **Rule layer** — deterministic keyword matching that classifies clear commands
  ("next", "repeat", "go back to…") with **no LLM call**. Handles most turns for free.
- **Safety guardrail** — curated rules that intercept doneness / temperature / raw-protein
  questions **before** the LLM, so the model never invents an unsafe answer.
- **Step re-injection** — each LLM call is given only the *current recipe step* + the new
  utterance. Fresh every call; nothing carried over.
- **STT / TTS / VAD** — speech-to-text (hear) / text-to-speech (speak) / voice activity
  detection (decide real speech vs. kitchen noise).
- **Token** — the billing unit. ≈ 0.75 words. Priced per million, input and output
  counted separately.
- **Transcript accumulation** — the anti-pattern: resending the whole conversation so far
  on every call. Input grows each turn → cost balloons. We avoid this.
- **Turn** — one round of the loop: the cook says (or doesn't say) something, the agent
  reacts.
- **User turn** — a turn driven by the cook speaking (vs. a timer firing on its own).
