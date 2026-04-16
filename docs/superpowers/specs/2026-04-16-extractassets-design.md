# ExtractAssets — Design Spec

**Date:** 2026-04-16
**Author:** Vedant Vijay (with Claude)
**Status:** Approved for implementation planning
**Phase:** 1 (single-user local tool). Phase 2 (hosted multi-user web app) informs today's boundaries but is out of scope for this spec.

---

## 1. Problem & Goals

Every short-form video (Instagram Reel, YouTube Short) has three distinct audio layers: **speech** (the creator talking), **sound effects** (short, usually repeated clips like whooshes, dings, pops), and **background music** (typically an identifiable song from the platform's music library). Existing stem-separation tools split audio by musical role (vocals / drums / bass / other), not by *editorial* role (speech / SFX / music). We need the editorial split.

**Goals (Phase 1):**
1. Given a single YouTube Shorts or Instagram Reel URL, produce:
   - `speech.wav` — the creator's voice
   - `music.wav` — the background music, plus metadata identifying the song when possible
   - `sfx/sfx_NN.wav` — a deduplicated library of individual SFX clips (one file per recurring effect)
2. Present all extracted assets in a modern web UI with inline playback (waveforms, native video), no downloads required to preview.
3. Use only free/local tooling. No API keys, no paid services.
4. Run locally on the user's Mac (Apple Silicon), single-user.
5. Build in swappable modules so individual stages can be iterated on without touching the rest of the system.

**Non-goals (Phase 1):**
- Transcription, translation, or subtitle generation.
- Audio fingerprinting fallback for music ID (will rely only on platform metadata via yt-dlp).
- Batch or queued processing — one URL at a time.
- Authentication, multi-tenancy, cloud hosting. These are Phase 2.
- Mobile or responsive design — desktop browser only (the user's Mac).

**Phase 2 outlook (not implemented today, but informs boundaries):**
The tool will eventually be offered as a hosted multi-user web app. Today's design uses interfaces for persistence, config, asset storage, and user identity so Phase 2 can swap the impls (file → DB, local disk → S3, hardcoded user → JWT auth) without rewriting the pipeline, orchestrator, or UI.

## 2. Architecture

Two processes during development, one in run mode.

- **Backend** (`backend/`) — FastAPI on `localhost:8000`. Runs the extraction pipeline as a mix of subprocess calls (`yt-dlp`, `ffmpeg`, `demucs`) and in-process Python (`librosa` for SFX mining). Exposes a REST API to start/cancel jobs and read config, a WebSocket to stream stage progress, and a static-file endpoint to stream extracted artifacts back to the UI for playback. Holds one job at a time in memory; a second `POST /api/jobs` while one is running returns HTTP 409.
- **Frontend** (`frontend/`) — Vite + React + Tailwind + wavesurfer.js SPA. On Extract, POSTs a new job, opens the WebSocket, transitions the right panel through `idle → processing → results` as stage events arrive. Loads audio/video via `GET /api/assets/{job_id}/{path}` URLs that resolve to files inside the job's output directory.

**Data flow for one run:**

```
User pastes URL
  → POST /api/jobs { url }              → { job_id, job_dir }
  → WS  /api/jobs/{job_id}/events       ← stream of stage events
                                        ← job.done { manifest } on completion
  → <video src="/api/assets/{id}/source.mp4">
  → <Waveform url="/api/assets/{id}/speech.wav">
  → <Waveform url="/api/assets/{id}/music.wav">
  → <SfxTile url="/api/assets/{id}/sfx/sfx_01.wav"> × N
```

**Run mode:** `./run.sh` starts uvicorn, which serves both the API and the pre-built React bundle on port 8000, then opens the browser.
**Dev mode:** `./dev.sh` runs vite on 5173 with `/api` proxied to uvicorn on 8000.

## 3. Pipeline Stages

Each stage is its own module under `backend/app/pipeline/`. All implement the same `Stage` protocol and are wired by the orchestrator without knowing about each other. The orchestrator runs them in order, passing each stage's artifacts as the next stage's inputs. Each stage checks if its outputs already exist and skips if so — re-running a failed job skips completed stages.

```python
# backend/app/pipeline/base.py
class Stage(Protocol):
    name: str
    def run(self, ctx: JobContext) -> StageResult: ...

@dataclass
class JobContext:
    job_dir: Path
    inputs: dict[str, Path]      # named artifacts from prior stages
    params: dict                 # config knobs for this stage
    emit: Callable[[StageEvent], None]

@dataclass
class StageResult:
    artifacts: dict[str, Path]   # name → relative path inside job_dir
    extra: dict                  # stage-specific metadata to include in manifest
```

### Stage 1 — `download.py`
- Tool: `yt-dlp` subprocess.
- Input: URL string (from `params`).
- Output: `source.mp4`, `source_meta.json` (raw yt-dlp info dict).
- Notes: yt-dlp's info dict surfaces `track`, `artist`, `album` when the platform has them (common on IG reels that use music from the IG library, and on YouTube Shorts with Content ID matches). This is our only music-identification source in Phase 1.

### Stage 2 — `audio.py`
- Tool: `ffmpeg` subprocess.
- Input: `source.mp4`.
- Output: `audio.wav` (44.1 kHz stereo PCM 16-bit).

### Stage 3 — `speech.py`
- Tool: `demucs` Python API.
- Model: `htdemucs_ft` (fine-tuned Hybrid Transformer Demucs).
- Device: `mps` on Apple Silicon, falls back to `cpu` if MPS unavailable or if a config toggle is set.
- Input: `audio.wav`.
- Output: `speech.wav` (vocals stem), `non_speech.wav` (drums+bass+other summed — everything that isn't vocals).

### Stage 4 — `sfx.py`
**This is the research-risk stage.** Phase 1 implementation:

1. Detect onsets in `non_speech.wav` with `librosa.onset.onset_detect` (backtracked to frame boundaries).
2. For each onset, extract a clip from `onset - 50ms` to `onset + min(1500ms, next_onset - 50ms)`, clamped to `[sfx_clip_min_ms, sfx_clip_max_ms]` (defaults 300ms, 1500ms).
3. Compute an MFCC feature vector per clip (13 coefficients, mean-pooled over time).
4. Cluster clips by cosine similarity using agglomerative clustering with a distance threshold.
5. Keep clusters with `>= sfx_min_cluster_size` members (default 2) — these are the repeated SFX.
6. For each kept cluster, export one representative clip (highest-energy member) as `sfx/sfx_NN.wav`.
7. Emit `sfx_clusters.json` with each cluster's member timestamps and count (for debugging and for stage 5).

Output: `sfx/sfx_NN.wav` files + `sfx_clusters.json`.
If zero clusters qualify, the stage succeeds with an empty `sfx/` directory — **this is not an error**.

**Why this implementation:** cheapest possible approach using only librosa. When it produces bad results on real reels, we swap the internals of this single file (e.g. to audfprint-style fingerprinting) without touching any other stage. Raw inputs (`non_speech.wav`) are preserved, so re-running stage 4 doesn't require re-running stages 1–3.

### Stage 5 — `music.py`
- Input: `non_speech.wav` + `sfx_clusters.json`.
- Zero out the time ranges covered by SFX cluster members in `non_speech.wav`, applying a 20 ms crossfade at each boundary to avoid clicks.
- Output: `music.wav`.
- Pull `track`, `artist`, `album` from `source_meta.json` if present; store in stage's `extra` metadata for the final manifest. If absent, music simply has no song metadata — still a valid result.

### Stage 6 — `finalize.py`
- Consolidates all stage `extra` metadata + artifact paths + durations into `metadata.json` (the AssetManifest, shape in §4).
- No subprocess work; pure aggregation.

## 4. API + WebSocket Contract

### REST endpoints

```
POST   /api/jobs
       body:   { url: string }
       return: 201 { job_id, job_dir } | 409 if another job is running

GET    /api/jobs/current
       return: { job_id, stages, current_stage, assets? } | 404 if none

POST   /api/jobs/{job_id}/cancel
       return: { ok: true }

GET    /api/config
       return: { output_base_dir, demucs_model, sfx_min_cluster_size,
                 sfx_clip_min_ms, sfx_clip_max_ms, demucs_device }

PUT    /api/config
       body:   (partial) subset of config fields

GET    /api/assets/{job_id}/{path}
       Streams a file from the job directory. `path` is validated against
       job_dir to prevent directory traversal.

GET    /api/jobs/{job_id}/log
       Returns the last N lines of the job's pipeline.log (for error UI).
```

### WebSocket

`WS /api/jobs/{job_id}/events` — single stream per job, JSON messages discriminated by `type`:

```ts
// on connect — full event replay for late-joining clients
{ type: "replay", events: StageEvent[] }

// stage lifecycle
{ type: "stage.start",    stage: StageName }
{ type: "stage.progress", stage: StageName, progress: 0..1, message?: string }
{ type: "stage.done",     stage: StageName, artifacts: { name: relative_path } }
{ type: "stage.error",    stage: StageName, message: string, retriable: boolean }

// job lifecycle
{ type: "job.done",       manifest: AssetManifest }
{ type: "job.error",      stage: StageName, message: string }
{ type: "job.canceled" }

type StageName = "download" | "audio" | "speech" | "sfx" | "music" | "finalize";
```

The backend keeps the last ~200 events per job in memory so a late-connecting client gets a full replay as the first frame. No message queue, no Redis — single-user constraint makes this trivial.

### AssetManifest (also written as `metadata.json`)

```ts
{
  job_id: string,
  source_url: string,
  created_at: string,           // ISO 8601
  duration_seconds: number,
  assets: {
    video:  { path: "source.mp4", duration: number },
    speech: { path: "speech.wav", duration: number },
    music:  {
      path: "music.wav",
      duration: number,
      song?: { title: string, artist: string, album?: string, source: "yt_dlp_meta" }
    },
    sfx: Array<{
      path: string,              // e.g. "sfx/sfx_01.wav"
      duration: number,
      repeats: number,           // cluster size from sfx_clusters.json
      onset_times: number[]      // seconds from start of video
    }>
  }
}
```

## 5. UI Structure

Split workspace matching the approved mockup (left controls, right workspace). Component tree:

```
<App>                        layout shell, WebSocket lifecycle, toast/error host
├── <LeftPanel>              ~320px fixed, controls
│   ├── <UrlInput>           URL field + "Extract" button
│   ├── <OutputDirPicker>    current output dir + "Change…" button
│   └── <Settings>           fold-out: SFX sensitivity, Demucs device (mps|cpu)
└── <RightPanel>             flex, state machine
    ├── <IdleState>          empty state + hint
    ├── <ProcessingState>    4 user-visible <StageCard>s (see stage mapping below)
    └── <ResultsState>
        ├── <VideoPreview>   native <video src=.../source.mp4>
        ├── <AssetCard title="Speech">     wavesurfer w/ speech color
        ├── <AssetCard title="Music">      wavesurfer w/ music color + song pills
        └── <SfxGrid>        grid of small <SfxTile>s
```

**Stage-card to pipeline-stage mapping.** The UI surfaces 4 user-meaningful cards. The 6 pipeline stages from §3 map to them as follows:

| StageCard (UI) | Pipeline stages (backend) |
|---|---|
| **Download** | `download` + `audio` (video fetch then ffmpeg extract) |
| **Separate speech** | `speech` (Demucs) |
| **Mine SFX** | `sfx` (onset detection + clustering) |
| **Identify music** | `music` + `finalize` (zero-out + manifest write) |

The frontend reads `stage.start`/`stage.done` events and updates the mapped card. Cards advance to "done" only when *all* their underlying pipeline stages report done. `finalize` is folded into the final card for presentation because it has no user-meaningful output beyond the manifest.

**State:** a single Zustand store `useJobStore` keyed by `jobId` with `{ status, stages, assets, error }`. The `useJobSocket(jobId)` hook reconciles WebSocket events into the store. No Redux.

**Waveforms:** `<Waveform>` wraps wavesurfer.js; takes `url` + `color` props; exposes `play/pause/seek` via ref. One component, three visual treatments (speech / music / sfx colors).

**Right-panel transitions:** Framer Motion fade + height animation between Idle → Processing → Results. StageCards transition outlined → in-progress → green-check as events arrive; their `stage.done` artifacts slide into the Results area *as each stage completes*, not only at the end. This makes the reveal feel continuous and also surfaces intermediate outputs for debugging.

**Frontend file structure:**

```
frontend/src/
  App.tsx
  components/
    LeftPanel/{UrlInput,OutputDirPicker,Settings}.tsx
    RightPanel/{IdleState,ProcessingState,ResultsState}.tsx
    AssetCard.tsx
    Waveform.tsx
    SfxTile.tsx
    StageCard.tsx
    VideoPreview.tsx
  hooks/{useJobSocket,useJobStore,useConfig}.ts
  lib/{api,ws,format}.ts
  styles/
```

**No component assumes "one job only."** `useJobStore` is keyed by `jobId`; the "only one at a time" rule is enforced server-side by the orchestrator. Phase 2 adds a jobs-list sidebar without refactoring components.

## 6. Output Layout, Config, Run UX

### Per-job output directory layout

```
<OUTPUT_BASE_DIR>/
  <yyyy-mm-dd>_<slug>_<short-hash>/       e.g. 2026-04-16_reel-sabrina_a3f2
    source.mp4
    source_meta.json
    audio.wav
    speech.wav
    non_speech.wav                        kept for debug and SFX stage re-run
    music.wav
    sfx/
      sfx_01.wav
      sfx_02.wav
      ...
    sfx_clusters.json                     cluster debug info
    metadata.json                         AssetManifest
    pipeline.log                          per-stage stdout/stderr
```

Intermediate artifacts (`non_speech.wav`, `sfx_clusters.json`) are kept so individual stages can be re-run without redoing earlier ones.

### Config

File path: `~/.extract-assets/config.json`. Defaults:

```json
{
  "output_base_dir": "~/Desktop/assets",
  "demucs_model": "htdemucs_ft",
  "demucs_device": "mps",
  "sfx_min_cluster_size": 2,
  "sfx_clip_min_ms": 300,
  "sfx_clip_max_ms": 1500
}
```

Accessed only via a `ConfigStore` interface. Default impl is file-backed; Phase 2 swaps to a DB-backed per-user impl.

### Output directory picker

Native OS directory pickers aren't available from a browser tab. UX: a text input with `~/` tilde expansion + "Reveal in Finder" button that calls `open <dir>` on the backend. Validated on change: must exist, must be writable.

### Run UX

```bash
# first time
./setup.sh      # uv sync, pnpm install, pnpm build, download Demucs weights

# each run
./run.sh        # uvicorn on :8000, waits for /health, opens default browser

# dev
./dev.sh        # vite on :5173 + uvicorn on :8000 in parallel
```

## 7. Error Handling

Per failure class:

| Failure | Stage | User sees | Retriable |
|---|---|---|---|
| Invalid URL / unsupported host | download | "URL not supported. yt-dlp couldn't parse." | yes |
| Video private / geo-blocked / 404 | download | Bubbled yt-dlp error | no |
| yt-dlp out of date | download | "Try `./update.sh` to refresh yt-dlp" | yes |
| ffmpeg decode error | audio | "Source media is corrupt" | yes (re-download) |
| Demucs OOM on MPS | speech | "Speech separation ran out of memory. Try CPU mode in Settings." | yes (after toggle) |
| Demucs missing weights | speech | "Run `./setup.sh` to install model weights" | yes |
| Zero SFX detected | sfx | **Not an error** — green with "0 SFX detected"; music stage proceeds | — |
| Disk full during write | any | "Disk full" | yes |
| User-initiated cancel | any | "Canceled" | — |

**Error model:** every stage raises `StageError(message: str, retriable: bool)`. The orchestrator catches and converts to a `stage.error` WS event, then halts the pipeline (no partial-success state machines). `retriable=true` surfaces a "Retry" button in the StageCard that re-runs from the failed stage forward; `retriable=false` shows only "New job."

**Logs:** each stage streams subprocess stdout/stderr to `pipeline.log` inside the job dir. `GET /api/jobs/{id}/log` returns the last N lines so the UI can show meaningful context on errors without forcing the user to a terminal.

## 8. Testing

MVP-appropriate scope. Not exhaustive.

1. **Pipeline stage unit tests** (`backend/tests/test_<stage>.py`) — each stage isolated with a fixture:
   - `test_audio.py`: fixture 5s MP4 → assert 44.1 kHz WAV exists, correct duration.
   - `test_sfx.py`: **synthetic** `non_speech.wav` generated with numpy — silence + the same sine-wave "beep" repeated 3×, plus a different beep once. Assert cluster count == 1, cluster size == 3, exported file exists, duration in range.
   - `test_music.py`: known input + known SFX cluster JSON → assert zeroed ranges in output.
2. **One real end-to-end test** (`backend/tests/test_e2e_fixture.py`) — committed 10-second fixture video in `backend/tests/fixtures/`, runs the full pipeline and asserts all 6 expected files exist. Marked `@pytest.mark.slow`; runs on demand.
3. **No React component tests in MVP.** Single-user tool; UI verified by hand.
4. **No API integration tests in MVP** beyond the pipeline tests. Endpoints are thin shells over the orchestrator.
5. **No CI in Phase 1.** Phase 2 adds GitHub Actions.

## 9. Phase 2 Extension Points

These interfaces exist from day one in Phase 1, with simple default impls. Phase 2 swaps the impls without touching callers.

| Interface | Phase 1 impl | Phase 2 impl |
|---|---|---|
| `JobStore` | in-memory dict keyed by `job_id` | Postgres `jobs` table |
| `ConfigStore` | JSON file at `~/.extract-assets/config.json` | per-user DB row |
| `AssetStorage` | local filesystem under `OUTPUT_BASE_DIR` | S3/R2 bucket, signed URLs |
| `UserContext` | hardcoded `user_id = "default"` | JWT-decoded user from request |
| `JobOrchestrator` | sync single-slot (409 on conflict) | queue-backed worker pool (Celery/RQ) with per-user quotas |

Additional Phase 2 work not prefigured today: auth middleware, per-user output-dir partitioning under `<user_id>/`, WebSocket auth (`user_id` must own `job_id`), rate limits, GPU contention management, storage quotas, cloud deployment, CI/CD.

## 10. Top-level Project Structure

```
extractassets/
  backend/
    app/
      main.py                # FastAPI app + route mounting
      api/                   # route handlers, one file per resource
        jobs.py
        config.py
        assets.py
        health.py
      pipeline/
        __init__.py          # orchestrator
        base.py              # Stage protocol, JobContext, StageResult, StageError
        download.py
        audio.py
        speech.py
        sfx.py
        music.py
        finalize.py
      storage/
        job_store.py         # JobStore interface + InMemoryJobStore impl
        config_store.py      # ConfigStore interface + FileConfigStore impl
        asset_storage.py     # AssetStorage interface + LocalAssetStorage impl
      ws/
        event_bus.py         # per-job event buffer + pub/sub
      core/
        user_context.py      # UserContext interface + DefaultUserContext impl
        errors.py            # StageError
    tests/
      fixtures/
      test_audio.py
      test_sfx.py
      test_music.py
      test_e2e_fixture.py
    pyproject.toml
  frontend/
    (see §5)
    package.json
    vite.config.ts
    tailwind.config.ts
  scripts/
    setup.sh
    run.sh
    dev.sh
    update.sh
  docs/
    superpowers/specs/2026-04-16-extractassets-design.md     # this file
  README.md
```

---

## Approvals

- [x] Architecture (§2)
- [x] Pipeline stages (§3)
- [x] API + WebSocket (§4)
- [x] UI structure (§5)
- [x] Output / config / run UX (§6)
- [x] Errors + testing (§7, §8)
- [x] Phase 2 extension points (§9)
