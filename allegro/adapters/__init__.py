"""Importing this package registers every provider adapter (paid + OSS stubs) with the
registry. ``bot.py`` does ``import allegro.adapters`` before building the pipeline."""

from . import llm, stt, tts  # noqa: F401  (import side effect: registration)
