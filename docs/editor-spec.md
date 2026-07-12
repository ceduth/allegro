# Visual pipeline editor — enhancement spec

Turning the read/swap editor (`allegro/editor/`) into a full pipeline editor: move/rewire
nodes, edit every field, and save/load named versions. Written as an implementable spec;
not yet built.

> Context: [`spike-plan.md`](./spike-plan.md) Phase 3. The editor is a GUI over a pipeline
> profile YAML; the bot reads that YAML on next start.

## The core constraint (read this first)

**The editor's ceiling is `bot.py`.** Today `bot.py` *hardcodes* the pipeline order
(`Pipeline([transport.input(), vad, stt, coach, tts, transport.output()])`) and the YAML is
a **dict of nodes** with no topology. The edges drawn in the editor are therefore
**decorative** — moving them changes nothing at runtime. Any real structure editing
requires the config to *carry* the structure and `bot.py` to *compile* from it.

**Design stance: a validated graph, not a free canvas.** A cascade has a semantic order
(VAD→STT→coach→TTS; transport in/out are endpoints; the LLM is a coach sidecar, not on the
audio path). A free-form canvas just lets you build unrunnable graphs. The compiler
validates every edit so Save only ever produces a runnable pipeline.

---

## Phase 3a — Make it a real editor (no runtime change) · ✅ shipped

No schema change, no `bot.py` change. Three fixes (all landed and browser-verified: nodes
drag and persist across re-renders, a per-node inspector edits every field, and Save writes
a `layout:` block the bot safely ignores):

### 3a.1 Fix node dragging
Nodes don't move because `App` rebuilds the node array from config every render, discarding
xyflow's positions. Fix with the standard controlled pattern:
- `const [nodes, setNodes, onNodesChange] = useNodesState(seed)` — seed **once** from config.
- Pass `onNodesChange` to `<ReactFlow>`; positions now persist across renders.
- Keep a separate `config` state for field edits; node `data` holds provider/params, node
  `position` holds layout. Don't recompute positions from config after seeding.

### 3a.2 Node inspector panel (right sidebar)
Select a node → edit its fields. This is where "edit all aspects" mostly lives:

| Node | Editable fields |
|---|---|
| VAD | `confidence`, `start_secs`, `stop_secs`, `min_volume` (number inputs) |
| STT | `provider` (select), `model` (text) |
| TTS | `provider`, `model`, `params.voice` |
| LLM | `provider`, `model` |
| transport | `type` (select) |
| runtime | `allow_interruptions` (checkbox), `timer_scale` (number) |
| coach | read-only — "builtin, not swappable" |

### 3a.3 Persist positions
On save, write a `layout:` block into the YAML (`layout: {vad: {x,y}, ...}`). `bot.py` and
`load_config` ignore unknown keys, so this is safe and forward-compatible with 3b.

**Payoff:** dragging works, every parameter is editable in-GUI, layout survives reload —
without touching the runtime. This alone makes the editor a genuine tool.

---

## Phase 3b — Compiled topology (the architectural lift) · ~2–3 days · touches runtime

Only needed to make **reorder / insert / remove / rewire** *mean* something. Be honest
about payoff: the 5 legs are all **required**, so insert/remove has little immediate use
until there are *optional* node types (a noise filter, a metrics logger, a turn-detector).
3b builds the machinery; its near-term value is the compiler + validation + position/graph
persistence. Defer until an optional processor actually needs placing, or until free rewire
is a real requirement.

### 3b.1 Schema v2 — declared graph

```yaml
version: 2
transport: { type: webrtc }
runtime: { allow_interruptions: false, timer_scale: 1.0 }
nodes:
  - { id: vad,   kind: vad,   provider: silero, params: {confidence: 0.5, ...}, enabled: true }
  - { id: stt,   kind: stt,   provider: whisper_mlx, model: large-v3-turbo-q4 }
  - { id: coach, kind: coach }                       # exactly one, fixed
  - { id: llm,   kind: llm,   provider: mock }         # sidecar — coach invokes it
  - { id: tts,   kind: tts,   provider: kokoro, params: {voice: af_heart} }
edges:                                                # the AUDIO path only
  - [transport.in, vad]
  - [vad, stt]
  - [stt, coach]
  - [coach, tts]
  - [tts, transport.out]
layout: { vad: {x: 150, y: 130}, stt: {x: 330, y: 130}, ... }
```

