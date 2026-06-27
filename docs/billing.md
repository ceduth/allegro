# Billing & spend safety

How Allegro is paid for, and how to make inadvertent LLM bills **structurally
impossible** during the phase where the loop isn't trusted yet.

> Token math and per-leg costs: [`cost-model.md`](./cost-model.md). Terms:
> [`glossary.md`](./glossary.md).

## Two products, two bills

| Surface | What it is | Paid by |
|---|---|---|
| **Dev** — Claude Code in the terminal | building Allegro | your **Max** subscription. No API key, no per-token charge. |
| **Runtime** — the in-app coach LLM | the app calling a model per turn | a **separate Console API key**, billed per token. **Max does not cover this.** |

- Keep the keys split. The app authenticates with the **Console key only** — never the
  Max login (that violates the ToS and has gotten accounts disabled).
- Local STT/TTS (faster-whisper, kokoro) need **no account, no key, no per-minute bill**.

## The guarantee: mock the LLM first

Free STT/TTS only makes an LLM bill *visible*. What makes an inadvertent bill *impossible*
is stubbing the LLM itself. The registry makes this one line.

- Add a **`mock` LLM provider** — canned classify/answer, **zero network calls**.
- Point `allegro.pipeline.yaml` at it for all spine + A/B/C/E work.
- Most of the test table doesn't need a real model anyway — only implicit-advance (C3)
  and free-form answers (D) do, and those can be faked deterministically.
- **Regression test:** assert the mock is called **0 times** across the silence / noise /
  advancement cases. "Nothing calls the LLM inadvertently" becomes a CI check, not a hope.

## Before the first *real* LLM call

Pre-flight checklist — do all of these before switching `llm.provider` off `mock`:

- [ ] Console API key created, **separate** from the Max login.
- [ ] **Spend limit** set low on that key/workspace (verify the exact control — Console
      settings move).
- [ ] **Usage email alerts** enabled.
- [ ] Turn log confirmed writing `source:llm` on every model call (your inadvertent-call
      detector).
- [ ] Mock-call-count regression test passing.

Then flip to a real model and watch the log: any `source:llm` you didn't expect is a bug,
caught immediately and cheaply.

## Free legs run locally

- STT (faster-whisper) and TTS (kokoro) run on your **dev machine** in Phase 0 — the
  pipeline already treats them as swappable nodes, so "local" is just which adapter you
  point at.
- With a `mock` (or spend-capped) LLM + local audio, the **entire dev loop has a hard,
  knowable cost ceiling** — at or near $0.

## Cost ceiling by configuration

| Config | LLM | STT/TTS | Worst-case dev cost |
|---|---|---|---|
| Phase 0a | `mock` | local | **$0** |
| Phase 0b | real, capped | local | bounded by the spend cap |
| Hosted baseline | real | paid (Deepgram/Cartesia) | ~$0.30/session (see spike-plan) |
