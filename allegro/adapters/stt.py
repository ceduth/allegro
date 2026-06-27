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
    """Local STT via Pipecat's Whisper service (faster-whisper / CTranslate2). Offline
    after the first model download; no key, no per-minute bill. Emits the same
    TranscriptionFrame as Deepgram, so it's a drop-in swap."""
    from pipecat.services.whisper.stt import Model, WhisperSTTService
    from pipecat.transcriptions.language import Language

    params = cfg.get("params", {})
    return WhisperSTTService(
        model=cfg.get("model") or Model.DISTIL_MEDIUM_EN,  # English-only, fast
        device=params.get("device", "cpu"),
        # VERIFY: float16 is CUDA-only; int8/default is safe on CPU/Apple Silicon.
        compute_type=params.get("compute_type", "int8"),
        language=Language.EN,
    )
