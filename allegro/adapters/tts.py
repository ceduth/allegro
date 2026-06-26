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
    # Phase 2: self-hosted Kokoro — biggest cost-cut for least quality loss.
    raise NotImplementedError("Kokoro TTS adapter not wired yet (Phase 2)")
