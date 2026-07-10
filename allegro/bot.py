"""Phase 0 baseline bot, wired for Pipecat 1.4.0's development runner.

The runner (`pipecat.runner.run`) owns the HTTP layer — `POST /start`, `POST /api/offer`,
and the prebuilt web UI at `/client` — and calls our `bot(runner_args)` once per browser
connection with an already-established WebRTC connection. We build the transport (with our
stock VAD), the coach, and the pipeline, and run it. This is the BASELINE: honest stock
defaults (barge-in ON, stock VAD) so we can record how badly it fails the A–F table.

Run (opens http://localhost:7860 → /client; use an HTTPS tunnel for a phone, see
docs/runbook-local.md):

    python -m allegro.bot                                             # hosted (needs keys)
    ALLEGRO_PIPELINE=allegro.pipeline.local.yaml python -m allegro.bot   # $0 local, no keys

The in-house core this drives is fully tested in tests/test_core.py.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import yaml

from . import adapters  # noqa: F401  registers providers
from .core import CoachCore, IntentClassifier, SafetyGuardrail, TIMES_UP, TimerManager
from .obs import TurnLog
from .recipe import weeknight_skillet
from .registry import build_llm, build_stt, build_tts

CONFIG_PATH = Path(__file__).resolve().parent.parent / "allegro.pipeline.yaml"

# Cloud providers that need a key. Local/mock providers need none — the point of the
# Phase 0a profile.
_KEY_BY_PROVIDER = {
    "deepgram": "DEEPGRAM_API_KEY",
    "cartesia": "CARTESIA_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def load_config(path: str | Path | None = None) -> dict:
    """Load the pipeline profile. Override the default with ALLEGRO_PIPELINE, e.g.
    `ALLEGRO_PIPELINE=allegro.pipeline.local.yaml` for the bill-safe $0 profile."""
    chosen = path or os.environ.get("ALLEGRO_PIPELINE") or CONFIG_PATH
    return yaml.safe_load(Path(chosen).read_text())


def required_keys(cfg: dict) -> list[str]:
    keys = []
    for leg in ("stt", "tts", "llm"):
        key = _KEY_BY_PROVIDER.get(cfg["nodes"][leg]["provider"])
        if key:
            keys.append(key)
    return keys


def build_core(cfg: dict) -> CoachCore:
    """Assemble the in-house coach with the configured LLM behind it."""
    llm = build_llm(cfg["nodes"]["llm"])
    classifier = IntentClassifier(llm_classify=llm.classify)
    return CoachCore(
        recipe=weeknight_skillet(),
        classifier=classifier,
        safety=SafetyGuardrail(),
        answerer=llm.answer,
    )


def _make_coach_processor(core: CoachCore, turnlog: TurnLog):
    """Factory so Pipecat is imported lazily (keeps tests/core SDK-free)."""
    from pipecat.frames.frames import Frame, TranscriptionFrame, TTSSpeakFrame
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    class CoachProcessor(FrameProcessor):
        def __init__(self) -> None:
            super().__init__()
            self._core = core
            self._log = turnlog
            self._timers = TimerManager(self._on_timer)

        async def _on_timer(self, step) -> None:
            self._log.event("timer_elapsed", step=step.index)
            await self.push_frame(TTSSpeakFrame(TIMES_UP), FrameDirection.DOWNSTREAM)

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, TranscriptionFrame):
                loop = asyncio.get_event_loop()
                # core.handle is sync and may block on the LLM → run it off the loop.
                turn = await loop.run_in_executor(None, self._core.handle, frame.text)
                self._log.record(turn, vad="speech")
                if turn.pointer_after != turn.pointer_before:
                    # arm() cancels any existing timer, re-arms only if the new step is timed.
                    self._timers.arm(self._core.state.current())
                if turn.spoke:
                    await self.push_frame(
                        TTSSpeakFrame(turn.spoke), FrameDirection.DOWNSTREAM
                    )
            else:
                await self.push_frame(frame, direction)

    return CoachProcessor()


async def bot(runner_args) -> None:
    """Runner entry point — discovered by pipecat.runner and invoked once per browser
    connection with an established WebRTC connection on `runner_args.webrtc_connection`."""
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams
    from pipecat.frames.frames import TTSSpeakFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.transports.base_transport import TransportParams
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

    cfg = load_config()
    core = build_core(cfg)
    turnlog = TurnLog(Path("logs") / "session.jsonl")

    vad_params = cfg["nodes"]["vad"].get("params", {})
    transport = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(**vad_params)),
        ),
    )
    stt = build_stt(cfg["nodes"]["stt"])
    tts = build_tts(cfg["nodes"]["tts"])
    coach = _make_coach_processor(core, turnlog)

    @transport.event_handler("on_client_connected")
    async def _greet(_transport, _client):
        turnlog.event("session_start")
        await coach.push_frame(TTSSpeakFrame(core.greeting()))

    allow_int = cfg.get("runtime", {}).get("allow_interruptions", True)
    pipeline = Pipeline([transport.input(), stt, coach, tts, transport.output()])
    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=allow_int, enable_metrics=True),
    )
    await PipelineRunner(handle_sigint=runner_args.handle_sigint).run(task)


def main() -> None:
    """Pre-flight the keys the active profile needs, then hand off to the runner's server
    (it registers /start, /api/offer, /status and mounts the /client UI). Pass runner CLI
    flags through, e.g. `python -m allegro.bot --host 0.0.0.0 --port 7860`."""
    missing = [k for k in required_keys(load_config()) if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            f"missing {', '.join(missing)} — copy .env.example to .env and fill it in "
            "(or run the $0 local profile: ALLEGRO_PIPELINE=allegro.pipeline.local.yaml)"
        )
    from pipecat.runner.run import main as runner_main

    runner_main()


if __name__ == "__main__":
    main()
