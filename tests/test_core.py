"""Text-level acceptance tests — the C/D/E table from phase1-kitchen-test.md, plus the
silence/noise (A/B) routing, driven directly against CoachCore. No audio, no Pipecat,
no live LLM (the implicit-cue path is stubbed). These are the deterministic regression
net for "silence is never a signal / advancement is intent-only".

The A1–A5 *acoustic* failures can only be proven on the live rig; what we assert here is
that once noise reaches the coach as a garbage/empty transcript, it routes to silence.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from allegro.core import CoachCore, Intent, IntentClassifier, SafetyGuardrail, timer_for
from allegro.recipe import weeknight_skillet


def _stub_llm(transcript: str, current_step_text: str) -> Intent:
    """Stand-in for the LLM classifier: only recognises the one implicit cue."""
    if "soft" in transcript.lower() or "translucent" in transcript.lower():
        return Intent.ADVANCE
    return Intent.UNKNOWN


def make_coach() -> CoachCore:
    return CoachCore(
        recipe=weeknight_skillet(),
        classifier=IntentClassifier(llm_classify=_stub_llm),
        safety=SafetyGuardrail(),
    )


# -- C. Advancement (only on explicit signal) -----------------------------------

def test_c1_next_advances_one_step():
    c = make_coach()
    turn = c.handle("next")
    assert turn.intent is Intent.ADVANCE
    assert turn.pointer_before == 0 and turn.pointer_after == 1


def test_c2_done_with_that_advances():
    c = make_coach()
    turn = c.handle("ok, done with that")
    assert turn.intent is Intent.ADVANCE
    assert turn.pointer_after == 1


def test_c3_implicit_cue_asks_and_holds_position():
    c = make_coach()
    turn = c.handle("the onions are soft now")
    # Implicit cue: advance OR ask. We ask, and crucially do NOT auto-advance.
    assert turn.intent is Intent.ADVANCE and turn.source == "llm"
    assert turn.pointer_after == 0
    assert "ready" in turn.spoke.lower()
    # ...and a following "yes" then advances.
    follow = c.handle("yes")
    assert follow.pointer_after == 1


def test_c4_confirms_before_safety_step():
    c = make_coach()
    c.handle("next")  # 0 -> 1 (sauté)
    turn = c.handle("next")  # next is the raw-chicken safety step
    assert turn.pointer_after == 1, "must not auto-advance into a safety step"
    assert "ready" in turn.spoke.lower()
    follow = c.handle("yes")
    assert follow.pointer_after == 2


# -- D. Intents (route without advancing) ---------------------------------------

def test_d1_say_that_again_repeats_in_place():
    c = make_coach()
    turn = c.handle("say that again")
    assert turn.intent is Intent.REPEAT
    assert turn.pointer_after == 0
    assert turn.spoke == c.recipe.steps[0].text


def test_d2_question_answers_in_place():
    c = make_coach()
    c.handle("next")
    c.handle("yes") if c.pending_confirm else None
    turn = c.handle("how much salt?")
    assert turn.intent is Intent.QUESTION
    assert turn.pointer_after == turn.pointer_before
    assert turn.spoke


def test_d3_is_it_done_yet_does_not_advance():
    c = make_coach()
    # walk to the simmer step
    c.handle("next")          # 0->1
    c.handle("next")          # ask (safety)
    c.handle("yes")           # ->2
    c.handle("next")          # ask? 2->3 not safety, advances directly
    turn = c.handle("is it done yet?")
    assert turn.intent is Intent.QUESTION
    assert turn.pointer_after == turn.pointer_before  # the classic trap


def test_d4_go_back_jumps_to_target():
    c = make_coach()
    c.handle("next")  # ->1
    turn = c.handle("go back to chopping the onion")
    assert turn.intent is Intent.JUMP
    assert turn.pointer_after == 0


# -- E. Timers ------------------------------------------------------------------

def test_e1_simmer_step_arms_a_timer():
    recipe = weeknight_skillet()
    simmer = next(s for s in recipe.steps if "simmer" in s.text)
    assert timer_for(simmer) == 10 * 60


def test_e1_advancing_into_simmer_reports_arm_timer():
    c = make_coach()
    c.handle("next")   # ->1
    c.handle("next")   # ask safety
    c.handle("yes")    # ->2
    turn = c.handle("next")  # ->3 simmer
    assert turn.pointer_after == 3
    assert turn.arm_timer == 10 * 60


def test_e3_untimed_step_arms_nothing():
    recipe = weeknight_skillet()
    chop = recipe.steps[0]
    assert timer_for(chop) is None


# -- A / B. Noise and silence route to silence ----------------------------------

def test_empty_transcript_is_silent_and_holds():
    c = make_coach()
    turn = c.handle("")
    assert turn.intent is Intent.UNKNOWN
    assert turn.spoke == ""
    assert turn.pointer_after == 0


def test_garbage_transcript_is_silent_and_holds():
    c = make_coach()
    turn = c.handle("clang sshhh brrrrr")  # spoon drop / faucet / blender leakage
    assert turn.intent is Intent.UNKNOWN
    assert turn.spoke == ""
    assert turn.pointer_after == 0


def test_safety_question_routes_to_curated_rule():
    c = make_coach()
    c.handle("next")          # ->1
    c.handle("next")          # ask safety
    c.handle("yes")           # ->2 raw chicken
    turn = c.handle("is the chicken safe to eat?")
    assert turn.intent is Intent.QUESTION
    assert "165" in turn.spoke  # curated doneness rule, not an LLM guess
    assert turn.pointer_after == turn.pointer_before


def test_safety_step_does_not_hijack_unrelated_questions():
    # On the raw-chicken step, a seasoning question must NOT get the safety rule.
    c = make_coach()
    c.handle("next")          # ->1
    c.handle("next")          # ask safety
    c.handle("yes")           # ->2 raw chicken
    turn = c.handle("should I add pepper?")
    assert turn.intent is Intent.QUESTION
    assert turn.source != "safety"
    assert "165" not in turn.spoke
    assert turn.pointer_after == turn.pointer_before


def test_timer_arms_fires_once_and_is_cancelable():
    # E-section mechanism: untimed step arms nothing; a timed step fires exactly once;
    # a jump/cancel stops it. Scaled tiny so the test is fast.
    import asyncio

    from allegro.core import TimerManager
    from allegro.recipe import Step

    timed = Step(index=3, text="simmer ten minutes", timer_seconds=600)
    untimed = Step(index=0, text="chop the onion")

    async def scenario():
        fired = []

        async def on_elapse(step):
            fired.append(step.index)

        tm = TimerManager(on_elapse, scale=0.0001)  # 600s -> 0.06s
        assert tm.arm(untimed) is False              # E3: untimed arms nothing
        assert tm.arm(timed) is True                 # E1: timed arms
        await asyncio.sleep(0.3)
        assert fired == [3]                          # E2: fires exactly once
        fired.clear()
        tm.arm(timed)
        tm.cancel()                                  # jump away → cancelled
        await asyncio.sleep(0.3)
        assert fired == []

    asyncio.run(scenario())
