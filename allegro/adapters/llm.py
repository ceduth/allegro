"""LLM adapters. Paid: Anthropic (Claude). OSS (Phase 2): Ollama / vLLM.

The LLM is NOT a pipeline node — the coach calls it directly (synchronously, off the
event loop via run_in_executor) for two jobs: classify implicit cues that the rule layer
misses, and answer free-form questions. Kept behind a tiny interface (`classify` +
`answer`) so any provider drops in.
"""

from __future__ import annotations

import os

from ..core.intents import Intent
from ..recipe import Step
from ..registry import register_llm

_CLASSIFY_SYS = (
    "You label a cook's spoken utterance during a hands-free recipe. Reply with EXACTLY "
    "one word: advance, question, repeat, jump, or unknown. 'advance' = they signal the "
    "current step is done (explicitly or implicitly, e.g. 'the onions are soft'). "
    "'question' = they ask something. 'repeat' = they want the step again. 'jump' = they "
    "want a different step. 'unknown' = noise or unclear. When unsure, answer unknown."
)

_ANSWER_SYS = (
    "You are a calm hands-free cooking coach. Answer in one or two short spoken "
    "sentences. Use the current step for context. Do not advance the recipe. If the "
    "question is about doneness, temperature, or raw meat and you are not certain, tell "
    "them the safe thing to do."
)

_WORD_TO_INTENT = {
    "advance": Intent.ADVANCE,
    "question": Intent.QUESTION,
    "repeat": Intent.REPEAT,
    "jump": Intent.JUMP,
    "unknown": Intent.UNKNOWN,
}


class AnthropicLLM:
    def __init__(self, model: str) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = model

    def classify(self, transcript: str, current_step_text: str) -> Intent:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=5,
            system=_CLASSIFY_SYS,
            messages=[{
                "role": "user",
                "content": f"Current step: {current_step_text}\nUtterance: {transcript}",
            }],
        )
        word = msg.content[0].text.strip().lower().split()[0] if msg.content else "unknown"
        return _WORD_TO_INTENT.get(word, Intent.UNKNOWN)

    def answer(self, question: str, step: Step) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=120,
            system=_ANSWER_SYS,
            messages=[{
                "role": "user",
                "content": f"Current step: {step.text}\nQuestion: {question}",
            }],
        )
        return msg.content[0].text.strip() if msg.content else ""


class MockLLM:
    """Zero-network LLM stand-in — the Phase 0a bill guarantee. Makes an inadvertent
    runtime LLM bill *structurally impossible*: there is no client and no network call.
    Counts its own calls so a regression test can assert the rule layer never reaches it
    on the no-LLM cases (silence / noise / explicit advancement)."""

    def __init__(self) -> None:
        self.classify_calls = 0
        self.answer_calls = 0

    @property
    def calls(self) -> int:
        return self.classify_calls + self.answer_calls

    def classify(self, transcript: str, current_step_text: str) -> Intent:
        self.classify_calls += 1
        t = transcript.lower()
        # Canned: recognise the one implicit-advance shape; everything else unknown.
        if any(w in t for w in ("soft", "translucent", "looks done", "ready now")):
            return Intent.ADVANCE
        return Intent.UNKNOWN

    def answer(self, question: str, step: Step) -> str:
        self.answer_calls += 1
        return f"(mock answer for: {step.text})"


@register_llm("mock")
def _mock(cfg: dict) -> MockLLM:
    return MockLLM()


@register_llm("anthropic")
def _anthropic(cfg: dict) -> AnthropicLLM:
    return AnthropicLLM(model=cfg.get("model", "claude-haiku-4-5"))


@register_llm("ollama")
def _ollama(cfg: dict):
    # Phase 2: local LLM via Ollama's OpenAI-compatible endpoint. Lowest priority swap —
    # Haiku is already the cheap leg.
    raise NotImplementedError("Ollama LLM adapter not wired yet (Phase 2)")
