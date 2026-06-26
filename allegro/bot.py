"""Phase 0 baseline bot: SmallWebRTC (phone browser) → Silero VAD → Deepgram STT →
CoachProcessor → Cartesia TTS, wired from allegro.pipeline.yaml.

This is the BASELINE: honest stock defaults (barge-in ON, stock VAD) so we can record
how badly it fails the A–F kitchen table. Do not tune here — tuning is Phase 1.

Run:  python -m allegro.bot   (needs the [live] extras + API keys; see README)

NOTE: a few Pipecat constructor/event details are version-sensitive and flagged inline
with `# VERIFY`. The in-house core this drives is fully tested in tests/test_core.py.
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


def load_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text())


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
    """Defined inside a factory so Pipecat is imported lazily (keeps tests SDK-free)."""
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


def build_pipeline(conn, cfg: dict, core: CoachCore, turnlog: TurnLog):
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.transports.base_transport import TransportParams
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

    vad_params = cfg["nodes"]["vad"].get("params", {})
    transport = SmallWebRTCTransport(
        webrtc_connection=conn,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(**vad_params)),
        ),
    )
    stt = build_stt(cfg["nodes"]["stt"])
    tts = build_tts(cfg["nodes"]["tts"])
    coach = _make_coach_processor(core, turnlog)

    # VERIFY: on client connect, greet once. Event name is version-sensitive.
    @transport.event_handler("on_client_connected")
    async def _greet(_t, _client):  # pragma: no cover - live only
        from pipecat.frames.frames import TTSSpeakFrame

        turnlog.event("session_start")
        await coach.push_frame(TTSSpeakFrame(core.greeting()))

    pipeline = Pipeline([transport.input(), stt, coach, tts, transport.output()])
    return pipeline


def make_fastapi_app():
    from fastapi import BackgroundTasks, FastAPI
    from fastapi.responses import JSONResponse
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
    from pipecat_ai_small_webrtc_prebuilt.frontend import SmallWebRTCPrebuiltUI

    cfg = load_config()
    allow_int = cfg.get("runtime", {}).get("allow_interruptions", True)
    app = FastAPI(title="Allegro Phase 0 baseline")
    app.mount("/client", SmallWebRTCPrebuiltUI)  # phone browser → /client

    async def run_bot(conn: SmallWebRTCConnection) -> None:
        core = build_core(cfg)
        turnlog = TurnLog(Path("logs") / "session.jsonl")
        pipeline = build_pipeline(conn, cfg, core, turnlog)
        task = PipelineTask(
            pipeline,
            params=PipelineParams(allow_interruptions=allow_int, enable_metrics=True),
        )
        await PipelineRunner().run(task)

    @app.post("/api/offer")
    async def offer(request: dict, background_tasks: BackgroundTasks):  # VERIFY signatures
        conn = SmallWebRTCConnection(ice_servers=["stun:stun.l.google.com:19302"])
        await conn.initialize(sdp=request["sdp"], type=request["type"])
        background_tasks.add_task(run_bot, conn)
        return JSONResponse(conn.get_answer())

    return app


def main() -> None:
    import uvicorn

    for key in ("DEEPGRAM_API_KEY", "CARTESIA_API_KEY", "ANTHROPIC_API_KEY"):
        if not os.environ.get(key):
            raise SystemExit(f"missing {key} — copy .env.example to .env and fill it in")
    uvicorn.run(make_fastapi_app(), host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
