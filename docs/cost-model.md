# Cost model — runtime economics

Per-cook token budget, leg-by-leg cost, and the self-hosted vs cloud tradeoff.
The point of this doc: **the LLM is the cheapest leg. STT + TTS are the spend.**
Optimize accordingly.

> Prices are mid-2026 list rates, input/output per 1M tokens. They move quarterly —
> verify before committing. Figures are order-of-magnitude, not invoices.

---

## 1. The one rule

- **LLM fires only on fallback turns** (rule layer handles most) → tiny, intermittent.
- **STT + TTS run continuously** for the whole 30-min session → the real bill.
- Chasing a cheaper LLM saves tenths of a cent. Moving STT/TTS local saves dollars.

---

## 2. Token budget — one 30-min cook

Assumptions: ~30–40 user turns; rule layer handles most for free; LLM fires on
~8 implicit-cue classifications + ~10 free-form answers. **Only the current step is
re-injected per call** — no transcript accumulation, so calls stay flat and tiny.

| LLM job  | calls | input tok | output tok |
|----------|-------|-----------|------------|
| Classify | ~8    | ~960      | ~25        |
| Answer   | ~10   | ~1,100    | ~500       |
| **Total**| **~18** | **~2,060** | **~525** |

≈ **2.6K tokens / cook.**

---

## 3. Cost per cook, by leg

| Leg  | runs            | ~$ / 30-min cook |
|------|-----------------|------------------|
| LLM  | ~18 short calls | **$0.0004 – 0.005** |
| STT  | continuous      | **~$0.10**       |
| TTS  | continuous      | **~$0.10 – 0.20**|

- STT + TTS outweigh the LLM by **~200–300×**.
- LLM cost is a rounding error. STT/TTS is the lever.

---

## 4. LLM provider options (one-line yaml swap)

| Provider              | $/1M (in/out) | notes                                          |
|-----------------------|---------------|------------------------------------------------|
| DeepSeek V4 Flash     | 0.14 / 0.28   | cheapest; MIT weights; accepts Anthropic format → near drop-in |
| Gemini Flash-Lite     | ~0.25 / 1.50  | generous free dev tier                         |
| GPT nano tier         | 0.05 / 0.40   | classification-grade                           |
| Llama 4 Scout (Groq)  | 0.18 / 0.59   | fastest — latency, not price, is the win        |
| Claude Haiku 4.5 (current) | ~0.25–1 / 1.25–5 | already budget-tier               |

- Per-cook delta between any of these: **< 1 cent.** Pick on latency / format fit, not price.
- **Split the two jobs** (adapter already separates `classify` / `answer`): cheap-or-local
  for classify, a slightly better hosted call only for the rarer answer.

---

## 5. Self-hosted vs cloud

CPU latency scales with **output** tokens — which is exactly why the two jobs split:

| Job      | output | CPU (3–8B, ~5–15 tok/s) | verdict          |
|----------|--------|-------------------------|------------------|
| Classify | ~3 tok | < 1 s                   | **CPU-viable**   |
| Answer   | ~50 tok| ~4–10 s                 | **too slow live**|

**Recommended split:**
- Classify → **local model on CPU** (1–3B via Ollama/llama.cpp). Free, private, fast enough.
- Answer → **cheap hosted call**. Fires rarely; fraction of a cent.

**Full self-host tradeoffs:**
- ✅ Privacy — voice/recipe data never leaves the box.
- ✅ Zero per-token cost.
- ❌ GPU runs ~$3–8/hr **whether idle or not**.
- ❌ Break-even vs hosted API only around **~50K requests/day**.
- ❌ Single-stream on CPU — concurrent cooks collapse latency. Fine for dev/pilot, not scale.
- ⚠️ Apple Silicon (unified memory) ≫ commodity x86 for local inference, if self-host = a Mac mini.

**Rule of thumb:** self-host for *privacy* or at *real scale* — not for cost today. At low
volume an idle GPU costs more than pennies-per-cook hosted.

---

## 6. Monthly scaling (where the money actually is)

| Leg | per cook | 1K cooks/mo | 10K cooks/mo |
|-----|----------|-------------|--------------|
| LLM | ~$0.001  | ~$1         | ~$4–12       |
| STT | ~$0.10   | ~$100       | ~$1,000      |
| TTS | ~$0.15   | ~$150       | ~$1,500      |

- The real cost-reduction move: **local STT (faster-whisper) + local TTS (kokoro)** —
  both already noted as swap targets in `allegro.pipeline.yaml`.

---

## 7. The invariant that keeps this cheap

The flat per-cook budget holds **only because state is re-injected, not accumulated.**

- ✅ Re-inject current step + minimal state each turn → input stays ~flat.
- ❌ Sending the running transcript each turn → input balloons per turn.
- ❌ Native speech-to-speech → context accumulates → ~10× cost blowup.

Cascaded + stateless re-injection is *why* a cook costs a tenth of a cent. Don't break it.

---

Term definitions (leg, turn, fallback turn, re-injection, …): see [`glossary.md`](./glossary.md).
