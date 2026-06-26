"""Provider registry — the swap surface.

Each leg (STT / LLM / TTS) is a name → builder mapping. Swapping a model is a one-line
change in allegro.pipeline.yaml; adding a provider is one adapter + one register call.
Builders import their heavy SDKs lazily (inside the function) so importing this module —
and registering an OSS stub — never requires the provider's package to be installed.
"""

from __future__ import annotations

from typing import Any, Callable

Builder = Callable[[dict], Any]

_STT: dict[str, Builder] = {}
_LLM: dict[str, Builder] = {}
_TTS: dict[str, Builder] = {}


def register_stt(name: str) -> Callable[[Builder], Builder]:
    def deco(fn: Builder) -> Builder:
        _STT[name] = fn
        return fn
    return deco


def register_llm(name: str) -> Callable[[Builder], Builder]:
    def deco(fn: Builder) -> Builder:
        _LLM[name] = fn
        return fn
    return deco


def register_tts(name: str) -> Callable[[Builder], Builder]:
    def deco(fn: Builder) -> Builder:
        _TTS[name] = fn
        return fn
    return deco


def _build(table: dict[str, Builder], cfg: dict, leg: str) -> Any:
    provider = cfg["provider"]
    if provider not in table:
        raise KeyError(f"no {leg} provider '{provider}'; registered: {sorted(table)}")
    return table[provider](cfg)


def build_stt(cfg: dict) -> Any:
    return _build(_STT, cfg, "stt")


def build_llm(cfg: dict) -> Any:
    return _build(_LLM, cfg, "llm")


def build_tts(cfg: dict) -> Any:
    return _build(_TTS, cfg, "tts")


def available() -> dict[str, list[str]]:
    return {"stt": sorted(_STT), "llm": sorted(_LLM), "tts": sorted(_TTS)}
