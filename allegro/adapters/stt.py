"""STT adapters. Paid: Deepgram. OSS (Phase 2): faster-whisper."""

from __future__ import annotations

import os

from ..registry import register_stt


@register_stt("deepgram")
def _deepgram(cfg: dict):
    from pipecat.services.deepgram.stt import DeepgramSTTService

    return DeepgramSTTService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        model=cfg.get("model", "nova-3"),
    )


@register_stt("faster_whisper")
def _faster_whisper(cfg: dict):
    # Phase 2: local STT. Must re-pass the A/B noise table before it counts.
    raise NotImplementedError("faster-whisper STT adapter not wired yet (Phase 2)")
