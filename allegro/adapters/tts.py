"""TTS adapters. Paid: Cartesia. OSS (Phase 2): Kokoro — the first leg to self-host."""

from __future__ import annotations

import os

from ..registry import register_tts


@register_tts("cartesia")
def _cartesia(cfg: dict):
    from pipecat.services.cartesia.tts import CartesiaTTSService

    params = cfg.get("params", {})
    return CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        voice_id=params.get("voice_id", "71a7ad14-091c-4e8e-a314-022ece01c121"),
    )


@register_tts("kokoro")
def _kokoro(cfg: dict):
    """Local TTS via Pipecat's Kokoro service (Kokoro-82M, ONNX). Model + voices
    auto-download once, then offline; no key, no per-char bill. Emits the same
    TTSAudioRawFrame as Cartesia (auto-resampled), so it's a drop-in swap.

    VERIFY: Kokoro is a recent Pipecat addition. If `import pipecat.services.kokoro.tts`
    fails on your pinned version, swap this node to provider `piper` below."""
    from pipecat.services.kokoro.tts import KokoroTTSService

    voice = cfg.get("params", {}).get("voice", "af_heart")
    return KokoroTTSService(settings=KokoroTTSService.Settings(voice=voice))


@register_tts("piper")
def _piper(cfg: dict):
    """Local TTS fallback for older Pipecat versions that lack Kokoro."""
    from pipecat.services.piper.tts import PiperTTSService

    voice = cfg.get("params", {}).get("voice_id", "en_US-lessac-medium")
    return PiperTTSService(voice_id=voice, use_cuda=False)
