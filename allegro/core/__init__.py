"""The in-house product: state machine, intents, timers, safety, coach. No Pipecat,
no I/O — pure and unit-tested against the C/D/E acceptance table."""

from .coach import CoachCore, Turn
from .intents import Classification, Intent, IntentClassifier, classify_rule
from .safety import SafetyGuardrail
from .state import RecipeState
from .timers import TIMES_UP, TimerManager, timer_for

__all__ = [
    "CoachCore", "Turn", "Classification", "Intent", "IntentClassifier",
    "classify_rule", "SafetyGuardrail", "RecipeState", "TimerManager",
    "timer_for", "TIMES_UP",
]
