"""Recipe state machine — the single source of truth for position.

The pointer moves ONLY through these methods, and only the coach's intent routing
calls them. Silence never reaches here, so silence can never move the pointer.
"""

from __future__ import annotations

from ..recipe import Recipe, Step

# Tokens with no discriminating value for jump resolution.
_STOPWORDS = frozenset(
    {
        "the", "to", "a", "an", "back", "go", "jump", "step", "that", "now", "is",
        "it", "and", "of", "on", "for", "with", "please", "lets", "let", "us",
        "where", "we", "were", "was", "i", "want", "wanna", "return",
    }
)


def _tokens(text: str) -> list[str]:
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower())
    return [t for t in cleaned.split() if t not in _STOPWORDS and len(t) >= 3]


def _prefix_match(a: str, b: str) -> bool:
    """True if one token is a >=3-char prefix of the other (chop ~ chopping)."""
    n = min(len(a), len(b))
    return n >= 3 and a[:n] == b[:n]


class RecipeState:
    def __init__(self, recipe: Recipe) -> None:
        self.recipe = recipe
        self.pointer = 0
        self.completed: list[int] = []

    def current(self) -> Step:
        return self.recipe.steps[self.pointer]

    def peek_next(self) -> Step | None:
        nxt = self.pointer + 1
        return self.recipe.steps[nxt] if nxt < len(self.recipe.steps) else None

    def at_end(self) -> bool:
        return self.pointer >= len(self.recipe.steps) - 1

    def advance(self) -> Step | None:
        """Move forward one step. No-op at the end. Returns the new current step."""
        if self.at_end():
            return None
        if self.pointer not in self.completed:
            self.completed.append(self.pointer)
        self.pointer += 1
        return self.current()

    def jump_to(self, index: int) -> Step:
        if not 0 <= index < len(self.recipe.steps):
            raise IndexError(index)
        self.pointer = index
        return self.current()

    def find_step(self, query: str) -> int | None:
        """Resolve a spoken target ("the marinade", "chopping the onion") to a step
        index by prefix-overlap against each step's tags + text. Returns the best
        match, or None if nothing scores."""
        q = _tokens(query)
        if not q:
            return None
        best_idx, best_score = None, 0
        for step in self.recipe.steps:
            searchable = _tokens(step.text) + list(step.tags)
            score = sum(
                1 for qt in q if any(_prefix_match(qt, st) for st in searchable)
            )
            if score > best_score:
                best_idx, best_score = step.index, score
        return best_idx
