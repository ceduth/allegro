"""Visual pipeline editor backend — a tiny FastAPI app that serves the xyflow editor and
reads/writes a pipeline profile. It is independent of the bot runtime: the editor edits the
YAML on disk, and the bot picks up the change on its next start. This is the whole payoff of
the declarative design — the editor is a GUI over the same config a human hand-edits.

Run:  python -m allegro.editor            # edits allegro.pipeline.yaml
      ALLEGRO_PIPELINE=allegro.pipeline.local.yaml python -m allegro.editor
Then open http://localhost:7870

Note: saving rewrites the YAML via a dump, so hand-written comments are not preserved.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

from ..registry import available

ROOT = Path(__file__).resolve().parent.parent.parent
HERE = Path(__file__).resolve().parent

# Classify providers so the UI can label them. Paid needs a key; mock is zero-network;
# everything else is local/OSS.
_PAID = {"deepgram", "cartesia", "anthropic"}


def _yaml_path() -> Path:
    return Path(os.environ.get("ALLEGRO_PIPELINE") or ROOT / "allegro.pipeline.yaml")


def _kind(name: str) -> str:
    return "paid" if name in _PAID else "mock" if name == "mock" else "local"


app = FastAPI(title="Allegro pipeline editor")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(HERE / "index.html")


@app.get("/api/providers")
def providers() -> dict:
    """Registry swap surface: {leg: [{name, kind}]} for the node dropdowns."""
    import allegro.adapters  # noqa: F401  registers providers (SDKs import lazily)

    return {
        leg: [{"name": n, "kind": _kind(n)} for n in names]
        for leg, names in available().items()
    }


@app.get("/api/pipeline")
def get_pipeline() -> dict:
    return {"path": str(_yaml_path()), "config": yaml.safe_load(_yaml_path().read_text())}


@app.put("/api/pipeline")
async def put_pipeline(request: Request) -> dict:
    config = await request.json()
    path = _yaml_path()
    path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    return {"ok": True, "path": str(path)}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=7870)


if __name__ == "__main__":
    main()
