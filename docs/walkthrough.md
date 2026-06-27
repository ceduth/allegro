# End-to-end walkthrough — one real cook

A beginner cooks the repo recipe (`weeknight_skillet`) hands-free. This traces the
logic turn by turn so the whole loop is legible: how silence and noise are ignored,
how the pointer moves only on intent, where timers and safety come from, and **why each
LLM call stays tiny** (step re-injection, not transcript accumulation).

> Unfamiliar terms (turn, intent, re-injection, …): see [`glossary.md`](./glossary.md).

## The recipe

Steps are 0-indexed. Step 2 is flagged for safety; step 3 has a timer.

```
0  Chop one onion into small dice.
1  Heat oil; sauté the onion until soft, ~5 min.
2  Add the raw chicken; brown all sides.        [SAFETY]
3  Pour in tomatoes; simmer 10 min.             [TIMER 600s]
4  Season and serve.
```

**Important:** the recipe text has no temperatures. Food-safety facts (chicken is done at
165°F / 74°C, etc.) live in a separate **curated safety knowledge** set — fixed,
human-written, never generated. The safety guardrail answers from *that*, which is why it
needs no LLM and cannot invent a number.

## How to read this

- **G** = the greeting, before any user turn. **T1, T2, …** = turn number (a sequence
  counter, not a clock).
- **ptr A→B** = recipe pointer before → after the turn.
- Each spoken line is labelled by *what produced it*:
  - **Coach (recipe step)** — canned step text the state machine reads aloud. Free.
  - **Coach (LLM answer)** — a paid LLM call, grounded in the current step.
  - **Coach (safety rule)** — the curated safety knowledge. No LLM.
  - **Coach (timer)** — fired by the timer. No LLM.
  - **Coach: —** — says nothing.

---

## The cook

**G — greeting** · ptr –→0
Coach (recipe step): *"Weeknight chicken and tomato skillet. Step one: chop one onion into small dice."*

---

**T1 — cook is silent 90s, chopping** → no speech · ptr 0→0
Coach: —
↳ VAD detects no speech, so nothing is sent. Silence is never a signal: no prompt, no advance.

---

**T2 — faucet turns on** → VAD rejects (not speech) · ptr 0→0
Coach: —
↳ The faucet never reaches STT — VAD filters it as non-speech. First line of defence.

---

**T3 — cook: "ok next"** → ADVANCE (rule) · ptr 0→1
Coach (recipe step): *"Step two: heat a tablespoon of oil over medium, then sauté the onion until soft, about five minutes."*
↳ An explicit command, matched by keyword. No LLM. Free.

---

**T4 — cook: "how much oil?"** → QUESTION (rule) · ptr 1→1
Coach (LLM answer): *"About a tablespoon."*
↳ A question is answered **in place** — the pointer does not move. The rule layer can route
the question but can't compose the answer, so this is a paid **LLM answer call**, grounded in
the current step. (Its exact payload is in *What the LLM sees*, below.)

---

**T5 — cook is silent 4 min, sautéing** → no speech · ptr 1→1
Coach: —
↳ This step has no timer, so a long silence is just work in progress. The agent stays quiet.

---

**T6 — cook: "the onions look soft now"** → ADVANCE (llm) · ptr 1→1
Coach (LLM answer): *"Next adds the raw chicken — a step to watch. Ready to move on?"*
↳ No keyword matched, so this is a paid **LLM classify call**. It reads as an implicit
advance — and implicit advances never move on their own, they **ask**. The next step is
safety-flagged, so the confirmation names it. Pointer holds at 1.

---

**T7 — cook: "yeah"** → CONFIRM_YES (rule) · ptr 1→2
Coach (recipe step): *"Step three: add the raw chicken to the pan and brown it on all sides."*
↳ The confirmation the previous turn was waiting for. Now the pointer moves. Free.

---

**T8 — a spoon clatters near the phone** → fragment slips past VAD → UNKNOWN (rule) · ptr 2→2
Coach: —
↳ Second line of defence: a sharp noise leaks past VAD, STT garbles it, and the rule layer
labels the garbage UNKNOWN → silence. It never reaches the LLM.

---

**T9 — cook: "is it done yet?"** → QUESTION → intercepted by SAFETY · ptr 2→2
Coach (safety rule): *"Chicken is safe at 165°F, 74°C, in the thickest part — juices run clear, no pink. If unsure, give it more time."*
↳ Two things at once. First, "is it done?" is the **classic trap** — it must answer without
advancing, and it does. Second, because we're on the raw-chicken step, the **safety guardrail
intercepts before the LLM** and answers from the curated safety knowledge. The 165°F figure
comes from there — not the recipe, not a model. **No paid call. No invented number.**

---

**T10 — cook: "ok done"** → ADVANCE (rule) · ptr 2→3
Coach (recipe step): *"Step four: pour in the tomatoes and simmer for ten minutes."* → **arms a 600s timer**
↳ Entering a timed step automatically arms its timer. Nothing is spoken about the timer yet.

---

**T11 — cook is silent, simmering** → *[600s elapse]* → TIMER fires · ptr 3→3
Coach (timer): *"Time's up."*
↳ The **only** time the agent speaks unprompted — and it speaks once. It does **not**
auto-advance; the pointer stays on step 3 until the cook says so.

---

**T12 — cook: "go back to browning the chicken"** → JUMP (rule) · ptr 3→2
Coach (recipe step): *"Step three: add the raw chicken to the pan and brown it on all sides."*
↳ "chicken" resolves by tag to step 2; the pointer jumps there and the step is re-read. The
step-3 timer is cancelled on leaving.

---

Every turn also writes one log line, e.g. T9:

```json
{"turn":9,"transcript":"is it done yet?","vad":"speech","intent":"question",
 "source":"safety","pointer_before":2,"pointer_after":2,
 "spoke":"Chicken is safe at 165..."}
```

---

## What the LLM sees — flat, every time

Of the twelve turns above, **only two paid for an LLM call** (T4 answer, T6 classify).
Everything else was the rule layer, the safety knowledge, a timer, or silence. Here are
those two calls in full:

**T4 — answer call**
```
system:  You are a calm hands-free cooking coach. Answer in one or two short
         sentences. Do not advance the recipe.
user:    Current step: Heat a tablespoon of oil… sauté the onion until soft…
         Question: how much oil?
```

**T6 — classify call**
```
system:  You label a cook's utterance. Reply with EXACTLY one word:
         advance | question | repeat | jump | unknown.
user:    Current step: Heat a tablespoon of oil… sauté the onion until soft…
         Utterance: the onions look soft now
```

What's **absent** from both: the greeting, every prior turn, the pointer history. Each call
carries **one step + one utterance** (~110 input tokens) and does not grow as the cook
proceeds. That is step re-injection.

---

## The anti-pattern we avoid

If the agent instead resent the running conversation each turn (transcript accumulation):

| by turn | accumulated design sends   | our design sends      |
|---------|----------------------------|-----------------------|
| T4      | greeting + T1–T4           | 1 step + 1 utterance  |
| T6      | greeting + T1–T6           | 1 step + 1 utterance  |
| T12     | greeting + T1–T12          | 1 step + 1 utterance  |

- Accumulated input **grows every turn** → cost climbs through the cook, ~10× by the end.
- Native speech-to-speech does this *internally* whether you want it or not.
- Cascaded + re-injection keeps every call flat → a whole cook ≈ a tenth of a cent
  (see [`cost-model.md`](./cost-model.md)).

**The single rule:** the **state machine** holds position; the LLM is handed only what it
needs for *this* turn and remembers nothing.