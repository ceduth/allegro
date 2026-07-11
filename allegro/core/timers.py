"""Timers — the only allowed proactive speech.

A step with ``timer_seconds`` arms a timer on entry. When it elapses the agent speaks
exactly once ("Time's up."). It never nags and never advances the pointer. Jumping away
cancels the armed timer.

``TimerManager`` is asyncio-based for the live pipeline. The arming *decision*
(``timer_for``) is a pure function so the E-section behaviour is unit-testable without
real time.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from ..recipe import Step

TIMES_UP = "Time's up."


def timer_for(step: Step) -> int | None:
    """Seconds to arm on entering this step, or None for an untimed step (E3)."""
    return step.timer_seconds


class TimerManager:
    def __init__(
        self, on_elapse: Callable[[Step], Awaitable[None]], scale: float = 1.0
    ) -> None:
        self._on_elapse = on_elapse
        self._task: asyncio.Task | None = None
        # Dev-only wall-clock speedup (e.g. 0.02 turns a 10-min simmer into 12s) so the
        # E-section can be validated live without waiting the full duration. 1.0 = real.
        self._scale = scale

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    def arm(self, step: Step) -> bool:
        """Arm a timer for ``step`` if it is timed. Cancels any existing timer first
        (so a jump never leaves a stale timer running). Returns True if armed."""
        self.cancel()
        seconds = timer_for(step)
        if seconds is None:
            return False
        self._task = asyncio.create_task(self._run(step, seconds * self._scale))
        return True

    async def _run(self, step: Step, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        await self._on_elapse(step)  # fires exactly once
