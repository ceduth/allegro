# Runbook — local $0 voice loop (faster-whisper + Kokoro)

Stand up the Phase 0a profile: `mock` LLM (zero network) + local STT/TTS, no API keys,
no per-token bill. This is the runbook to actually *talk to the coach for free* before
spending a cent on the hosted baseline.

> Profile: [`../allegro.pipeline.local.yaml`](../allegro.pipeline.local.yaml).
> Why this order: [`billing.md`](./billing.md).

## 0. Prereqs

- Python **3.11+** (`python3 --version`).
- Phone and computer on the **same Wi-Fi** (the phone browser connects peer-to-peer to
  your machine over WebRTC).
- ~2–4 GB free disk: Python deps + the Whisper and Kokoro models (downloaded once).
- macOS note: Pipecat's Silero VAD and Kokoro run on **onnxruntime**, faster-whisper on
  **CTranslate2** — no PyTorch/CUDA needed on Apple Silicon.

## 1. Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e ".[live,dev]"
```

This pulls `pipecat-ai[deepgram,cartesia,silero,webrtc,whisper,kokoro]` plus the
small-webrtc prebuilt UI. (Deepgram/Cartesia/Anthropic SDKs come along but go unused on
the local profile.)

> **macOS / Apple Silicon (verified on pipecat-ai 1.4.0):** Pipecat's Whisper STT module
> does a module-level `import mlx_whisper` on macOS, so it won't import without it — even
> though faster-whisper is the actual backend. The `[live]` extra installs it
> automatically via a `sys_platform == 'darwin'` marker; if you installed without that,
> run `pip install "pipecat-ai[mlx-whisper]"`.

## 2. Verify the version-sensitive bits (do this before the first run)

Kokoro is a recent Pipecat addition; confirm your pinned version actually ships it, and
that the local STT imports resolve:

```bash
python -c "import pipecat.services.kokoro.tts; print('kokoro OK')"
python -c "from pipecat.services.whisper.stt import WhisperSTTService, Model; print('whisper OK')"
```

- **`kokoro OK` fails?** Your `pipecat-ai` predates the Kokoro service. Edit
  `allegro.pipeline.local.yaml` → set `tts.provider: piper` (already wired as the
  fallback), then `pip install "pipecat-ai[piper]"`. *(On 1.4.0 it's present — confirmed.)*
- **`whisper OK` fails with `No module named 'mlx_whisper'`** (macOS): `pip install
  "pipecat-ai[mlx-whisper]"` — see the note in §1. *(Confirmed: this is required on Apple
  Silicon with 1.4.0.)*

## 3. Run the local profile

```bash
ALLEGRO_PIPELINE=allegro.pipeline.local.yaml python -m allegro.bot
```

- **First run is slow**: the Whisper model (~hundreds of MB) and Kokoro model + voices
  download and cache. Subsequent runs are offline.
- The server requires **no API keys** on this profile — if it complains about a missing
  key, you're accidentally on the hosted profile (check `ALLEGRO_PIPELINE`).

## 4. Connect the phone

1. Find your computer's LAN IP: `ipconfig getifaddr en0` (Wi-Fi) on macOS.
2. On the phone browser, open `http://<that-ip>:7860/client`.
3. Allow microphone access. You should hear the greeting (the step-one recipe line).
4. Prop the phone ~3 ft away and cook. Every turn writes to `logs/session.jsonl`.

## 5. Watch the turn log

```bash
tail -f logs/session.jsonl
```

Each line carries `transcript · vad · intent · source · pointer_before/after · spoke`.
Per the spec, most failures are diagnosable straight from this — keep it open while testing.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `import pipecat.services.kokoro.tts` fails | Old Pipecat — switch `tts.provider` to `piper` (§2). |
| Whisper error: *"device does not support efficient float16"* | On CPU/Apple Silicon keep `compute_type: int8` (the local profile default). Don't set `float16` without CUDA. |
| Phone can't reach `:7860` | Different Wi-Fi, or macOS firewall blocking Python. Same network; allow incoming connections for the Python binary. |
| No greeting / no audio back | The `on_client_connected` event name is `# VERIFY` in `bot.py` — confirm it against your installed Pipecat (see bot.py:build_pipeline). |
| Agent gets cut off by noise | **Expected** on stock defaults (`allow_interruptions: true`). That's the Phase 0 baseline finding, not a bug — record it. |
| Mic permission blocked on phone | `http://` over LAN may need the site marked as allowed; some browsers gate mic to secure contexts — try Safari on iOS, or Chrome which allows mic on private-IP origins. |

## What this proves (and doesn't)

- **Proves:** the cascade runs end-to-end locally, the coach logic drives a real voice
  loop, the turn log captures everything — all at **$0**.
- **Doesn't prove:** the A1–A5 noise kill-criteria. Local STT/TTS on dev Wi-Fi is not the
  noisy-kitchen rig, and Kokoro/Whisper are not the hosted Cartesia/Deepgram you baseline
  in 0b. Treat 0a as logic validation; the acceptance table is 0b on the real rig.

## Teardown (full cleanup)

Everything installs into the repo-local `.venv` — the base/system Python is never touched.
The only things that live *outside* the venv are the model caches (shared across projects
by design), so a complete reset is:

```bash
# 1. the virtualenv (all Python deps: pipecat, faster-whisper, kokoro, mlx-whisper, …)
rm -rf .venv

# 2. the downloaded models — these survive deleting .venv
rm -rf ~/.cache/pipecat/kokoro-onnx          # Kokoro model + voices (~330 MB)
rm -rf ~/.cache/huggingface/hub/models--*whisper*   # Whisper model (~400 MB)

# 3. local run artifacts (gitignored, optional)
rm -rf logs/
```

Nothing else is created: no global pip installs, no system packages, no launch agents.
Deleting `.venv` reclaims the dependencies; step 2 reclaims the ~700 MB of model files.
