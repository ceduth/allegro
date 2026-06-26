"""CoachCore — the recipe state machine + intent routing, with no I/O and no Pipecat
dependency. The live ``CoachProcessor`` (in ``bot.py``) wraps this; the C/D/E acceptance
table is tested directly against it.

Routing rules (from CLAUDE.md invariants):
  - Silence / noise (UNKNOWN) → say nothing, pointer unchanged.        (A, B)
  - Explicit advance ("next") → advance one step.                      (C1, C2)
  - Implicit advance (LLM-classified) → ASK "ready to move on?",
    do not auto-advance.                                              (C3)
  - Advancing INTO a safety step → confirm first.                      (C4)
  - Repeat / question / jump → answer or re-position, never advance.   (D1–D4)
  - "is it done yet?" is a question → answer, hold position.           (D3 trap)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .intents import Classification, Intent, IntentClassifier
from .safety import SafetyGuardrail
from .state import RecipeState
from ..recipe import Recipe, Step

# Callable[[question, current_step], answer_text] — the LLM answer path.
Answerer = Callable[[str, Step], str]


@dataclass
class Turn:
    """One logged interaction. The turn log is built from these."""
    transcript: str
    intent: Intent
    source: str
    pointer_before: int
    pointer_after: int
    spoke: str                  # "" means the agent stayed silent
    arm_timer: int | None = None  # seconds to (re)arm on the new step, if any


class CoachCore:
    def __init__(
        self,
        recipe: Recipe,
        classifier: IntentClassifier,
        safety: SafetyGuardrail,
        answerer: Answerer | None = None,
    ) -> None:
        self.recipe = recipe
        self.state = RecipeState(recipe)
        self.classifier = classifier
        self.safety = safety
        self.answerer = answerer
        self.pending_confirm = False  # True after we asked "ready to move on?"

    # -- public API -------------------------------------------------------------

    def greeting(self) -> str:
        s = self.state.current()
        return f"{self.recipe.title}. Step one: {s.text}"

    def handle(self, transcript: str) -> Turn:
        before = self.state.pointer
        cls = self.classifier.classify(transcript, self.state)

        if self.pending_confirm:
            spoke, armed = self._handle_pending(cls, transcript)
        else:
            spoke, armed = self._handle_normal(cls, transcript)

        return Turn(
            transcript=transcript,
            intent=cls.intent,
            source=cls.source,
            pointer_before=before,
            pointer_after=self.state.pointer,
            spoke=spoke,
            arm_timer=armed,
        )

    # -- routing ----------------------------------------------------------------

    def _handle_pending(self, cls: Classification, transcript: str) -> tuple[str, int | None]:
        """We previously asked 'ready to move on?' and are awaiting a yes/no."""
        if cls.intent == Intent.CONFIRM_YES:
            self.pending_confirm = False
            return self._do_advance()
        if cls.intent == Intent.CONFIRM_NO:
            self.pending_confirm = False
            return "Okay, take your time. Say next when you're ready.", None
        if cls.intent == Intent.QUESTION:
            # Answer but stay parked on the question — keep waiting for confirmation.
            return self._answer(transcript), None
        # Anything else (incl. noise) → stay silent, keep waiting.
        return "", None

    def _handle_normal(self, cls: Classification, transcript: str) -> tuple[str, int | None]:
        intent = cls.intent
        if intent == Intent.UNKNOWN:
            return "", None  # silence is never a signal
        if intent == Intent.REPEAT:
            return self.state.current().text, None
        if intent == Intent.QUESTION:
            return self._answer(transcript), None
        if intent == Intent.JUMP:
            return self._do_jump(cls)
        if intent == Intent.ADVANCE:
            # Explicit ("next") advances directly; implicit (LLM) asks first.
            if cls.source == "llm":
                return self._ask_confirm(reason=None)
            return self._maybe_advance()
        # CONFIRM_* with nothing pending → ignore.
        return "", None

    def _maybe_advance(self) -> tuple[str, int | None]:
        nxt = self.state.peek_next()
        if nxt is None:
            return "That was the last step. Enjoy the meal.", None
        if nxt.safety:
            return self._ask_confirm(reason=nxt)  # C4: confirm before a safety step
        return self._do_advance()

    def _ask_confirm(self, reason: Step | None) -> tuple[str, int | None]:
        self.pending_confirm = True
        if reason is not None and reason.safety:
            return f"Next is a step to watch: {reason.text} Ready to move on?", None
        return "Ready to move on?", None

    def _do_advance(self) -> tuple[str, int | None]:
        step = self.state.advance()
        if step is None:
            return "That was the last step. Enjoy the meal.", None
        return f"Step {step.index + 1}: {step.text}", step.timer_seconds

    def _do_jump(self, cls: Classification) -> tuple[str, int | None]:
        if cls.target_index is None:
            return "Which step do you want to go to?", None
        step = self.state.jump_to(cls.target_index)
        return f"Step {step.index + 1}: {step.text}", step.timer_seconds

    def _answer(self, transcript: str) -> str:
        step = self.state.current()
        curated = self.safety.answer(transcript, step)
        if curated is not None:
            return curated
        if self.answerer is not None:
            return self.answerer(transcript, step)
        # No LLM wired (e.g. baseline/tests): fall back to re-reading the step.
        return step.text
