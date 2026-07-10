"""Intent classification: transcript → intent, against the current pointer.

Two layers, cheapest first:
  1. A rule layer for unambiguous spoken commands (next / repeat / go back / questions).
     Deterministic, free, and the bulk of real turns — also what makes the C/D/E table
     unit-testable without a live LLM.
  2. An LLM fallback for implicit cues ("the onions are soft now") that no keyword
     catches. Injected as a callable so tests can stub it.

Garbage / empty transcripts (dropped spoon, blender, faucet that leaked through STT)
classify as UNKNOWN and route to silence — never to the LLM, never to advancement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .state import RecipeState


class Intent(Enum):
    ADVANCE = "advance"
    REPEAT = "repeat"
    QUESTION = "question"
    JUMP = "jump"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    UNKNOWN = "unknown"  # noise / unintelligible → no action, no speech


@dataclass
class Classification:
    intent: Intent
    source: str  # "rule" | "llm"
    target_index: int | None = None  # for JUMP


# Callable[[transcript, current_step_text], Intent]
LlmClassify = Callable[[str, str], Intent]

_REPEAT = ("repeat", "say that again", "read that again", "one more time",
           "come again", "what was that")
_ADVANCE = ("next", "done with that", "done with this", "im done", "i'm done",
            "move on", "moving on", "keep going", "got it next", "next step",
            "finished", "all done", "ok done", "okay done")
_YES = ("yes", "yeah", "yep", "yup", "sure", "go ahead", "do it", "ok go",
        "okay go", "ready", "lets go", "let's go", "go for it")
_NO = ("no", "not yet", "wait", "hold on", "nope", "stop", "hang on", "give me a sec")
_QUESTION_STARTS = ("how", "what", "when", "where", "why", "which", "is", "are",
                    "do", "does", "did", "can", "could", "should", "would", "will",
                    "was", "were", "am")
_JUMP_PREFIXES = ("go back to", "back to", "go to", "jump to", "return to",
                  "take me back to", "go back", "jump back to")


def _norm(transcript: str) -> str:
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in transcript.lower())
    return " ".join(cleaned.split())


def classify_rule(transcript: str, state: RecipeState) -> Classification | None:
    """Return a Classification for clear commands, or None to defer to the LLM.

    UNKNOWN (a real classification, not None) is returned for empty/garbage so we
    short-circuit to silence without paying for an LLM call."""
    raw = transcript.strip()
    norm = _norm(transcript)
    if not norm:
        return Classification(Intent.UNKNOWN, "rule")

    # Repeat before question so "what was that" reads as repeat, not a query.
    if any(p in norm for p in _REPEAT):
        return Classification(Intent.REPEAT, "rule")

    # Jump: "go back to <target>" → resolve target to a step.
    for prefix in _JUMP_PREFIXES:
        if norm.startswith(prefix):
            target = norm[len(prefix):].strip()
            idx = state.find_step(target) if target else None
            return Classification(Intent.JUMP, "rule", target_index=idx)

    # Questions: anything interrogative answers in place, never advances.
    first = norm.split()[0]
    if raw.endswith("?") or first in _QUESTION_STARTS:
        return Classification(Intent.QUESTION, "rule")

    if norm in _YES:
        return Classification(Intent.CONFIRM_YES, "rule")
    if norm in _NO:
        return Classification(Intent.CONFIRM_NO, "rule")

    if any(p in norm for p in _ADVANCE):
        return Classification(Intent.ADVANCE, "rule")

    return None  # defer to LLM


class IntentClassifier:
    def __init__(self, llm_classify: LlmClassify | None = None) -> None:
        self._llm = llm_classify

    def classify(self, transcript: str, state: RecipeState) -> Classification:
        ruled = classify_rule(transcript, state)
        if ruled is not None:
            return ruled
        if self._llm is not None:
            intent = self._llm(transcript, state.current().text)
            return Classification(intent, "llm")
        return Classification(Intent.UNKNOWN, "rule")