Key modeling point: **the LLM is not on the audio path.** It has `kind: llm`, no edges, and
is bound to the coach as a sidecar (the coach calls it per turn). The compiler builds it
separately and injects it into `build_core`.

### 3b.2 `bot.py` becomes a validating compiler

```
compile(config) -> Pipeline:
    validate(config)                       # raises on any invariant violation
    llm   = build_llm(node[kind==llm])     # sidecar
    core  = build_core(recipe, llm, ...)   # coach owns the llm
    chain = topo_sort(edges from transport.in → transport.out)   # main path
    procs = [build(node) for node in chain if node.enabled]      # vad/stt/coach/tts/…
    return Pipeline([transport.input(), *procs, transport.output()])
```

### 3b.3 Validation invariants (Save disabled + red nodes when violated)
- exactly one `coach`, one `stt`, one `tts`, one `llm`.
- the main path is a single acyclic chain from `transport.in` to `transport.out`.
- ordering by frame type: **VAD → STT → coach → TTS** (STT before coach, TTS after).
- every node's `provider` is registered for its `kind` (warn if it's a Phase-2 stub).
- endpoints (`transport.in/out`) appear exactly once and aren't rewired away.

### 3b.4 Back-compat / migration
`load_config` and `compile` accept **both** shapes: `nodes` is a dict → v1 (current
hardcoded order); `nodes` is a list (or `version: 2`) → v2 compiler. Ship a one-shot
`allegro.pipeline.migrate` that rewrites v1 → v2, and have the editor emit v2 on save. v1
keeps working so nothing breaks.

### 3b.5 Editor operations unlocked
- Splice a node into an edge (insert), delete/toggle optional nodes (required kinds can't be
  removed), reconnect edges **only where validation passes** (live-validated; invalid = red).
- A node palette (drag onto canvas) — seeded with real optional kinds as they're added.

---

## Phase 3c — Save/load versions · ~1 day · low risk

- **`pipelines/` directory** of named versions (`hosted.yaml`, `local.yaml`,
  `experiment-lowvad.yaml`). Root `allegro.pipeline*.yaml` stay as the defaults.
- **API:**

  | Method + path | Does |
  |---|---|
  | `GET /api/pipelines` | list `[{name, active}]` |
  | `GET /api/pipelines/{name}` | load `{config, layout}` |
  | `PUT /api/pipelines/{name}` | save / save-as (body = config) |
  | `DELETE /api/pipelines/{name}` | delete |
  | `GET /api/pipelines/{a}/diff/{b}` | *(optional; or diff client-side)* |

- **UI:** left sidebar version list — Load, Save, **Save as…**, Duplicate, Delete,
  mark-active; optional **diff two versions** (deep-diff rendered as a change list).
- **Active version:** the bot defaults to `allegro.pipeline.yaml`; "activate" writes a
  `pipelines/.active` pointer the bot honors, with `ALLEGRO_PIPELINE` still overriding.
- Layout persists per version (the `layout:` block from 3a).
- Git already versions the *canonical* profiles; this adds named *working* versions on top.

---

## Open decisions

1. **Track `pipelines/` in git?** Recommend **yes** (versions are shareable config, small).
2. **Active-version mechanism:** `.active` pointer file (default) + `ALLEGRO_PIPELINE`
   override — vs env-only. Recommend the pointer file so the editor can set it.
3. **Comment preservation:** the current save is a YAML dump (drops comments). If that
   matters, switch the editor to `ruamel.yaml` (round-trips comments) — adds a dep.
4. **Optional node types:** 3b's insert/remove is only useful once real optional processors
   exist. First candidates: a pre-STT noise/gain filter, a turn-detector, a metrics logger.

## Effort & sequencing

| Phase | Effort | Risk | Immediate payoff |
|---|---|---|---|
| 3a — drag + inspector + layout | ~½ day | low | **high** — real editing, no runtime change |
| 3b — compiled topology | ~2–3 days | med (touches runtime; re-verify live loop) | modest until optional nodes exist |
| 3c — versioning | ~1 day | low | high if you juggle several pipelines |

**Recommendation:** do **3a now** (cheap, high value, safe), then **3c** if you're managing
multiple pipelines. Hold **3b** until there's an actual optional-processor to place or free
rewire becomes a hard requirement — the compiler is real work whose payoff is future
extensibility, and **none of this moves the Phase-1 gate** (the 0b baseline cook does).
