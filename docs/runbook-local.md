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

This pulls `pipecat-ai[deepgram,cartesia,silero,webrtc,whisper,kokoro,runner]` — the
`runner` extra provides the dev server (`/start`, `/api/offer`) and the prebuilt `/client`
UI that `bot.py` runs under. (Deepgram/Cartesia/Anthropic SDKs come along but go unused on
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

## 4. Connect

### First, validate on the laptop (no HTTPS needed)

`localhost` is a browser **secure context**, so the mic + WebRTC work over plain HTTP:

1. Open `http://localhost:7860/client` on the same machine.
2. Click **Connect** (top-right). Allow the mic.
3. You should hear the greeting (step one), then be able to talk to the coach.

Do this first — it's the fastest proof the whole loop works, for $0.

### Then the phone — needs HTTPS (a tunnel)

**You cannot use `http://<lan-ip>:7860` on a phone.** Browsers block the microphone
(`getUserMedia`) and WebRTC on any non-localhost HTTP origin, and Chrome force-upgrades
LAN IPs to `https://` — which hits the plain-HTTP server and gives `ERR_SSL_PROTOCOL_ERROR`
(server log: `Invalid HTTP request received`). Give the phone a real HTTPS origin with a
tunnel. With the bot running, in another terminal:

```bash
cloudflared tunnel --url http://localhost:7860     # prints a https://<random>.trycloudflare.com URL
# or:  ngrok http 7860
```

Open the printed `https://…/client` on the phone, allow the mic, and cook. Signaling goes
through the tunnel; the audio itself is still WebRTC peer-to-peer over your LAN. Prop the
phone ~3 ft away. Every turn writes to `logs/session.jsonl`.

> Alternative to a tunnel: run the server with a self-signed TLS cert and accept the
> browser warning on the phone — more fiddly than a tunnel; the tunnel is recommended.

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
| Browser: *"Unable to connect"*; server log: `POST /start 404` | Stale install without the runner (or the old hand-rolled server). `bot.py` runs under `pipecat.runner.run`, which serves `/start`. Re-run `pip install -e ".[live,dev]"` (pulls `pipecat-ai[runner]`). |
| `ERR_SSL_PROTOCOL_ERROR` on the LAN IP; log says `Invalid HTTP request received` | Chrome force-upgraded `http://<ip>` to `https://` against the plain-HTTP server. Don't use the LAN IP — use `localhost` on the laptop, or a tunnel for the phone (§4). |
| Mic blocked / no mic prompt on the phone | Non-localhost HTTP is not a secure context, so `getUserMedia` is blocked. There is no header/flag fix worth chasing — use a tunnel (§4). `localhost` on the laptop is exempt. |
| No greeting / no audio back after connecting | Capture the server log and the browser EVENTS panel. The greeting fires on `on_client_connected` (confirmed correct on 1.4.0); if the pipeline connects but is silent, check STT/TTS built and the mic track started. |
| Agent gets cut off by noise | **Expected** on stock defaults (`allow_interruptions: true`). That's the Phase 0 baseline finding, not a bug — record it. |

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
