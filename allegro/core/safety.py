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

# keyword → topic. First match wins. Kept deliberately tight so a question is only
# intercepted when it actually touches a safety topic. doneness includes neutral phrasings
# ("is it safe yet", "ready to eat") so a real doneness question on the raw-chicken step is
# caught — but seasoning/quantity questions ("more salt?", "add pepper?") are NOT.
_TRIGGERS: list[tuple[tuple[str, ...], str]] = [
    (("done", "cooked", "cook through", "cooked enough", "pink", "ready to eat",
      "ready yet", "safe to eat", "safe yet", "is it safe", "165", "temperature",
      "temp"), "doneness"),
    (("raw", "salmonella", "contaminat", "wash", "taste"), "raw_protein"),
    (("splatter", "smoke", "grease fire", "oil fire", "flare"), "hot_oil"),
]


class SafetyGuardrail:
    def answer(self, transcript: str, step: Step) -> str | None:
        """Return a curated safety answer only when the question touches a safety topic;
        otherwise None (let the LLM answer). An unrelated question is never hijacked, even
        on a safety-critical step — a doneness/raw question there matches by keyword."""
        t = transcript.lower()
        for keys, topic in _TRIGGERS:
            if any(k in t for k in keys):
                return _RULES[topic]
        return None
