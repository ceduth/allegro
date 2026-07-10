"""Safety guardrail — curated rules that intercept doneness / temperature / raw-protein
questions BEFORE the LLM. When a question touches one of these, the curated answer wins;
the LLM never gets to invent a confident-but-wrong fix. When uncertain, the safe answer
wins.
"""

from __future__ import annotations

from .state import RecipeState
from ..recipe import Step

# topic → curated answer.
_RULES: dict[str, str] = {
    "doneness": (
        "Chicken is safe at 165 degrees Fahrenheit, 74 Celsius, in the thickest part. "
        "Cut in, and the juices should run clear with no pink. If you are unsure, give it "
        "more time. Undercooked chicken is not worth the risk."
    ),
    "raw_protein": (
        "Treat anything that touched the raw chicken as contaminated. Do not taste the "
        "pan until the chicken is fully cooked, and wash your hands, the board, and the "
        "knife before they touch anything else."
    ),
    "hot_oil": (
        "Add ingredients to hot oil gently to avoid splatter, and keep a lid nearby. "
        "If oil ever smokes heavily or catches, cover the pan and turn off the heat — "
        "never water."
    ),
}

# keyword → topic. First match wins. Kept deliberately tight: a bare "oil" would wrongly
# intercept "how much oil?" (a quantity question) with splatter advice, so hot_oil keys on
# hazard words only, and doneness drops "how long" for the same reason.
_TRIGGERS: list[tuple[tuple[str, ...], str]] = [
    (("done", "cooked", "cook through", "pink", "ready to eat", "165", "temperature",
      "temp"), "doneness"),
    (("raw", "salmonella", "contaminat", "wash", "taste"), "raw_protein"),
    (("splatter", "smoke", "grease fire", "oil fire", "flare"), "hot_oil"),
]


class SafetyGuardrail:
    def answer(self, transcript: str, step: Step) -> str | None:
        """Return a curated safety answer if the question touches a safety topic OR the
        current step is itself safety-critical; otherwise None (let the LLM answer)."""
        t = transcript.lower()

        # A question asked while standing on a raw-protein step is safety-relevant even
        # if phrased neutrally ("is this ok yet?").
        if step.safety and step.safety_topic == "raw_chicken":
            for keys, topic in _TRIGGERS:
                if any(k in t for k in keys):
                    return _RULES[topic]
            return _RULES["doneness"]

        for keys, topic in _TRIGGERS:
            if any(k in t for k in keys):
                return _RULES[topic]
        return None
