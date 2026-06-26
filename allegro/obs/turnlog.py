"""Per-turn structured log. Per the spec, most failures are diagnosable directly from
this, so it is built in from the start: raw transcript, VAD decision, classified intent,
and the pointer position before and after.

One JSON object per line (JSONL) under ``logs/``. Append-only, flushed each turn so a
crashed cook still leaves a full trace.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ..core.coach import Turn


class TurnLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, record: dict) -> None:
        record["ts"] = datetime.now(timezone.utc).isoformat()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()

    def record(self, turn: Turn, vad: str | None = None) -> None:
        rec = asdict(turn)
        rec["intent"] = turn.intent.value
        rec["vad"] = vad
        self._write(rec)

    def event(self, kind: str, **fields) -> None:
        """Log a non-turn event (timer fired, session start, greeting)."""
        self._write({"event": kind, **fields})
