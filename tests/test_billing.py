"""Phase 0a bill guarantee: prove the rule layer never reaches the LLM on the no-LLM
cases. With the `mock` provider (zero network), "nothing calls the model inadvertently"
becomes a CI check, not a hope. See docs/billing.md.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from allegro.adapters.llm import MockLLM
from allegro.core import CoachCore, IntentClassifier, SafetyGuardrail
from allegro.recipe import weeknight_skillet


def _coach_with_mock():
    mock = MockLLM()
    classifier = IntentClassifier(llm_classify=mock.classify)
    coach = CoachCore(weeknight_skillet(), classifier, SafetyGuardrail(), answerer=mock.answer)
    return coach, mock


# Turns the rule layer fully recognises — none may touch the LLM.
NO_LLM_TURNS = [
    "",                               # silence (empty → UNKNOWN at the rule layer)
    "next",                           # explicit advance
    "ok, done with that",             # explicit advance
    "say that again",                 # repeat
    "go back to chopping the onion",  # jump
    "yes",                            # confirm (nothing pending → ignored)
    "no",
]


def test_rule_recognised_turns_never_touch_the_llm():
    coach, mock = _coach_with_mock()
    for utterance in NO_LLM_TURNS:
        coach.handle(utterance)
    assert mock.calls == 0, f"LLM was called {mock.calls}x on rule-recognised turns"


def test_nonempty_noise_is_a_free_fallback_not_a_zero_call():
    # Gibberish that STT renders as words matches no keyword, so it DOES reach the
    # classifier — there's no way to distinguish it from an implicit cue without the
    # model. The guarantee is that it's the mock (zero network, $0) and routes to
    # silence, NOT that it's a zero-call case.
    coach, mock = _coach_with_mock()
    turn = coach.handle("clang sshhh brrrrr")
    assert mock.classify_calls == 1          # reached the (free) mock classifier
    assert turn.spoke == ""                  # …and was classified to silence
    assert turn.pointer_after == turn.pointer_before


def test_safety_questions_never_touch_the_llm():
    coach, mock = _coach_with_mock()
    coach.handle("next")   # 0->1
    coach.handle("next")   # ask before safety step
    coach.handle("yes")    # ->2 raw chicken
    turn = coach.handle("is it safe to eat yet?")
    assert mock.calls == 0, "safety guardrail must answer before the LLM"
    assert turn.source == "safety"


def test_implicit_cue_is_the_expected_fallback_call():
    # The one advancement case the rule layer can't catch → one classify call, no answer.
    coach, mock = _coach_with_mock()
    coach.handle("the onions are soft now")
    assert mock.classify_calls == 1
    assert mock.answer_calls == 0


def test_free_form_question_is_the_expected_answer_call():
    coach, mock = _coach_with_mock()
    turn = coach.handle("how much salt do I add?")
    assert mock.answer_calls == 1
    assert turn.source == "llm"
    assert turn.pointer_after == turn.pointer_before  # answered in place
