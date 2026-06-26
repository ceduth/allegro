"""The one hardcoded Phase-1 recipe: a sauté step, a timed simmer, and a chop step.

A recipe is a flat list of steps with an explicit pointer (held in
``core.state.RecipeState``). Each step may arm a timer on entry and may be marked
safety-critical (irreversible / raw-protein / doneness) so the coach confirms before
advancing into it and routes related questions to the curated safety rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    index: int
    text: str
    timer_seconds: int | None = None  # arms a timer on entry when set
    safety: bool = False              # irreversible/safety-critical: confirm before advancing
    safety_topic: str | None = None   # routes Q&A to a curated rule, e.g. "raw_chicken"
    tags: tuple[str, ...] = ()         # keywords for jump resolution ("go back to ...")


@dataclass(frozen=True)
class Recipe:
    title: str
    steps: tuple[Step, ...]

    def __post_init__(self) -> None:
        for i, step in enumerate(self.steps):
            assert step.index == i, f"step {i} has index {step.index}"


def weeknight_skillet() -> Recipe:
    """Weeknight chicken & tomato skillet — chop, sauté, raw-protein, timed simmer."""
    steps = (
        Step(
            index=0,
            text="Chop one onion into small dice.",
            tags=("onion", "chop", "dice", "prep"),
        ),
        Step(
            index=1,
            text="Heat a tablespoon of oil over medium, then sauté the onion until "
            "soft and translucent, about five minutes.",
            tags=("onion", "saute", "oil", "soften"),
        ),
        Step(
            index=2,
            text="Add the raw chicken to the pan and brown it on all sides.",
            safety=True,
            safety_topic="raw_chicken",
            tags=("chicken", "raw", "brown", "protein"),
        ),
        Step(
            index=3,
            text="Pour in the tomatoes and simmer for ten minutes.",
            timer_seconds=10 * 60,
            tags=("tomato", "simmer", "sauce"),
        ),
        Step(
            index=4,
            text="Season with salt and pepper to taste, then serve.",
            tags=("salt", "season", "pepper", "serve", "finish"),
        ),
    )
    return Recipe(title="Weeknight chicken and tomato skillet", steps=steps)
