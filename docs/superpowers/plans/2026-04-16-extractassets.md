# ExtractAssets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web tool that extracts three editorial audio assets — speech, deduplicated sound-effects, and background music — from any Instagram Reel or YouTube Short URL, with a polished React UI for inline playback.

**Architecture:** FastAPI backend (Python) drives a 6-stage extraction pipeline (yt-dlp → ffmpeg → Demucs → librosa SFX mining → music zero-out → manifest). Progress streams to a Vite+React+Tailwind SPA via WebSocket. Single-user Phase 1; interfaces (`JobStore`, `ConfigStore`, `AssetStorage`, `UserContext`) drawn today so Phase 2 multi-user hosting is a non-rewriting extension.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, uvicorn, yt-dlp, demucs, librosa, numpy, soundfile, pydantic, pytest, httpx
- Frontend: React 18, TypeScript, Vite, TailwindCSS, Zustand, wavesurfer.js, framer-motion
- Tooling: `uv` for Python deps, `pnpm` for Node deps
- Platform: macOS (Apple Silicon, MPS acceleration)

**Spec reference:** [docs/superpowers/specs/2026-04-16-extractassets-design.md](../specs/2026-04-16-extractassets-design.md)

**Note on git:** Commit steps are included as reference checkpoints. The user has opted out of git for now — treat commits as "milestone passed, safe point to pause" markers. When ready, `git init` and the plan's commit commands work as-is.

---

## Phase 1 — Backend Pipeline (Tasks 1-14)

Phase 1 produces a CLI-testable extraction pipeline. At the end of Task 14 you can run `python -m app.pipeline.cli <url>` and get the 6 expected output files on disk without any API or UI. This is where all the novel/risky work lives — get it right before layering anything on top.

---

### Task 1: Backend scaffolding & health endpoint

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/health.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
*.egg-info/

# Node
node_modules/
dist/
.vite/

# Local
.DS_Store
.extract-assets/
outputs/

# Superpowers
.superpowers/
```

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[project]
name = "extractassets-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "pydantic>=2.5",
    "python-multipart>=0.0.9",
    "yt-dlp>=2024.3.10",
    "demucs>=4.0.1",
    "librosa>=0.10.1",
    "numpy>=1.26",
    "soundfile>=0.12",
    "scikit-learn>=1.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow (select with -m slow)",
]
```

- [ ] **Step 3: Create health endpoint**

```python
# backend/app/api/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/health")
def health():
    return {"ok": True}
```

```python
# backend/app/main.py
from fastapi import FastAPI
from app.api import health

def create_app() -> FastAPI:
    app = FastAPI(title="ExtractAssets")
    app.include_router(health.router)
    return app

app = create_app()
```

- [ ] **Step 4: Write failing test**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app

def test_health_returns_ok():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
```

- [ ] **Step 5: Install deps and run tests**

Run: `cd backend && uv venv && uv pip install -e ".[dev]" && uv run pytest -v`
Expected: `test_health_returns_ok PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/ .gitignore
git commit -m "feat(backend): scaffold FastAPI app with health endpoint"
```

---

### Task 2: Pipeline base types (Stage protocol, context, errors)

**Files:**
- Create: `backend/app/pipeline/__init__.py`
- Create: `backend/app/pipeline/base.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/tests/test_pipeline_base.py`

- [ ] **Step 1: Create error type**

```python
# backend/app/core/errors.py
class StageError(Exception):
    """Raised by a pipeline stage when it cannot complete."""
    def __init__(self, message: str, retriable: bool = True):
        super().__init__(message)
        self.message = message
        self.retriable = retriable
```

- [ ] **Step 2: Create pipeline base types**

```python
# backend/app/pipeline/base.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, Any

StageName = str  # one of "download"|"audio"|"speech"|"sfx"|"music"|"finalize"

@dataclass
class StageEvent:
    """Emitted by a stage during run() via the emit callback."""
    type: str  # "progress"
    stage: StageName
    progress: float | None = None  # 0.0 - 1.0
    message: str | None = None

@dataclass
class JobContext:
    job_id: str
    job_dir: Path
    inputs: dict[str, Path] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    emit: Callable[[StageEvent], None] = lambda _e: None

@dataclass
class StageResult:
    artifacts: dict[str, Path] = field(default_factory=dict)  # name → relative path inside job_dir
    extra: dict[str, Any] = field(default_factory=dict)       # stage-specific metadata for manifest

class Stage(Protocol):
    name: StageName
    def run(self, ctx: JobContext) -> StageResult: ...
```

- [ ] **Step 3: Write tests**

```python
# backend/tests/test_pipeline_base.py
from pathlib import Path
from app.pipeline.base import JobContext, StageResult, StageEvent, Stage
from app.core.errors import StageError

def test_stage_error_defaults_retriable_true():
    err = StageError("boom")
    assert err.retriable is True
    assert err.message == "boom"

def test_stage_error_non_retriable():
    err = StageError("permanent", retriable=False)
    assert err.retriable is False

def test_job_context_defaults():
    ctx = JobContext(job_id="j1", job_dir=Path("/tmp/j1"))
    assert ctx.inputs == {}
    assert ctx.params == {}
    # default emit is a no-op
    ctx.emit(StageEvent(type="progress", stage="download", progress=0.5))

def test_stage_result_defaults():
    res = StageResult()
    assert res.artifacts == {}
    assert res.extra == {}

def test_stage_protocol_compliance():
    class DummyStage:
        name = "download"
        def run(self, ctx: JobContext) -> StageResult:
            return StageResult()
    stage: Stage = DummyStage()
    assert stage.name == "download"
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_pipeline_base.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline backend/app/core backend/tests/test_pipeline_base.py
git commit -m "feat(pipeline): define Stage protocol, JobContext, StageResult, StageError"
```

---

### Task 3: ConfigStore interface + FileConfigStore impl

**Files:**
- Create: `backend/app/storage/__init__.py`
- Create: `backend/app/storage/config_store.py`
- Create: `backend/tests/test_config_store.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_config_store.py
import json
from pathlib import Path
import pytest
from app.storage.config_store import Config, ConfigStore, FileConfigStore, DEFAULT_CONFIG

def test_default_config_has_expected_fields():
    assert DEFAULT_CONFIG.output_base_dir
    assert DEFAULT_CONFIG.demucs_model == "htdemucs_ft"
    assert DEFAULT_CONFIG.demucs_device in ("mps", "cpu")
    assert DEFAULT_CONFIG.sfx_min_cluster_size == 2
    assert DEFAULT_CONFIG.sfx_clip_min_ms == 300
    assert DEFAULT_CONFIG.sfx_clip_max_ms == 1500

def test_file_config_store_loads_defaults_when_missing(tmp_path: Path):
    store = FileConfigStore(tmp_path / "config.json")
    cfg = store.load()
    assert cfg.demucs_model == "htdemucs_ft"

def test_file_config_store_saves_and_loads(tmp_path: Path):
    p = tmp_path / "config.json"
    store = FileConfigStore(p)
    cfg = store.load()
    cfg.sfx_min_cluster_size = 3
    store.save(cfg)
    # reload
    store2 = FileConfigStore(p)
    cfg2 = store2.load()
    assert cfg2.sfx_min_cluster_size == 3

def test_file_config_store_partial_update(tmp_path: Path):
    p = tmp_path / "config.json"
    store = FileConfigStore(p)
    store.update({"demucs_device": "cpu"})
    cfg = store.load()
    assert cfg.demucs_device == "cpu"
    # untouched fields keep defaults
    assert cfg.demucs_model == "htdemucs_ft"

def test_file_config_store_expands_tilde(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = tmp_path / "config.json"
    store = FileConfigStore(p)
    store.update({"output_base_dir": "~/my-assets"})
    cfg = store.load()
    assert cfg.output_base_dir == str(tmp_path / "my-assets")
```

- [ ] **Step 2: Implement ConfigStore**

```python
# backend/app/storage/config_store.py
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Protocol, Any

@dataclass
class Config:
    output_base_dir: str = "~/Desktop/assets"
    demucs_model: str = "htdemucs_ft"
    demucs_device: str = "mps"
    sfx_min_cluster_size: int = 2
    sfx_clip_min_ms: int = 300
    sfx_clip_max_ms: int = 1500

DEFAULT_CONFIG = Config()

def _expand(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("~"):
        return os.path.expanduser(value)
    return value

class ConfigStore(Protocol):
    def load(self) -> Config: ...
    def save(self, cfg: Config) -> None: ...
    def update(self, patch: dict[str, Any]) -> Config: ...

class FileConfigStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> Config:
        if not self.path.exists():
            return Config()
        data = json.loads(self.path.read_text())
        # Expand tildes on read; start from defaults for forward-compat
        merged = asdict(Config())
        merged.update({k: _expand(v) for k, v in data.items() if k in merged})
        return Config(**merged)

    def save(self, cfg: Config) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(cfg), indent=2))

    def update(self, patch: dict[str, Any]) -> Config:
        cfg = self.load()
        valid = {f.name for f in fields(Config)}
        for k, v in patch.items():
            if k in valid:
                setattr(cfg, k, _expand(v))
        self.save(cfg)
        return cfg
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_config_store.py -v`
Expected: all 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/storage backend/tests/test_config_store.py
git commit -m "feat(storage): add ConfigStore interface + FileConfigStore impl"
```

---

### Task 4: JobStore interface + InMemoryJobStore impl

**Files:**
- Create: `backend/app/storage/job_store.py`
- Create: `backend/tests/test_job_store.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_job_store.py
import pytest
from app.storage.job_store import JobState, JobStatus, InMemoryJobStore

def test_create_job_returns_id_and_state():
    store = InMemoryJobStore()
    job = store.create(url="https://example.com/reel/1", job_dir="/tmp/j1")
    assert job.job_id
    assert job.status == JobStatus.PENDING
    assert job.url == "https://example.com/reel/1"

def test_get_returns_none_when_missing():
    store = InMemoryJobStore()
    assert store.get("nope") is None

def test_get_current_returns_only_active_job():
    store = InMemoryJobStore()
    j1 = store.create(url="u1", job_dir="/tmp/j1")
    assert store.get_current() is not None
    store.set_status(j1.job_id, JobStatus.DONE)
    assert store.get_current() is None

def test_create_while_running_raises():
    store = InMemoryJobStore()
    store.create(url="u1", job_dir="/tmp/j1")
    with pytest.raises(RuntimeError, match="already running"):
        store.create(url="u2", job_dir="/tmp/j2")

def test_set_status_transitions():
    store = InMemoryJobStore()
    job = store.create(url="u1", job_dir="/tmp/j1")
    store.set_status(job.job_id, JobStatus.RUNNING)
    assert store.get(job.job_id).status == JobStatus.RUNNING

def test_set_stage_updates_current_stage():
    store = InMemoryJobStore()
    job = store.create(url="u1", job_dir="/tmp/j1")
    store.set_current_stage(job.job_id, "speech")
    assert store.get(job.job_id).current_stage == "speech"

def test_cancel_marks_canceled():
    store = InMemoryJobStore()
    job = store.create(url="u1", job_dir="/tmp/j1")
    store.set_status(job.job_id, JobStatus.CANCELED)
    assert store.get(job.job_id).status == JobStatus.CANCELED
    assert store.get_current() is None
```

- [ ] **Step 2: Implement JobStore**

```python
# backend/app/storage/job_store.py
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELED = "canceled"

@dataclass
class JobState:
    job_id: str
    url: str
    job_dir: str
    status: JobStatus = JobStatus.PENDING
    current_stage: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

class JobStore(Protocol):
    def create(self, url: str, job_dir: str) -> JobState: ...
    def get(self, job_id: str) -> JobState | None: ...
    def get_current(self) -> JobState | None: ...
    def set_status(self, job_id: str, status: JobStatus, error: str | None = None) -> None: ...
    def set_current_stage(self, job_id: str, stage: str) -> None: ...

ACTIVE = {JobStatus.PENDING, JobStatus.RUNNING}

class InMemoryJobStore:
    def __init__(self):
        self._jobs: dict[str, JobState] = {}

    def create(self, url: str, job_dir: str) -> JobState:
        if self.get_current() is not None:
            raise RuntimeError("a job is already running")
        job_id = uuid.uuid4().hex[:12]
        state = JobState(job_id=job_id, url=url, job_dir=job_dir)
        self._jobs[job_id] = state
        return state

    def get(self, job_id: str) -> JobState | None:
        return self._jobs.get(job_id)

    def get_current(self) -> JobState | None:
        for j in self._jobs.values():
            if j.status in ACTIVE:
                return j
        return None

    def set_status(self, job_id: str, status: JobStatus, error: str | None = None) -> None:
        job = self._jobs[job_id]
        job.status = status
        if error:
            job.error_message = error

    def set_current_stage(self, job_id: str, stage: str) -> None:
        self._jobs[job_id].current_stage = stage
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_job_store.py -v`
Expected: all 7 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/storage/job_store.py backend/tests/test_job_store.py
git commit -m "feat(storage): add JobStore interface + InMemoryJobStore"
```

---

### Task 5: EventBus (per-job event buffer + pub/sub)

**Files:**
- Create: `backend/app/ws/__init__.py`
- Create: `backend/app/ws/event_bus.py`
- Create: `backend/tests/test_event_bus.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_event_bus.py
import asyncio
import pytest
from app.ws.event_bus import EventBus

@pytest.mark.asyncio
async def test_publish_buffers_event():
    bus = EventBus(buffer_size=10)
    await bus.publish("j1", {"type": "stage.start", "stage": "download"})
    assert len(bus.replay("j1")) == 1

@pytest.mark.asyncio
async def test_subscribe_receives_live_events():
    bus = EventBus(buffer_size=10)
    queue = bus.subscribe("j1")
    await bus.publish("j1", {"type": "stage.start", "stage": "download"})
    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert msg == {"type": "stage.start", "stage": "download"}

@pytest.mark.asyncio
async def test_two_subscribers_both_receive():
    bus = EventBus(buffer_size=10)
    q1 = bus.subscribe("j1")
    q2 = bus.subscribe("j1")
    await bus.publish("j1", {"type": "x"})
    assert (await asyncio.wait_for(q1.get(), 1.0)) == {"type": "x"}
    assert (await asyncio.wait_for(q2.get(), 1.0)) == {"type": "x"}

@pytest.mark.asyncio
async def test_subscriber_for_different_job_isolated():
    bus = EventBus(buffer_size=10)
    q1 = bus.subscribe("j1")
    q2 = bus.subscribe("j2")
    await bus.publish("j1", {"type": "x"})
    assert not q2.qsize()
    assert (await asyncio.wait_for(q1.get(), 1.0))["type"] == "x"

@pytest.mark.asyncio
async def test_buffer_evicts_oldest_beyond_size():
    bus = EventBus(buffer_size=3)
    for i in range(5):
        await bus.publish("j1", {"i": i})
    replayed = bus.replay("j1")
    assert len(replayed) == 3
    assert replayed[0]["i"] == 2  # first 2 evicted
    assert replayed[-1]["i"] == 4
```

- [ ] **Step 2: Implement EventBus**

```python
# backend/app/ws/event_bus.py
from __future__ import annotations
import asyncio
from collections import defaultdict, deque
from typing import Any

class EventBus:
    """
    Per-job event bus with bounded replay buffer.
    - publish(job_id, event)    -> buffers + fans out to all live subscribers
    - subscribe(job_id) -> queue live events (does NOT replay)
    - replay(job_id) -> returns buffered events so caller can send them first
    """
    def __init__(self, buffer_size: int = 200):
        self._buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=buffer_size))
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        self._buffers[job_id].append(event)
        for q in list(self._subscribers[job_id]):
            await q.put(event)

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        if q in self._subscribers[job_id]:
            self._subscribers[job_id].remove(q)

    def replay(self, job_id: str) -> list[dict[str, Any]]:
        return list(self._buffers[job_id])
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_event_bus.py -v`
Expected: all 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/ws backend/tests/test_event_bus.py
git commit -m "feat(ws): add EventBus with per-job replay buffer"
```

---

### Task 6: AssetStorage interface + LocalAssetStorage impl

**Files:**
- Create: `backend/app/storage/asset_storage.py`
- Create: `backend/tests/test_asset_storage.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_asset_storage.py
from pathlib import Path
import pytest
from app.storage.asset_storage import LocalAssetStorage, AssetNotFound, PathTraversal

def test_create_job_dir_returns_path(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    p = s.create_job_dir(job_id="abc", slug="reel-demo")
    assert p.exists()
    assert p.parent == tmp_path
    assert "abc" in p.name
    assert "reel-demo" in p.name

def test_resolve_within_job_dir(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    p = s.create_job_dir(job_id="abc", slug="x")
    (p / "foo.wav").write_bytes(b"data")
    resolved = s.resolve(p.name, "foo.wav")
    assert resolved == p / "foo.wav"

def test_resolve_nested_subpath(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    p = s.create_job_dir(job_id="abc", slug="x")
    (p / "sfx").mkdir()
    (p / "sfx" / "sfx_01.wav").write_bytes(b"d")
    resolved = s.resolve(p.name, "sfx/sfx_01.wav")
    assert resolved == p / "sfx" / "sfx_01.wav"

def test_resolve_rejects_traversal(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    p = s.create_job_dir(job_id="abc", slug="x")
    with pytest.raises(PathTraversal):
        s.resolve(p.name, "../../etc/passwd")

def test_resolve_raises_on_missing_job(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    with pytest.raises(AssetNotFound):
        s.resolve("nonexistent", "foo.wav")
```

- [ ] **Step 2: Implement LocalAssetStorage**

```python
# backend/app/storage/asset_storage.py
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Protocol

class AssetNotFound(Exception): pass
class PathTraversal(Exception): pass

def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9-]+", "-", s.lower()).strip("-")
    return (s or "untitled")[:40]

class AssetStorage(Protocol):
    def create_job_dir(self, job_id: str, slug: str) -> Path: ...
    def resolve(self, job_dir_name: str, relpath: str) -> Path: ...

class LocalAssetStorage:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_job_dir(self, job_id: str, slug: str) -> Path:
        date = datetime.utcnow().strftime("%Y-%m-%d")
        name = f"{date}_{_slugify(slug)}_{job_id[:6]}"
        p = self.base_dir / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def resolve(self, job_dir_name: str, relpath: str) -> Path:
        job_dir = (self.base_dir / job_dir_name).resolve()
        if not job_dir.exists() or not job_dir.is_dir():
            raise AssetNotFound(job_dir_name)
        target = (job_dir / relpath).resolve()
        try:
            target.relative_to(job_dir)
        except ValueError:
            raise PathTraversal(relpath)
        return target
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_asset_storage.py -v`
Expected: all 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/storage/asset_storage.py backend/tests/test_asset_storage.py
git commit -m "feat(storage): add AssetStorage with path-traversal-safe resolve"
```

---

### Task 7: UserContext interface + DefaultUserContext impl

**Files:**
- Create: `backend/app/core/user_context.py`
- Create: `backend/tests/test_user_context.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_user_context.py
from app.core.user_context import UserContext, DefaultUserContext

def test_default_user_context_returns_default_user():
    ctx = DefaultUserContext()
    assert ctx.user_id() == "default"

def test_user_context_is_protocol():
    class CustomUC:
        def user_id(self) -> str:
            return "alice"
    uc: UserContext = CustomUC()
    assert uc.user_id() == "alice"
```

- [ ] **Step 2: Implement UserContext**

```python
# backend/app/core/user_context.py
from __future__ import annotations
from typing import Protocol

class UserContext(Protocol):
    def user_id(self) -> str: ...

class DefaultUserContext:
    """Phase 1: hardcoded single user. Phase 2 swaps for JWT-decoded impl."""
    def user_id(self) -> str:
        return "default"
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_user_context.py -v`
Expected: 2 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/user_context.py backend/tests/test_user_context.py
git commit -m "feat(core): add UserContext interface with default single-user impl"
```

---

### Task 8: Pipeline Stage 1 — download.py (yt-dlp wrapper)

**Files:**
- Create: `backend/app/pipeline/download.py`
- Create: `backend/tests/test_stage_download.py`

Note: we test by mocking subprocess so tests stay fast and offline. Real yt-dlp is covered by the e2e test (Task 27).

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_stage_download.py
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from app.pipeline.base import JobContext
from app.pipeline.download import DownloadStage
from app.core.errors import StageError

def _ctx(tmp_path: Path, url: str) -> JobContext:
    return JobContext(
        job_id="j1",
        job_dir=tmp_path,
        params={"url": url},
    )

@patch("app.pipeline.download.subprocess.run")
def test_download_success_writes_mp4_and_meta(mock_run, tmp_path: Path):
    # Simulate yt-dlp writing a file and printing metadata JSON
    def side_effect(cmd, *a, **kw):
        # The download command
        if "--write-info-json" in cmd:
            (tmp_path / "source.mp4").write_bytes(b"fakevideo")
            (tmp_path / "source.info.json").write_text(json.dumps({
                "title": "Demo Reel",
                "track": "Espresso",
                "artist": "Sabrina Carpenter"
            }))
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect
    stage = DownloadStage()
    result = stage.run(_ctx(tmp_path, "https://instagram.com/reel/abc"))

    assert "video" in result.artifacts
    assert (tmp_path / result.artifacts["video"]).exists()
    assert "meta" in result.artifacts
    meta = json.loads((tmp_path / result.artifacts["meta"]).read_text())
    assert meta["track"] == "Espresso"

@patch("app.pipeline.download.subprocess.run")
def test_download_failure_raises_stage_error(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR: Private video")
    stage = DownloadStage()
    with pytest.raises(StageError) as exc:
        stage.run(_ctx(tmp_path, "https://instagram.com/reel/private"))
    assert "Private" in exc.value.message

def test_download_requires_url_param(tmp_path: Path):
    stage = DownloadStage()
    with pytest.raises(StageError):
        stage.run(JobContext(job_id="j1", job_dir=tmp_path, params={}))
```

- [ ] **Step 2: Implement download stage**

```python
# backend/app/pipeline/download.py
from __future__ import annotations
import subprocess
import shutil
from pathlib import Path
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError

class DownloadStage:
    name = "download"

    def run(self, ctx: JobContext) -> StageResult:
        url = ctx.params.get("url")
        if not url:
            raise StageError("missing url param", retriable=False)

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0, message="starting"))

        # Use yt-dlp to download video + info JSON
        out_template = str(ctx.job_dir / "source.%(ext)s")
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--no-warnings",
            "--write-info-json",
            "--restrict-filenames",
            "-o", out_template,
            "-f", "mp4/best[ext=mp4]/best",
            url,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise StageError(f"yt-dlp failed: {proc.stderr.strip()[:200]}")

        # Normalize filenames
        video = ctx.job_dir / "source.mp4"
        meta = ctx.job_dir / "source.info.json"
        if not video.exists():
            # yt-dlp may have picked a different extension; find it
            candidates = [p for p in ctx.job_dir.glob("source.*") if p.suffix != ".json"]
            if not candidates:
                raise StageError("download succeeded but no video file found", retriable=False)
            shutil.move(str(candidates[0]), str(video))

        if not meta.exists():
            raise StageError("download succeeded but no info JSON found", retriable=False)

        # Rename info.json → source_meta.json (spec uses that name)
        dst_meta = ctx.job_dir / "source_meta.json"
        shutil.move(str(meta), str(dst_meta))

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0, message="done"))
        return StageResult(
            artifacts={"video": Path("source.mp4"), "meta": Path("source_meta.json")},
        )
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_stage_download.py -v`
Expected: 3 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipeline/download.py backend/tests/test_stage_download.py
git commit -m "feat(pipeline): add download stage (yt-dlp wrapper)"
```

---

### Task 9: Pipeline Stage 2 — audio.py (ffmpeg extract)

**Files:**
- Create: `backend/app/pipeline/audio.py`
- Create: `backend/tests/test_stage_audio.py`
- Create: `backend/tests/fixtures/tiny.mp4` (generated in step 1)

- [ ] **Step 1: Generate tiny MP4 fixture**

Run:
```bash
cd backend && mkdir -p tests/fixtures && \
  ffmpeg -y -f lavfi -i "sine=frequency=440:duration=2" -f lavfi -i "color=c=black:s=64x64:d=2" \
    -c:v libx264 -c:a aac -pix_fmt yuv420p tests/fixtures/tiny.mp4
```
Expected: creates a 2-second 64×64 video with a 440Hz tone. ~10KB file.

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_stage_audio.py
import shutil
from pathlib import Path
import soundfile as sf
from app.pipeline.base import JobContext
from app.pipeline.audio import AudioStage

FIXTURE = Path(__file__).parent / "fixtures" / "tiny.mp4"

def _ctx_with_video(tmp_path: Path) -> JobContext:
    shutil.copy(FIXTURE, tmp_path / "source.mp4")
    return JobContext(
        job_id="j1",
        job_dir=tmp_path,
        inputs={"video": tmp_path / "source.mp4"},
    )

def test_audio_produces_wav(tmp_path: Path):
    stage = AudioStage()
    result = stage.run(_ctx_with_video(tmp_path))
    out = tmp_path / result.artifacts["audio"]
    assert out.exists()
    data, sr = sf.read(out)
    assert sr == 44100
    assert data.ndim == 2  # stereo
    assert abs(len(data) / sr - 2.0) < 0.1  # ~2 seconds
```

- [ ] **Step 3: Implement audio stage**

```python
# backend/app/pipeline/audio.py
from __future__ import annotations
import subprocess
from pathlib import Path
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError

class AudioStage:
    name = "audio"

    def run(self, ctx: JobContext) -> StageResult:
        video = ctx.inputs.get("video")
        if not video or not video.exists():
            raise StageError("missing video input", retriable=False)

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0))
        out = ctx.job_dir / "audio.wav"
        cmd = [
            "ffmpeg", "-y", "-i", str(video),
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise StageError(f"ffmpeg failed: {proc.stderr.strip()[:200]}")
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0))
        return StageResult(artifacts={"audio": Path("audio.wav")})
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_stage_audio.py -v`
Expected: 1 test PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/audio.py backend/tests/test_stage_audio.py backend/tests/fixtures/tiny.mp4
git commit -m "feat(pipeline): add audio stage (ffmpeg extract to 44.1kHz stereo WAV)"
```

---

### Task 10: Pipeline Stage 3 — speech.py (Demucs wrapper)

**Files:**
- Create: `backend/app/pipeline/speech.py`
- Create: `backend/tests/test_stage_speech.py`

Demucs is heavy. We mock the actual separator call and assert the stage produces the right artifact names + file writes. Real Demucs is exercised in Task 27 (e2e).

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_stage_speech.py
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import soundfile as sf
from app.pipeline.base import JobContext
from app.pipeline.speech import SpeechStage

def _prep_audio(tmp_path: Path) -> JobContext:
    # 2s of stereo silence, 44.1kHz
    sf.write(tmp_path / "audio.wav", np.zeros((88200, 2), dtype=np.float32), 44100)
    return JobContext(
        job_id="j1",
        job_dir=tmp_path,
        inputs={"audio": tmp_path / "audio.wav"},
        params={"model": "htdemucs_ft", "device": "cpu"},
    )

@patch("app.pipeline.speech._run_demucs")
def test_speech_produces_vocals_and_non_speech(mock_run, tmp_path: Path):
    # Fake Demucs: writes vocals.wav and a no_vocals.wav
    def fake_run(audio_path, out_dir, model, device):
        out_dir.mkdir(parents=True, exist_ok=True)
        sf.write(out_dir / "vocals.wav", np.zeros((88200, 2), dtype=np.float32), 44100)
        sf.write(out_dir / "no_vocals.wav", np.ones((88200, 2), dtype=np.float32) * 0.1, 44100)
    mock_run.side_effect = fake_run

    stage = SpeechStage()
    result = stage.run(_prep_audio(tmp_path))
    assert (tmp_path / result.artifacts["speech"]).exists()
    assert (tmp_path / result.artifacts["non_speech"]).exists()
    # non_speech.wav should not be all zeros
    data, _ = sf.read(tmp_path / result.artifacts["non_speech"])
    assert data.any()
```

- [ ] **Step 2: Implement speech stage**

```python
# backend/app/pipeline/speech.py
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError

def _run_demucs(audio_path: Path, out_dir: Path, model: str, device: str) -> None:
    """Actual Demucs invocation. Isolated so tests can mock it."""
    cmd = [
        "python", "-m", "demucs",
        "-n", model,
        "-d", device,
        "--two-stems=vocals",
        "-o", str(out_dir),
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise StageError(f"demucs failed: {proc.stderr.strip()[:300]}")

class SpeechStage:
    name = "speech"

    def run(self, ctx: JobContext) -> StageResult:
        audio = ctx.inputs.get("audio")
        if not audio or not audio.exists():
            raise StageError("missing audio input", retriable=False)

        model = ctx.params.get("model", "htdemucs_ft")
        device = ctx.params.get("device", "mps")
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0, message=f"running {model} on {device}"))

        demucs_out = ctx.job_dir / "_demucs"
        _run_demucs(audio, demucs_out, model, device)

        # Demucs writes to: <out_dir>/<model>/<audio_stem>/vocals.wav
        # and the complement as no_vocals.wav when --two-stems=vocals is used.
        # In tests we bypass that nesting by writing to out_dir directly.
        vocals = _find(demucs_out, "vocals.wav")
        no_vocals = _find(demucs_out, "no_vocals.wav")
        if not vocals or not no_vocals:
            raise StageError("demucs output files not found", retriable=False)

        speech_path = ctx.job_dir / "speech.wav"
        non_speech_path = ctx.job_dir / "non_speech.wav"
        shutil.move(str(vocals), str(speech_path))
        shutil.move(str(no_vocals), str(non_speech_path))
        shutil.rmtree(demucs_out, ignore_errors=True)

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0))
        return StageResult(
            artifacts={
                "speech": Path("speech.wav"),
                "non_speech": Path("non_speech.wav"),
            }
        )

def _find(root: Path, name: str) -> Path | None:
    for p in root.rglob(name):
        return p
    return None
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_stage_speech.py -v`
Expected: 1 test PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipeline/speech.py backend/tests/test_stage_speech.py
git commit -m "feat(pipeline): add speech stage (Demucs wrapper) with mocked tests"
```

---

### Task 11: Pipeline Stage 4 — sfx.py (onset + MFCC clustering)

**Files:**
- Create: `backend/app/pipeline/sfx.py`
- Create: `backend/tests/test_stage_sfx.py`

This is the research-risk stage. The test uses a fully synthetic audio file with a known repeated pattern, so we can assert the clustering finds exactly what we placed.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_stage_sfx.py
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from app.pipeline.base import JobContext
from app.pipeline.sfx import SfxStage

SR = 44100

def _beep(freq: float, dur_s: float, sr: int = SR) -> np.ndarray:
    t = np.linspace(0, dur_s, int(sr * dur_s), endpoint=False)
    env = np.hanning(len(t))  # smooth envelope so onsets look realistic
    mono = 0.6 * env * np.sin(2 * np.pi * freq * t)
    return np.stack([mono, mono], axis=1).astype(np.float32)

def _silence(dur_s: float, sr: int = SR) -> np.ndarray:
    return np.zeros((int(sr * dur_s), 2), dtype=np.float32)

def _prep_non_speech(tmp_path: Path) -> JobContext:
    # Layout: 0.5s silence, beep(800Hz, 0.4s), 1.0s silence, beep(800Hz, 0.4s),
    # 1.0s silence, beep(800Hz, 0.4s), 0.5s silence, beep(2000Hz, 0.4s) once.
    segments = [
        _silence(0.5),
        _beep(800, 0.4),
        _silence(1.0),
        _beep(800, 0.4),
        _silence(1.0),
        _beep(800, 0.4),
        _silence(0.5),
        _beep(2000, 0.4),
    ]
    audio = np.concatenate(segments, axis=0)
    sf.write(tmp_path / "non_speech.wav", audio, SR)
    return JobContext(
        job_id="j1",
        job_dir=tmp_path,
        inputs={"non_speech": tmp_path / "non_speech.wav"},
        params={"min_cluster_size": 2, "clip_min_ms": 300, "clip_max_ms": 1500},
    )

def test_sfx_detects_repeated_beep_cluster(tmp_path: Path):
    stage = SfxStage()
    result = stage.run(_prep_non_speech(tmp_path))

    # Expect at least one cluster (800Hz beep, 3 members), and the 2000Hz beep
    # should NOT be a cluster (only 1 instance, below min_cluster_size=2).
    clusters_path = tmp_path / "sfx_clusters.json"
    assert clusters_path.exists()
    clusters = json.loads(clusters_path.read_text())
    assert len(clusters) == 1
    assert clusters[0]["count"] == 3

    sfx_dir = tmp_path / "sfx"
    exported = sorted(sfx_dir.glob("*.wav"))
    assert len(exported) == 1  # one representative per kept cluster

def test_sfx_empty_output_when_no_clusters(tmp_path: Path):
    # Only 1 beep, min_cluster_size=2 → no clusters
    audio = np.concatenate([_silence(0.5), _beep(800, 0.4), _silence(0.5)], axis=0)
    sf.write(tmp_path / "non_speech.wav", audio, SR)
    ctx = JobContext(
        job_id="j1", job_dir=tmp_path,
        inputs={"non_speech": tmp_path / "non_speech.wav"},
        params={"min_cluster_size": 2, "clip_min_ms": 300, "clip_max_ms": 1500},
    )
    stage = SfxStage()
    result = stage.run(ctx)

    clusters = json.loads((tmp_path / "sfx_clusters.json").read_text())
    assert clusters == []
    sfx_dir = tmp_path / "sfx"
    assert sfx_dir.exists()
    assert list(sfx_dir.glob("*.wav")) == []
```

- [ ] **Step 2: Implement SFX stage**

```python
# backend/app/pipeline/sfx.py
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import librosa
import soundfile as sf
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError

N_MFCC = 13
CLUSTER_DIST_THRESHOLD = 0.35  # cosine distance; tuned for MFCC-mean vectors

class SfxStage:
    name = "sfx"

    def run(self, ctx: JobContext) -> StageResult:
        non_speech = ctx.inputs.get("non_speech")
        if not non_speech or not non_speech.exists():
            raise StageError("missing non_speech input", retriable=False)

        min_members = int(ctx.params.get("min_cluster_size", 2))
        clip_min_ms = int(ctx.params.get("clip_min_ms", 300))
        clip_max_ms = int(ctx.params.get("clip_max_ms", 1500))

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0, message="loading audio"))

        y, sr = librosa.load(str(non_speech), sr=None, mono=True)
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.2, message="detecting onsets"))

        onsets = librosa.onset.onset_detect(y=y, sr=sr, units="samples", backtrack=True)
        clip_min = int(sr * clip_min_ms / 1000)
        clip_max = int(sr * clip_max_ms / 1000)

        clips: list[dict] = []
        for i, start in enumerate(onsets):
            next_onset = onsets[i + 1] if i + 1 < len(onsets) else len(y)
            end = min(start + clip_max, next_onset, len(y))
            if end - start < clip_min:
                end = min(start + clip_min, len(y))
            if end - start < int(sr * 0.1):  # < 100ms, too short to be useful
                continue
            clip = y[start:end]
            mfcc = librosa.feature.mfcc(y=clip, sr=sr, n_mfcc=N_MFCC)
            feat = mfcc.mean(axis=1)
            clips.append({
                "start_s": float(start / sr),
                "end_s": float(end / sr),
                "feat": feat,
                "energy": float(np.sqrt((clip ** 2).mean())),
            })

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.5, message=f"clustering {len(clips)} candidates"))

        clusters_serialized: list[dict] = []
        sfx_dir = ctx.job_dir / "sfx"
        sfx_dir.mkdir(exist_ok=True)
        sfx_artifacts: dict[str, Path] = {}

        if len(clips) >= min_members:
            feats = np.vstack([c["feat"] for c in clips])
            dist = cosine_distances(feats)
            # agglomerative with precomputed distances
            n_samples = len(clips)
            algo = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=CLUSTER_DIST_THRESHOLD,
                metric="precomputed",
                linkage="average",
            )
            labels = algo.fit_predict(dist)

            # group clips by label
            groups: dict[int, list[int]] = {}
            for idx, label in enumerate(labels):
                groups.setdefault(int(label), []).append(idx)

            # keep only groups with >= min_members, export one representative (highest energy)
            kept = [(label, indices) for label, indices in groups.items() if len(indices) >= min_members]
            kept.sort(key=lambda x: len(x[1]), reverse=True)

            y_stereo, sr_stereo = sf.read(str(non_speech))
            if y_stereo.ndim == 1:
                y_stereo = np.stack([y_stereo, y_stereo], axis=1)

            for n, (label, indices) in enumerate(kept, start=1):
                rep = max(indices, key=lambda i: clips[i]["energy"])
                c = clips[rep]
                start_samp = int(c["start_s"] * sr_stereo)
                end_samp = int(c["end_s"] * sr_stereo)
                clip_audio = y_stereo[start_samp:end_samp]
                fname = f"sfx_{n:02d}.wav"
                sf.write(str(sfx_dir / fname), clip_audio, sr_stereo)
                sfx_artifacts[f"sfx_{n:02d}"] = Path("sfx") / fname
                clusters_serialized.append({
                    "index": n,
                    "count": len(indices),
                    "representative_path": f"sfx/{fname}",
                    "onset_times_s": [clips[i]["start_s"] for i in indices],
                    "offset_times_s": [clips[i]["end_s"] for i in indices],
                })

        (ctx.job_dir / "sfx_clusters.json").write_text(json.dumps(clusters_serialized, indent=2))
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0,
                            message=f"{len(clusters_serialized)} clusters"))
        return StageResult(
            artifacts={**sfx_artifacts, "clusters_meta": Path("sfx_clusters.json")},
            extra={"sfx_count": len(clusters_serialized)},
        )
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_stage_sfx.py -v`
Expected: 2 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipeline/sfx.py backend/tests/test_stage_sfx.py
git commit -m "feat(pipeline): add sfx stage (onset + MFCC agglomerative clustering)"
```

---

### Task 12: Pipeline Stage 5 — music.py (zero-out SFX, pull song metadata)

**Files:**
- Create: `backend/app/pipeline/music.py`
- Create: `backend/tests/test_stage_music.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_stage_music.py
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from app.pipeline.base import JobContext
from app.pipeline.music import MusicStage

SR = 44100

def _prep(tmp_path: Path, song_meta: dict | None = None) -> JobContext:
    # 3 seconds of constant 0.5 amplitude stereo
    audio = np.ones((SR * 3, 2), dtype=np.float32) * 0.5
    sf.write(tmp_path / "non_speech.wav", audio, SR)
    # Pretend 1.0s-1.5s is an SFX cluster member → should be zeroed
    clusters = [{
        "index": 1,
        "count": 2,
        "representative_path": "sfx/sfx_01.wav",
        "onset_times_s": [1.0],
        "offset_times_s": [1.5],
    }]
    (tmp_path / "sfx_clusters.json").write_text(json.dumps(clusters))
    meta = {"title": "Demo"}
    if song_meta:
        meta.update(song_meta)
    (tmp_path / "source_meta.json").write_text(json.dumps(meta))
    return JobContext(
        job_id="j1",
        job_dir=tmp_path,
        inputs={
            "non_speech": tmp_path / "non_speech.wav",
            "clusters_meta": tmp_path / "sfx_clusters.json",
            "meta": tmp_path / "source_meta.json",
        },
    )

def test_music_zeroes_sfx_ranges(tmp_path: Path):
    stage = MusicStage()
    result = stage.run(_prep(tmp_path))
    out = sf.read(tmp_path / result.artifacts["music"])[0]
    # Sample at 1.25s should be zero-ish (in the zeroed range)
    mid_sample = int(1.25 * SR)
    assert abs(out[mid_sample].mean()) < 0.01
    # Sample at 0.2s should be ~0.5 (untouched)
    early = int(0.2 * SR)
    assert abs(out[early].mean() - 0.5) < 0.05

def test_music_extracts_song_meta_when_present(tmp_path: Path):
    stage = MusicStage()
    result = stage.run(_prep(tmp_path, {"track": "Espresso", "artist": "Sabrina Carpenter"}))
    assert result.extra["song"]["title"] == "Espresso"
    assert result.extra["song"]["artist"] == "Sabrina Carpenter"
    assert result.extra["song"]["source"] == "yt_dlp_meta"

def test_music_no_song_meta_when_absent(tmp_path: Path):
    stage = MusicStage()
    result = stage.run(_prep(tmp_path))
    assert result.extra.get("song") is None
```

- [ ] **Step 2: Implement music stage**

```python
# backend/app/pipeline/music.py
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError

CROSSFADE_MS = 20

class MusicStage:
    name = "music"

    def run(self, ctx: JobContext) -> StageResult:
        non_speech = ctx.inputs.get("non_speech")
        clusters_meta = ctx.inputs.get("clusters_meta")
        source_meta = ctx.inputs.get("meta")
        if not non_speech or not clusters_meta or not source_meta:
            raise StageError("missing inputs for music stage", retriable=False)

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0))

        audio, sr = sf.read(str(non_speech))
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        audio = audio.astype(np.float32).copy()

        clusters = json.loads(clusters_meta.read_text())
        crossfade_samples = int(sr * CROSSFADE_MS / 1000)

        for cluster in clusters:
            for start_s, end_s in zip(cluster["onset_times_s"], cluster["offset_times_s"]):
                s = max(0, int(start_s * sr))
                e = min(len(audio), int(end_s * sr))
                if e <= s:
                    continue
                # Apply crossfade at boundaries: linear ramp into zero then out
                fade_in_end = min(e, s + crossfade_samples)
                fade_out_start = max(s, e - crossfade_samples)
                if fade_in_end > s:
                    ramp = np.linspace(1.0, 0.0, fade_in_end - s)[:, None]
                    audio[s:fade_in_end] *= ramp
                if e > fade_out_start:
                    ramp = np.linspace(0.0, 1.0, e - fade_out_start)[:, None]
                    audio[fade_out_start:e] *= ramp
                if fade_out_start > fade_in_end:
                    audio[fade_in_end:fade_out_start] = 0.0

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.7))

        out_path = ctx.job_dir / "music.wav"
        sf.write(str(out_path), audio, sr)

        # Pull song metadata from yt-dlp info dict if present
        meta = json.loads(source_meta.read_text())
        song = None
        title = meta.get("track") or meta.get("song_title")
        artist = meta.get("artist") or meta.get("creator")
        if title:
            song = {
                "title": title,
                "artist": artist,
                "album": meta.get("album"),
                "source": "yt_dlp_meta",
            }

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0))
        return StageResult(
            artifacts={"music": Path("music.wav")},
            extra={"song": song} if song else {"song": None},
        )
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_stage_music.py -v`
Expected: 3 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipeline/music.py backend/tests/test_stage_music.py
git commit -m "feat(pipeline): add music stage (SFX zero-out + song metadata extraction)"
```

---

### Task 13: Pipeline Stage 6 — finalize.py (manifest writer)

**Files:**
- Create: `backend/app/pipeline/finalize.py`
- Create: `backend/tests/test_stage_finalize.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_stage_finalize.py
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from app.pipeline.base import JobContext
from app.pipeline.finalize import FinalizeStage

SR = 44100

def _fake_wav(p: Path, dur_s: float):
    sf.write(str(p), np.zeros((int(SR * dur_s), 2), dtype=np.float32), SR)

def test_finalize_writes_manifest(tmp_path: Path):
    # Fake prior-stage outputs
    _fake_wav(tmp_path / "source.mp4", 2.0)  # stand-in for video (we only read duration from audio)
    _fake_wav(tmp_path / "speech.wav", 2.0)
    _fake_wav(tmp_path / "music.wav", 2.0)
    sfx_dir = tmp_path / "sfx"
    sfx_dir.mkdir()
    _fake_wav(sfx_dir / "sfx_01.wav", 0.5)
    (tmp_path / "sfx_clusters.json").write_text(json.dumps([
        {"index": 1, "count": 3, "representative_path": "sfx/sfx_01.wav",
         "onset_times_s": [0.5, 1.0, 1.5], "offset_times_s": [0.7, 1.2, 1.7]}
    ]))

    ctx = JobContext(
        job_id="j1",
        job_dir=tmp_path,
        inputs={
            "video": tmp_path / "source.mp4",
            "speech": tmp_path / "speech.wav",
            "music": tmp_path / "music.wav",
            "clusters_meta": tmp_path / "sfx_clusters.json",
        },
        params={"source_url": "https://example.com/reel/1"},
    )
    ctx.params["song"] = {"title": "Demo", "artist": "A", "source": "yt_dlp_meta"}

    stage = FinalizeStage()
    result = stage.run(ctx)
    manifest = json.loads((tmp_path / result.artifacts["manifest"]).read_text())

    assert manifest["job_id"] == "j1"
    assert manifest["source_url"] == "https://example.com/reel/1"
    assert manifest["assets"]["speech"]["path"] == "speech.wav"
    assert manifest["assets"]["music"]["song"]["title"] == "Demo"
    assert len(manifest["assets"]["sfx"]) == 1
    assert manifest["assets"]["sfx"][0]["repeats"] == 3
```

- [ ] **Step 2: Implement finalize stage**

```python
# backend/app/pipeline/finalize.py
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
import soundfile as sf
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError

def _duration(p: Path) -> float:
    try:
        info = sf.info(str(p))
        return float(info.duration)
    except Exception:
        return 0.0

class FinalizeStage:
    name = "finalize"

    def run(self, ctx: JobContext) -> StageResult:
        speech = ctx.inputs.get("speech")
        music = ctx.inputs.get("music")
        clusters_meta = ctx.inputs.get("clusters_meta")
        video = ctx.inputs.get("video")
        source_url = ctx.params.get("source_url", "")
        song = ctx.params.get("song")

        if not (speech and music and clusters_meta):
            raise StageError("missing inputs for finalize", retriable=False)

        clusters = json.loads(clusters_meta.read_text())
        sfx_entries = []
        for c in clusters:
            rel = c["representative_path"]
            abs_p = ctx.job_dir / rel
            sfx_entries.append({
                "path": rel,
                "duration": _duration(abs_p),
                "repeats": c["count"],
                "onset_times": c["onset_times_s"],
            })

        manifest = {
            "job_id": ctx.job_id,
            "source_url": source_url,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "duration_seconds": _duration(speech) if speech else 0.0,
            "assets": {
                "video": {"path": "source.mp4", "duration": _duration(video) if video else 0.0},
                "speech": {"path": "speech.wav", "duration": _duration(speech)},
                "music": {
                    "path": "music.wav",
                    "duration": _duration(music),
                    **({"song": song} if song else {}),
                },
                "sfx": sfx_entries,
            },
        }

        out = ctx.job_dir / "metadata.json"
        out.write_text(json.dumps(manifest, indent=2))
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0))
        return StageResult(artifacts={"manifest": Path("metadata.json")}, extra={"manifest": manifest})
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/test_stage_finalize.py -v`
Expected: 1 test PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/pipeline/finalize.py backend/tests/test_stage_finalize.py
git commit -m "feat(pipeline): add finalize stage (AssetManifest writer)"
```

---

### Task 14: Orchestrator

**Files:**
- Create: `backend/app/pipeline/orchestrator.py`
- Create: `backend/app/pipeline/cli.py`
- Create: `backend/tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_orchestrator.py
from pathlib import Path
import pytest
from app.pipeline.base import JobContext, StageResult, Stage, StageEvent
from app.pipeline.orchestrator import Orchestrator
from app.core.errors import StageError

class FakeStage:
    def __init__(self, name: str, artifacts: dict, fail: bool = False, retriable: bool = True):
        self.name = name
        self._artifacts = artifacts
        self._fail = fail
        self._retriable = retriable

    def run(self, ctx: JobContext) -> StageResult:
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.5))
        if self._fail:
            raise StageError(f"{self.name} boom", retriable=self._retriable)
        return StageResult(artifacts={k: Path(v) for k, v in self._artifacts.items()})

def test_orchestrator_runs_stages_in_order(tmp_path: Path):
    events = []
    orch = Orchestrator(
        stages=[
            FakeStage("download", {"video": "source.mp4"}),
            FakeStage("audio", {"audio": "audio.wav"}),
        ],
        emit=lambda e: events.append(e),
    )
    (tmp_path / "source.mp4").write_bytes(b"x")
    (tmp_path / "audio.wav").write_bytes(b"x")
    result = orch.run(job_id="j1", job_dir=tmp_path, params={})
    # Events should show both stage.start and stage.done for each
    types = [(e["type"], e["stage"]) for e in events]
    assert ("stage.start", "download") in types
    assert ("stage.done", "download") in types
    assert ("stage.start", "audio") in types
    assert ("stage.done", "audio") in types
    assert result["success"]

def test_orchestrator_passes_artifacts_between_stages(tmp_path: Path):
    observed_inputs = {}
    class RecordingStage:
        name = "audio"
        def run(self, ctx):
            observed_inputs.update(ctx.inputs)
            return StageResult()
    (tmp_path / "source.mp4").write_bytes(b"x")
    orch = Orchestrator(stages=[FakeStage("download", {"video": "source.mp4"}), RecordingStage()])
    orch.run(job_id="j1", job_dir=tmp_path, params={})
    assert "video" in observed_inputs
    assert observed_inputs["video"] == tmp_path / "source.mp4"

def test_orchestrator_stops_on_stage_error_and_emits_job_error(tmp_path: Path):
    events = []
    orch = Orchestrator(
        stages=[FakeStage("download", {}, fail=True, retriable=True), FakeStage("audio", {})],
        emit=lambda e: events.append(e),
    )
    result = orch.run(job_id="j1", job_dir=tmp_path, params={})
    assert not result["success"]
    assert any(e["type"] == "stage.error" and e["stage"] == "download" for e in events)
    assert not any(e["stage"] == "audio" for e in events)

def test_orchestrator_can_be_canceled(tmp_path: Path):
    from threading import Event
    cancel = Event()
    class SlowStage:
        name = "download"
        def run(self, ctx):
            cancel.wait(timeout=0.5)  # block briefly
            return StageResult()
    events = []
    orch = Orchestrator(stages=[SlowStage()], emit=lambda e: events.append(e), cancel_event=cancel)
    cancel.set()
    result = orch.run(job_id="j1", job_dir=tmp_path, params={})
    # Should have emitted job.canceled or job.error
    assert any(e["type"] in ("job.canceled", "job.error") for e in events)
```

- [ ] **Step 2: Implement Orchestrator**

```python
# backend/app/pipeline/orchestrator.py
from __future__ import annotations
from pathlib import Path
from threading import Event
from typing import Callable, Any
from app.pipeline.base import Stage, JobContext, StageEvent
from app.core.errors import StageError

Emit = Callable[[dict[str, Any]], None]

class Orchestrator:
    def __init__(
        self,
        stages: list[Stage],
        emit: Emit | None = None,
        cancel_event: Event | None = None,
    ):
        self.stages = stages
        self.emit = emit or (lambda _e: None)
        self.cancel_event = cancel_event

    def run(self, job_id: str, job_dir: Path, params: dict) -> dict:
        inputs: dict[str, Path] = {}
        shared_params: dict[str, Any] = dict(params)  # stages can read source_url, song, etc.

        def _stage_emit(event: StageEvent):
            self.emit({
                "type": "stage.progress",
                "stage": event.stage,
                "progress": event.progress,
                "message": event.message,
            })

        for stage in self.stages:
            if self.cancel_event and self.cancel_event.is_set():
                self.emit({"type": "job.canceled"})
                return {"success": False, "canceled": True}

            self.emit({"type": "stage.start", "stage": stage.name})

            ctx = JobContext(
                job_id=job_id,
                job_dir=job_dir,
                inputs={**inputs},
                params={**shared_params},
                emit=_stage_emit,
            )

            try:
                result = stage.run(ctx)
            except StageError as e:
                self.emit({
                    "type": "stage.error",
                    "stage": stage.name,
                    "message": e.message,
                    "retriable": e.retriable,
                })
                self.emit({"type": "job.error", "stage": stage.name, "message": e.message})
                return {"success": False, "stage": stage.name, "error": e.message}

            # Convert relative artifact paths to absolute paths, add to inputs
            for name, rel_path in result.artifacts.items():
                inputs[name] = job_dir / rel_path

            # Propagate stage extras into shared params so later stages can use them
            for key, value in result.extra.items():
                shared_params[key] = value

            self.emit({
                "type": "stage.done",
                "stage": stage.name,
                "artifacts": {name: str(p) for name, p in result.artifacts.items()},
            })

        self.emit({"type": "job.done", "manifest": shared_params.get("manifest", {})})
        return {"success": True}
```

- [ ] **Step 3: Create CLI entry point**

```python
# backend/app/pipeline/cli.py
"""CLI entry so the pipeline can be exercised without the API/UI.

Usage:
    python -m app.pipeline.cli <url> [--output-dir PATH] [--device cpu|mps]
"""
from __future__ import annotations
import argparse
import json
import uuid
from pathlib import Path
from app.pipeline.orchestrator import Orchestrator
from app.pipeline.download import DownloadStage
from app.pipeline.audio import AudioStage
from app.pipeline.speech import SpeechStage
from app.pipeline.sfx import SfxStage
from app.pipeline.music import MusicStage
from app.pipeline.finalize import FinalizeStage
from app.storage.asset_storage import LocalAssetStorage

def build_default_stages() -> list:
    return [
        DownloadStage(),
        AudioStage(),
        SpeechStage(),
        SfxStage(),
        MusicStage(),
        FinalizeStage(),
    ]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--output-dir", default="./outputs")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--model", default="htdemucs_ft")
    args = ap.parse_args()

    storage = LocalAssetStorage(Path(args.output_dir))
    job_id = uuid.uuid4().hex[:12]
    job_dir = storage.create_job_dir(job_id=job_id, slug="cli")

    def emit(event):
        print(json.dumps(event))

    orch = Orchestrator(stages=build_default_stages(), emit=emit)
    result = orch.run(
        job_id=job_id,
        job_dir=job_dir,
        params={
            "url": args.url,
            "device": args.device,
            "model": args.model,
            "min_cluster_size": 2,
            "clip_min_ms": 300,
            "clip_max_ms": 1500,
            "source_url": args.url,
        },
    )
    print(json.dumps({"final": result}))

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_orchestrator.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/orchestrator.py backend/app/pipeline/cli.py backend/tests/test_orchestrator.py
git commit -m "feat(pipeline): add orchestrator and CLI entry"
```

**Checkpoint:** Phase 1 complete. You now have a CLI-testable pipeline. Sanity-check with a real URL (takes ~30-60s):
```bash
cd backend && uv run python -m app.pipeline.cli "https://www.youtube.com/shorts/<id>" --output-dir ../outputs --device mps
```
The output directory should contain `source.mp4`, `audio.wav`, `speech.wav`, `non_speech.wav`, `music.wav`, `sfx/`, `sfx_clusters.json`, `metadata.json`.

---

## Phase 2 — Backend API (Tasks 15-18)

Phase 2 wraps the pipeline in HTTP routes + WebSocket so the frontend has something to call. By end of Task 18 you can drive the pipeline from curl/wscat without a UI.

---

### Task 15: Config endpoints (GET/PUT /api/config)

**Files:**
- Create: `backend/app/api/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/deps.py`
- Create: `backend/tests/test_api_config.py`

- [ ] **Step 1: Create dependency injection seams**

```python
# backend/app/deps.py
"""FastAPI dependency providers. Replace these in tests to swap impls."""
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from app.storage.config_store import FileConfigStore
from app.storage.job_store import InMemoryJobStore
from app.storage.asset_storage import LocalAssetStorage
from app.ws.event_bus import EventBus
from app.core.user_context import DefaultUserContext

CONFIG_PATH = Path("~/.extract-assets/config.json").expanduser()

@lru_cache(maxsize=1)
def get_config_store() -> FileConfigStore:
    return FileConfigStore(CONFIG_PATH)

@lru_cache(maxsize=1)
def get_job_store() -> InMemoryJobStore:
    return InMemoryJobStore()

@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    return EventBus()

def get_asset_storage() -> LocalAssetStorage:
    cfg = get_config_store().load()
    return LocalAssetStorage(Path(cfg.output_base_dir).expanduser())

def get_user_context() -> DefaultUserContext:
    return DefaultUserContext()
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_api_config.py
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app import deps
from app.storage.config_store import FileConfigStore

def _override(tmp_path: Path):
    store = FileConfigStore(tmp_path / "cfg.json")
    app.dependency_overrides[deps.get_config_store] = lambda: store
    return store

def test_get_config_returns_defaults(tmp_path: Path):
    _override(tmp_path)
    client = TestClient(app)
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["demucs_model"] == "htdemucs_ft"
    assert body["sfx_min_cluster_size"] == 2
    app.dependency_overrides.clear()

def test_put_config_updates_fields(tmp_path: Path):
    _override(tmp_path)
    client = TestClient(app)
    resp = client.put("/api/config", json={"demucs_device": "cpu"})
    assert resp.status_code == 200
    assert resp.json()["demucs_device"] == "cpu"
    # persist check
    resp2 = client.get("/api/config")
    assert resp2.json()["demucs_device"] == "cpu"
    app.dependency_overrides.clear()

def test_put_config_ignores_unknown_fields(tmp_path: Path):
    _override(tmp_path)
    client = TestClient(app)
    resp = client.put("/api/config", json={"bogus": "x", "demucs_model": "htdemucs"})
    assert resp.status_code == 200
    body = resp.json()
    assert "bogus" not in body
    assert body["demucs_model"] == "htdemucs"
    app.dependency_overrides.clear()
```

- [ ] **Step 3: Implement config router**

```python
# backend/app/api/config.py
from fastapi import APIRouter, Depends
from dataclasses import asdict
from app.deps import get_config_store
from app.storage.config_store import FileConfigStore

router = APIRouter(prefix="/api/config", tags=["config"])

@router.get("")
def get_config(store: FileConfigStore = Depends(get_config_store)):
    return asdict(store.load())

@router.put("")
def put_config(patch: dict, store: FileConfigStore = Depends(get_config_store)):
    cfg = store.update(patch)
    return asdict(cfg)
```

- [ ] **Step 4: Mount in main.py**

```python
# backend/app/main.py — replace existing file
from fastapi import FastAPI
from app.api import health, config

def create_app() -> FastAPI:
    app = FastAPI(title="ExtractAssets")
    app.include_router(health.router)
    app.include_router(config.router)
    return app

app = create_app()
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_api_config.py -v`
Expected: 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/config.py backend/app/main.py backend/app/deps.py backend/tests/test_api_config.py
git commit -m "feat(api): add config endpoints"
```

---

### Task 16: Jobs endpoints (POST /api/jobs, GET current, POST cancel)

**Files:**
- Create: `backend/app/api/jobs.py`
- Create: `backend/app/jobs/__init__.py`
- Create: `backend/app/jobs/runner.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_jobs.py`

- [ ] **Step 1: Create JobRunner (wires orchestrator to background task)**

```python
# backend/app/jobs/runner.py
from __future__ import annotations
import asyncio
import threading
from pathlib import Path
from app.pipeline.cli import build_default_stages
from app.pipeline.orchestrator import Orchestrator
from app.storage.job_store import InMemoryJobStore, JobStatus
from app.ws.event_bus import EventBus
from app.storage.config_store import FileConfigStore

class JobRunner:
    """
    Runs a pipeline in a background thread and bridges its sync `emit` callback
    back into the FastAPI asyncio event loop via run_coroutine_threadsafe.

    The event loop MUST be passed in (captured by the caller via
    asyncio.get_running_loop()). Do not try to grab the loop inside this thread —
    threads don't have a default running loop.
    """
    # Module-level registries so cancel() works across requests with a fresh
    # JobRunner instance (cheap, keyed by job_id).
    _cancel_events: dict[str, threading.Event] = {}
    _threads: dict[str, threading.Thread] = {}

    def __init__(
        self,
        job_store: InMemoryJobStore,
        event_bus: EventBus,
        config_store: FileConfigStore,
        loop: asyncio.AbstractEventLoop,
    ):
        self.jobs = job_store
        self.bus = event_bus
        self.config = config_store
        self.loop = loop

    def start(self, job_id: str, url: str, job_dir: Path) -> None:
        cancel_event = threading.Event()
        JobRunner._cancel_events[job_id] = cancel_event
        loop = self.loop

        def emit(event: dict):
            # thread-safe publish back into asyncio loop owned by FastAPI
            asyncio.run_coroutine_threadsafe(self.bus.publish(job_id, event), loop)
            # update job status on key events
            if event.get("type") == "stage.start":
                self.jobs.set_current_stage(job_id, event["stage"])
                self.jobs.set_status(job_id, JobStatus.RUNNING)
            elif event.get("type") == "job.done":
                self.jobs.set_status(job_id, JobStatus.DONE)
            elif event.get("type") == "job.error":
                self.jobs.set_status(job_id, JobStatus.ERROR, error=event.get("message"))
            elif event.get("type") == "job.canceled":
                self.jobs.set_status(job_id, JobStatus.CANCELED)

        cfg = self.config.load()

        def _run():
            orch = Orchestrator(
                stages=build_default_stages(),
                emit=emit,
                cancel_event=cancel_event,
            )
            orch.run(
                job_id=job_id,
                job_dir=job_dir,
                params={
                    "url": url,
                    "source_url": url,
                    "device": cfg.demucs_device,
                    "model": cfg.demucs_model,
                    "min_cluster_size": cfg.sfx_min_cluster_size,
                    "clip_min_ms": cfg.sfx_clip_min_ms,
                    "clip_max_ms": cfg.sfx_clip_max_ms,
                },
            )

        t = threading.Thread(target=_run, daemon=True)
        JobRunner._threads[job_id] = t
        t.start()

    @classmethod
    def cancel(cls, job_id: str) -> bool:
        ev = cls._cancel_events.get(job_id)
        if ev:
            ev.set()
            return True
        return False
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_api_jobs.py
from pathlib import Path
from fastapi.testclient import TestClient
from app import deps
from app.main import app
from app.storage.config_store import FileConfigStore
from app.storage.job_store import InMemoryJobStore
from app.ws.event_bus import EventBus
from app.storage.asset_storage import LocalAssetStorage

def _setup(tmp_path: Path):
    cfg_store = FileConfigStore(tmp_path / "cfg.json")
    cfg_store.update({"output_base_dir": str(tmp_path / "outs")})
    job_store = InMemoryJobStore()
    bus = EventBus()
    asset_storage = LocalAssetStorage(tmp_path / "outs")
    app.dependency_overrides[deps.get_config_store] = lambda: cfg_store
    app.dependency_overrides[deps.get_job_store] = lambda: job_store
    app.dependency_overrides[deps.get_event_bus] = lambda: bus
    app.dependency_overrides[deps.get_asset_storage] = lambda: asset_storage
    return job_store

def _teardown():
    app.dependency_overrides.clear()

def test_post_jobs_returns_job_id_and_creates_dir(tmp_path: Path, monkeypatch):
    # Prevent the runner from actually running the pipeline in this test.
    from app.api import jobs
    monkeypatch.setattr(jobs, "_run_pipeline_async", lambda *a, **k: None)
    _setup(tmp_path)
    client = TestClient(app)
    resp = client.post("/api/jobs", json={"url": "https://example.com/reel/1"})
    assert resp.status_code == 201
    body = resp.json()
    assert "job_id" in body
    assert "job_dir" in body
    _teardown()

def test_post_jobs_409_when_one_running(tmp_path: Path, monkeypatch):
    from app.api import jobs
    monkeypatch.setattr(jobs, "_run_pipeline_async", lambda *a, **k: None)
    _setup(tmp_path)
    client = TestClient(app)
    client.post("/api/jobs", json={"url": "https://example.com/reel/1"})
    resp = client.post("/api/jobs", json={"url": "https://example.com/reel/2"})
    assert resp.status_code == 409
    _teardown()

def test_get_current_returns_active_job(tmp_path: Path, monkeypatch):
    from app.api import jobs
    monkeypatch.setattr(jobs, "_run_pipeline_async", lambda *a, **k: None)
    _setup(tmp_path)
    client = TestClient(app)
    client.post("/api/jobs", json={"url": "https://example.com/reel/1"})
    resp = client.get("/api/jobs/current")
    assert resp.status_code == 200
    _teardown()

def test_get_current_404_when_none(tmp_path: Path):
    _setup(tmp_path)
    client = TestClient(app)
    resp = client.get("/api/jobs/current")
    assert resp.status_code == 404
    _teardown()
```

- [ ] **Step 3: Implement jobs router**

```python
# backend/app/api/jobs.py
from __future__ import annotations
import asyncio
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import get_job_store, get_event_bus, get_asset_storage, get_config_store
from app.storage.job_store import InMemoryJobStore
from app.storage.asset_storage import LocalAssetStorage
from app.ws.event_bus import EventBus
from app.storage.config_store import FileConfigStore
from app.jobs.runner import JobRunner

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

class CreateJobRequest(BaseModel):
    url: str

def _run_pipeline_async(
    job_id: str, url: str, job_dir: Path,
    jobs: InMemoryJobStore, bus: EventBus, config: FileConfigStore,
    loop: asyncio.AbstractEventLoop,
):
    """Indirection that tests can monkeypatch to no-op."""
    JobRunner(jobs, bus, config, loop).start(job_id, url, job_dir)

@router.post("", status_code=201)
async def create_job(
    req: CreateJobRequest,
    jobs: InMemoryJobStore = Depends(get_job_store),
    bus: EventBus = Depends(get_event_bus),
    storage: LocalAssetStorage = Depends(get_asset_storage),
    config: FileConfigStore = Depends(get_config_store),
):
    if jobs.get_current() is not None:
        raise HTTPException(409, "a job is already running")
    loop = asyncio.get_running_loop()  # capture FastAPI's event loop
    state = jobs.create(url=req.url, job_dir="(pending)")
    job_dir = storage.create_job_dir(job_id=state.job_id, slug=_slug_from_url(req.url))
    state.job_dir = str(job_dir)
    _run_pipeline_async(state.job_id, req.url, job_dir, jobs, bus, config, loop)
    return {"job_id": state.job_id, "job_dir": str(job_dir)}

@router.get("/current")
def get_current(jobs: InMemoryJobStore = Depends(get_job_store)):
    state = jobs.get_current()
    if state is None:
        raise HTTPException(404, "no active job")
    return {
        "job_id": state.job_id,
        "url": state.url,
        "status": state.status.value,
        "current_stage": state.current_stage,
        "job_dir": state.job_dir,
    }

@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, jobs: InMemoryJobStore = Depends(get_job_store)):
    if jobs.get(job_id) is None:
        raise HTTPException(404, "job not found")
    ok = JobRunner.cancel(job_id)
    return {"ok": ok}

def _slug_from_url(url: str) -> str:
    seg = url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^a-zA-Z0-9]+", "-", seg.lower())[:40] or "job"
```

- [ ] **Step 4: Mount in main.py**

```python
# backend/app/main.py — replace
from fastapi import FastAPI
from app.api import health, config, jobs

def create_app() -> FastAPI:
    app = FastAPI(title="ExtractAssets")
    app.include_router(health.router)
    app.include_router(config.router)
    app.include_router(jobs.router)
    return app

app = create_app()
```

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_api_jobs.py -v`
Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/jobs.py backend/app/jobs backend/app/main.py backend/tests/test_api_jobs.py
git commit -m "feat(api): add jobs endpoints (create/current/cancel)"
```

---

### Task 17: Assets streaming + log endpoints

**Files:**
- Create: `backend/app/api/assets.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_assets.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_api_assets.py
from pathlib import Path
from fastapi.testclient import TestClient
from app import deps
from app.main import app
from app.storage.asset_storage import LocalAssetStorage

def _setup(tmp_path: Path) -> Path:
    storage = LocalAssetStorage(tmp_path / "outs")
    job_dir = storage.create_job_dir(job_id="abc123", slug="x")
    app.dependency_overrides[deps.get_asset_storage] = lambda: storage
    return job_dir

def test_stream_asset_returns_file(tmp_path: Path):
    job_dir = _setup(tmp_path)
    (job_dir / "speech.wav").write_bytes(b"FAKEWAV")
    client = TestClient(app)
    resp = client.get(f"/api/assets/{job_dir.name}/speech.wav")
    assert resp.status_code == 200
    assert resp.content == b"FAKEWAV"
    app.dependency_overrides.clear()

def test_stream_asset_nested_path(tmp_path: Path):
    job_dir = _setup(tmp_path)
    (job_dir / "sfx").mkdir()
    (job_dir / "sfx" / "sfx_01.wav").write_bytes(b"SFX")
    client = TestClient(app)
    resp = client.get(f"/api/assets/{job_dir.name}/sfx/sfx_01.wav")
    assert resp.status_code == 200
    assert resp.content == b"SFX"
    app.dependency_overrides.clear()

def test_stream_asset_rejects_traversal(tmp_path: Path):
    job_dir = _setup(tmp_path)
    client = TestClient(app)
    resp = client.get(f"/api/assets/{job_dir.name}/../etc/passwd")
    assert resp.status_code in (400, 404)
    app.dependency_overrides.clear()

def test_stream_asset_missing_job(tmp_path: Path):
    _setup(tmp_path)
    client = TestClient(app)
    resp = client.get("/api/assets/nope/any.wav")
    assert resp.status_code == 404
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Implement assets router**

```python
# backend/app/api/assets.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.deps import get_asset_storage
from app.storage.asset_storage import LocalAssetStorage, AssetNotFound, PathTraversal

router = APIRouter(prefix="/api/assets", tags=["assets"])

@router.get("/{job_dir_name}/{path:path}")
def stream_asset(
    job_dir_name: str,
    path: str,
    storage: LocalAssetStorage = Depends(get_asset_storage),
):
    try:
        p = storage.resolve(job_dir_name, path)
    except PathTraversal:
        raise HTTPException(400, "invalid path")
    except AssetNotFound:
        raise HTTPException(404, "job not found")
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "asset not found")
    return FileResponse(p)
```

- [ ] **Step 3: Mount in main.py**

```python
# backend/app/main.py — add line
from app.api import assets
# inside create_app(), after existing includes:
    app.include_router(assets.router)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_api_assets.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/assets.py backend/app/main.py backend/tests/test_api_assets.py
git commit -m "feat(api): add asset streaming endpoint with path traversal guard"
```

---

### Task 18: WebSocket /api/jobs/{id}/events

**Files:**
- Create: `backend/app/api/ws.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_ws.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_api_ws.py
import asyncio
from fastapi.testclient import TestClient
from app import deps
from app.main import app
from app.ws.event_bus import EventBus

def test_ws_replay_on_connect():
    """
    End-to-end check that the WS endpoint accepts a connection and sends the
    replay frame containing previously-buffered events. Live streaming across
    the test-thread / app-thread boundary is not covered here because EventBus
    queues are bound to the loop that created them; asyncio.Queue does not
    cross loops cleanly. Live streaming is exercised by Task 5's EventBus unit
    tests within a single loop, and by the end-to-end run in Task 27.
    """
    bus = EventBus()

    # Pre-populate the replay buffer. Run publish on a temporary loop — the
    # buffer is a plain deque, so events survive loop disposal.
    async def seed():
        await bus.publish("j1", {"type": "stage.start", "stage": "download"})
        await bus.publish("j1", {"type": "stage.progress", "stage": "download", "progress": 0.5})
    asyncio.new_event_loop().run_until_complete(seed())

    app.dependency_overrides[deps.get_event_bus] = lambda: bus
    try:
        with TestClient(app) as client:
            with client.websocket_connect("/api/jobs/j1/events") as ws:
                first = ws.receive_json()
                assert first["type"] == "replay"
                assert len(first["events"]) == 2
                assert first["events"][0]["stage"] == "download"
    finally:
        app.dependency_overrides.clear()

def test_ws_replay_empty_when_no_events():
    bus = EventBus()
    app.dependency_overrides[deps.get_event_bus] = lambda: bus
    try:
        with TestClient(app) as client:
            with client.websocket_connect("/api/jobs/never/events") as ws:
                first = ws.receive_json()
                assert first["type"] == "replay"
                assert first["events"] == []
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Implement WebSocket endpoint**

```python
# backend/app/api/ws.py
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.deps import get_event_bus
from app.ws.event_bus import EventBus

router = APIRouter()

@router.websocket("/api/jobs/{job_id}/events")
async def job_events(ws: WebSocket, job_id: str, bus: EventBus = Depends(get_event_bus)):
    await ws.accept()
    # Replay first
    await ws.send_json({"type": "replay", "events": bus.replay(job_id)})
    # Then stream live
    queue = bus.subscribe(job_id)
    try:
        while True:
            event = await queue.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(job_id, queue)
```

- [ ] **Step 3: Mount in main.py**

```python
# backend/app/main.py — add to imports and include
from app.api import ws
# inside create_app():
    app.include_router(ws.router)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_api_ws.py -v`
Expected: 2 tests PASS (both replay-frame tests). Live event streaming across the test-thread / app-thread boundary is deliberately not tested here — see comment at the top of the file. Task 5's EventBus tests cover live streaming within a single loop, and Task 27's e2e test covers the full pipeline emitting through the real uvicorn loop.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/ws.py backend/app/main.py backend/tests/test_api_ws.py
git commit -m "feat(api): add WebSocket endpoint for job events"
```

**Checkpoint:** Phase 2 complete. Backend API is fully functional. Smoke test manually:
```bash
cd backend && uv run uvicorn app.main:app --port 8000
# in another terminal:
curl -X POST http://localhost:8000/api/jobs -H "Content-Type: application/json" -d '{"url":"https://www.youtube.com/shorts/<id>"}'
# then tail with: wscat -c ws://localhost:8000/api/jobs/<job_id>/events
```

---

## Phase 3 — Frontend (Tasks 19-26)

Phase 3 builds the React SPA matching the approved mockup (split workspace, cards with waveforms). No component tests in MVP per spec — verification by hand against the running backend.

---

### Task 19: Frontend scaffolding (Vite + React + Tailwind + deps)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/styles/tokens.css`

- [ ] **Step 1: Initialize the project**

Run:
```bash
cd frontend
pnpm init -y
pnpm add react@18 react-dom@18 zustand wavesurfer.js framer-motion
pnpm add -D typescript @types/react @types/react-dom vite @vitejs/plugin-react tailwindcss postcss autoprefixer
```

- [ ] **Step 2: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true, ws: true },
    },
  },
  build: { outDir: '../backend/app/static', emptyOutDir: true },
});
```

- [ ] **Step 3: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noFallthroughCasesInSwitch": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "allowSyntheticDefaultImports": true,
    "skipLibCheck": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `frontend/tailwind.config.ts` + postcss**

```ts
// frontend/tailwind.config.ts
import type { Config } from 'tailwindcss';
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0a0b',
        surface: '#141416',
        'surface-2': '#1c1c1f',
        'surface-3': '#232327',
        border: '#26262a',
        'border-soft': '#1f1f23',
        text: '#f2f2f3',
        'text-dim': '#9a9aa0',
        'text-mute': '#5e5e64',
        accent: '#7c83ff',
        good: '#4ade80',
        speech: '#60a5fa',
        music: '#fbbf24',
        sfx: '#f472b6',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Menlo', 'monospace'],
      },
      letterSpacing: { tight: '-0.01em', tighter: '-0.025em' },
    },
  },
} satisfies Config;
```

```js
// frontend/postcss.config.js
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 5: Create HTML + CSS entry**

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ExtractAssets</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
</head>
<body class="bg-bg text-text">
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

```css
/* frontend/src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html, body { @apply antialiased; letter-spacing: -0.01em; font-feature-settings: 'cv11', 'ss01'; }
  body { font-family: 'Inter', system-ui, sans-serif; }
}
```

- [ ] **Step 6: Create skeleton App**

```tsx
// frontend/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(<App />);
```

```tsx
// frontend/src/App.tsx
export default function App() {
  return (
    <div className="min-h-screen grid grid-cols-[320px_1fr]">
      <aside className="border-r border-border bg-surface p-6">LeftPanel</aside>
      <main className="p-6">RightPanel</main>
    </div>
  );
}
```

- [ ] **Step 7: Run dev server smoke check**

Run: `cd frontend && pnpm exec vite --port 5173`
Expected: opens on http://localhost:5173, shows "LeftPanel | RightPanel" on the dark background.

Stop server with Ctrl+C.

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vite + React + Tailwind with dark palette"
```

---

### Task 20: Frontend API client + WS hook + Zustand store

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/ws.ts`
- Create: `frontend/src/lib/format.ts`
- Create: `frontend/src/hooks/useJobStore.ts`
- Create: `frontend/src/hooks/useJobSocket.ts`
- Create: `frontend/src/hooks/useConfig.ts`

- [ ] **Step 1: Create API client**

```ts
// frontend/src/lib/api.ts
export type StageName = 'download' | 'audio' | 'speech' | 'sfx' | 'music' | 'finalize';

export interface Config {
  output_base_dir: string;
  demucs_model: string;
  demucs_device: 'mps' | 'cpu';
  sfx_min_cluster_size: number;
  sfx_clip_min_ms: number;
  sfx_clip_max_ms: number;
}

export interface Manifest {
  job_id: string;
  source_url: string;
  created_at: string;
  duration_seconds: number;
  assets: {
    video: { path: string; duration: number };
    speech: { path: string; duration: number };
    music: { path: string; duration: number; song?: { title: string; artist?: string; source: string } };
    sfx: Array<{ path: string; duration: number; repeats: number; onset_times: number[] }>;
  };
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const api = {
  health: () => req<{ ok: boolean }>('/api/health'),
  getConfig: () => req<Config>('/api/config'),
  putConfig: (patch: Partial<Config>) =>
    req<Config>('/api/config', { method: 'PUT', body: JSON.stringify(patch) }),
  createJob: (url: string) =>
    req<{ job_id: string; job_dir: string }>('/api/jobs', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }),
  getCurrentJob: () => req<any>('/api/jobs/current'),
  cancelJob: (job_id: string) =>
    req<{ ok: boolean }>(`/api/jobs/${job_id}/cancel`, { method: 'POST' }),
  assetUrl: (job_dir_name: string, relpath: string) =>
    `/api/assets/${encodeURIComponent(job_dir_name)}/${relpath.split('/').map(encodeURIComponent).join('/')}`,
};
```

- [ ] **Step 2: Create WS helper**

```ts
// frontend/src/lib/ws.ts
export type WsEvent =
  | { type: 'replay'; events: WsEvent[] }
  | { type: 'stage.start'; stage: string }
  | { type: 'stage.progress'; stage: string; progress?: number; message?: string }
  | { type: 'stage.done'; stage: string; artifacts: Record<string, string> }
  | { type: 'stage.error'; stage: string; message: string; retriable: boolean }
  | { type: 'job.done'; manifest: any }
  | { type: 'job.error'; stage: string; message: string }
  | { type: 'job.canceled' };

export function openJobSocket(jobId: string, onEvent: (e: WsEvent) => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/api/jobs/${jobId}/events`);
  ws.onmessage = (ev) => {
    try { onEvent(JSON.parse(ev.data) as WsEvent); }
    catch (e) { console.error('bad ws frame', e); }
  };
  return ws;
}
```

- [ ] **Step 3: Create format helpers**

```ts
// frontend/src/lib/format.ts
export function fmtDuration(seconds: number): string {
  if (!isFinite(seconds)) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function fmtDurationPrecise(seconds: number): string {
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  return fmtDuration(seconds);
}
```

- [ ] **Step 4: Create Zustand store**

```ts
// frontend/src/hooks/useJobStore.ts
import { create } from 'zustand';
import type { Manifest, StageName } from '@/lib/api';

type Status = 'idle' | 'running' | 'done' | 'error' | 'canceled';
type StageStatus = 'pending' | 'running' | 'done' | 'error';

export interface StageState {
  status: StageStatus;
  progress: number;
  message?: string;
  errorMessage?: string;
  retriable?: boolean;
  artifacts?: Record<string, string>;
}

interface JobSliceState {
  jobId: string | null;
  jobDirName: string | null;
  status: Status;
  stages: Record<StageName, StageState>;
  manifest: Manifest | null;
  error: { stage: StageName; message: string } | null;
}

interface JobStore extends JobSliceState {
  startJob: (jobId: string, jobDirName: string) => void;
  applyEvent: (e: any) => void;
  reset: () => void;
}

const initialStages = (): Record<StageName, StageState> => ({
  download: { status: 'pending', progress: 0 },
  audio: { status: 'pending', progress: 0 },
  speech: { status: 'pending', progress: 0 },
  sfx: { status: 'pending', progress: 0 },
  music: { status: 'pending', progress: 0 },
  finalize: { status: 'pending', progress: 0 },
});

export const useJobStore = create<JobStore>((set, get) => ({
  jobId: null, jobDirName: null, status: 'idle',
  stages: initialStages(), manifest: null, error: null,

  startJob: (jobId, jobDirName) =>
    set({ jobId, jobDirName, status: 'running', stages: initialStages(), manifest: null, error: null }),

  applyEvent: (e) => {
    const s = get().stages;
    switch (e.type) {
      case 'replay':
        (e.events as any[]).forEach((sub) => get().applyEvent(sub));
        break;
      case 'stage.start':
        set({ stages: { ...s, [e.stage]: { ...s[e.stage as StageName], status: 'running' } } });
        break;
      case 'stage.progress':
        set({ stages: {
          ...s,
          [e.stage]: { ...s[e.stage as StageName], status: 'running', progress: e.progress ?? s[e.stage as StageName].progress, message: e.message },
        }});
        break;
      case 'stage.done':
        set({ stages: {
          ...s,
          [e.stage]: { ...s[e.stage as StageName], status: 'done', progress: 1, artifacts: e.artifacts },
        }});
        break;
      case 'stage.error':
        set({ stages: {
          ...s,
          [e.stage]: { ...s[e.stage as StageName], status: 'error', errorMessage: e.message, retriable: e.retriable },
        }});
        break;
      case 'job.done':
        set({ status: 'done', manifest: e.manifest });
        break;
      case 'job.error':
        set({ status: 'error', error: { stage: e.stage, message: e.message } });
        break;
      case 'job.canceled':
        set({ status: 'canceled' });
        break;
    }
  },

  reset: () => set({ jobId: null, jobDirName: null, status: 'idle', stages: initialStages(), manifest: null, error: null }),
}));
```

- [ ] **Step 5: Create useJobSocket hook**

```ts
// frontend/src/hooks/useJobSocket.ts
import { useEffect } from 'react';
import { openJobSocket } from '@/lib/ws';
import { useJobStore } from './useJobStore';

export function useJobSocket() {
  const jobId = useJobStore((s) => s.jobId);
  const applyEvent = useJobStore((s) => s.applyEvent);

  useEffect(() => {
    if (!jobId) return;
    const ws = openJobSocket(jobId, applyEvent);
    return () => ws.close();
  }, [jobId, applyEvent]);
}
```

- [ ] **Step 6: Create useConfig hook**

```ts
// frontend/src/hooks/useConfig.ts
import { useCallback, useEffect, useState } from 'react';
import { api, type Config } from '@/lib/api';

export function useConfig() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.getConfig().then(setConfig).finally(() => setLoading(false)); }, []);

  const update = useCallback(async (patch: Partial<Config>) => {
    const next = await api.putConfig(patch);
    setConfig(next);
    return next;
  }, []);

  return { config, loading, update };
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib frontend/src/hooks
git commit -m "feat(frontend): add API client, WS hook, Zustand job store, config hook"
```

---

### Task 21: LeftPanel components (UrlInput + OutputDirPicker + Settings)

**Files:**
- Create: `frontend/src/components/LeftPanel/UrlInput.tsx`
- Create: `frontend/src/components/LeftPanel/OutputDirPicker.tsx`
- Create: `frontend/src/components/LeftPanel/Settings.tsx`
- Create: `frontend/src/components/LeftPanel/index.tsx`

- [ ] **Step 1: Create UrlInput**

```tsx
// frontend/src/components/LeftPanel/UrlInput.tsx
import { useState } from 'react';
import { api } from '@/lib/api';
import { useJobStore } from '@/hooks/useJobStore';

export function UrlInput() {
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const startJob = useJobStore((s) => s.startJob);
  const status = useJobStore((s) => s.status);
  const running = status === 'running';

  async function extract() {
    setErr(null);
    setBusy(true);
    try {
      const { job_id, job_dir } = await api.createJob(url);
      const jobDirName = job_dir.split('/').pop() ?? job_id;
      startJob(job_id, jobDirName);
    } catch (e: any) {
      setErr(e.message || 'failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <label className="block text-[10px] uppercase tracking-[0.1em] text-text-mute font-semibold">URL</label>
      <input
        className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm placeholder:text-text-mute focus:border-accent outline-none transition-colors"
        placeholder="https://instagram.com/reel/..."
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        disabled={running}
      />
      <button
        className="w-full bg-accent text-white rounded-lg py-2 text-sm font-medium hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition"
        onClick={extract}
        disabled={!url || busy || running}
      >
        {busy ? 'Starting…' : running ? 'Running…' : 'Extract'}
      </button>
      {err && <div className="text-xs text-red-400 mt-1">{err}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Create OutputDirPicker**

```tsx
// frontend/src/components/LeftPanel/OutputDirPicker.tsx
import { useState } from 'react';
import { useConfig } from '@/hooks/useConfig';

export function OutputDirPicker() {
  const { config, update } = useConfig();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');

  if (!config) return null;

  async function save() {
    await update({ output_base_dir: value });
    setEditing(false);
  }

  return (
    <div className="space-y-2">
      <label className="block text-[10px] uppercase tracking-[0.1em] text-text-mute font-semibold">Output directory</label>
      {editing ? (
        <div className="space-y-2">
          <input
            className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs font-mono placeholder:text-text-mute focus:border-accent outline-none"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="~/Desktop/assets"
          />
          <div className="flex gap-2">
            <button onClick={save} className="text-xs bg-accent text-white rounded px-3 py-1">Save</button>
            <button onClick={() => setEditing(false)} className="text-xs text-text-dim">Cancel</button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between bg-surface-2 border border-border-soft rounded-lg px-3 py-2">
          <div className="text-xs font-mono text-text-dim truncate">{config.output_base_dir}</div>
          <button
            onClick={() => { setValue(config.output_base_dir); setEditing(true); }}
            className="text-[11px] text-accent hover:underline ml-2"
          >
            Change
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create Settings**

```tsx
// frontend/src/components/LeftPanel/Settings.tsx
import { useState } from 'react';
import { useConfig } from '@/hooks/useConfig';

export function Settings() {
  const { config, update } = useConfig();
  const [open, setOpen] = useState(false);
  if (!config) return null;

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left text-[10px] uppercase tracking-[0.1em] text-text-mute font-semibold flex items-center justify-between"
      >
        <span>Settings</span>
        <span>{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          <div>
            <div className="text-xs text-text-dim mb-1">Demucs device</div>
            <div className="flex gap-1 bg-surface-2 p-1 rounded-lg border border-border-soft">
              {(['mps', 'cpu'] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => update({ demucs_device: d })}
                  className={`flex-1 text-xs py-1 rounded ${config.demucs_device === d ? 'bg-accent text-white' : 'text-text-dim'}`}
                >
                  {d.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs text-text-dim mb-1">
              SFX min repeats: <span className="font-mono text-text">{config.sfx_min_cluster_size}</span>
            </div>
            <input
              type="range"
              min={2} max={5} step={1}
              value={config.sfx_min_cluster_size}
              onChange={(e) => update({ sfx_min_cluster_size: Number(e.target.value) })}
              className="w-full accent-accent"
            />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Assemble LeftPanel**

```tsx
// frontend/src/components/LeftPanel/index.tsx
import { UrlInput } from './UrlInput';
import { OutputDirPicker } from './OutputDirPicker';
import { Settings } from './Settings';

export function LeftPanel() {
  return (
    <aside className="border-r border-border bg-surface p-6 space-y-6">
      <div className="text-xs uppercase tracking-[0.1em] text-text-mute font-semibold">ExtractAssets</div>
      <UrlInput />
      <OutputDirPicker />
      <Settings />
    </aside>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/LeftPanel
git commit -m "feat(frontend): add LeftPanel (UrlInput + OutputDirPicker + Settings)"
```

---

### Task 22: StageCard + ProcessingState with stage mapping

**Files:**
- Create: `frontend/src/components/StageCard.tsx`
- Create: `frontend/src/components/RightPanel/ProcessingState.tsx`
- Create: `frontend/src/components/RightPanel/IdleState.tsx`

- [ ] **Step 1: Create StageCard**

```tsx
// frontend/src/components/StageCard.tsx
import { motion } from 'framer-motion';

export type StageCardStatus = 'pending' | 'running' | 'done' | 'error';

interface Props {
  title: string;
  status: StageCardStatus;
  progress: number; // 0..1, shown when running
  message?: string;
  errorMessage?: string;
  color: string;    // tailwind class segment, e.g. 'speech' | 'music' | 'sfx' | 'accent'
}

export function StageCard({ title, status, progress, message, errorMessage, color }: Props) {
  const borderClass =
    status === 'done' ? 'border-good/50' :
    status === 'error' ? 'border-red-500/60' :
    status === 'running' ? `border-${color}` :
    'border-border-soft';

  return (
    <motion.div
      layout
      className={`bg-surface-2 border ${borderClass} rounded-xl p-4 space-y-2`}
      transition={{ duration: 0.2 }}
    >
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{title}</div>
        <StatusDot status={status} color={color} />
      </div>
      {status === 'running' && (
        <div className="h-1 bg-surface-3 rounded overflow-hidden">
          <motion.div className={`h-full bg-${color}`} animate={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      )}
      {status === 'running' && message && <div className="text-[11px] text-text-mute">{message}</div>}
      {status === 'error' && <div className="text-[11px] text-red-400">{errorMessage}</div>}
      {status === 'done' && <div className="text-[11px] text-good">Done</div>}
    </motion.div>
  );
}

function StatusDot({ status, color }: { status: StageCardStatus; color: string }) {
  if (status === 'done') return <div className="w-2 h-2 rounded-full bg-good" />;
  if (status === 'error') return <div className="w-2 h-2 rounded-full bg-red-500" />;
  if (status === 'running') return <div className={`w-2 h-2 rounded-full bg-${color} animate-pulse`} />;
  return <div className="w-2 h-2 rounded-full bg-text-mute/40" />;
}
```

- [ ] **Step 2: Create IdleState**

```tsx
// frontend/src/components/RightPanel/IdleState.tsx
export function IdleState() {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center space-y-2">
        <div className="text-lg text-text-dim">Paste a link to start</div>
        <div className="text-xs text-text-mute">Extracted speech, SFX, and music will appear here.</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create ProcessingState with stage mapping**

```tsx
// frontend/src/components/RightPanel/ProcessingState.tsx
import { useJobStore } from '@/hooks/useJobStore';
import { StageCard, type StageCardStatus } from '@/components/StageCard';

// UI shows 4 cards; map each to 1+ pipeline stages.
const MAPPING: { ui: string; stages: Array<keyof ReturnType<typeof useJobStore.getState>['stages']>; color: string }[] = [
  { ui: 'Download',        stages: ['download', 'audio'],      color: 'accent' },
  { ui: 'Separate speech', stages: ['speech'],                 color: 'speech' },
  { ui: 'Mine SFX',        stages: ['sfx'],                    color: 'sfx' },
  { ui: 'Identify music',  stages: ['music', 'finalize'],      color: 'music' },
];

function aggregate(stages: ReturnType<typeof useJobStore.getState>['stages'], names: string[]): { status: StageCardStatus; progress: number; message?: string; errorMessage?: string } {
  const sub = names.map((n) => (stages as any)[n]);
  if (sub.some((s) => s.status === 'error')) {
    const errored = sub.find((s) => s.status === 'error');
    return { status: 'error', progress: 0, errorMessage: errored?.errorMessage };
  }
  if (sub.every((s) => s.status === 'done')) return { status: 'done', progress: 1 };
  if (sub.some((s) => s.status === 'running' || s.status === 'done')) {
    const total = sub.reduce((a, s) => a + (s.status === 'done' ? 1 : s.progress), 0) / sub.length;
    const msg = sub.find((s) => s.status === 'running')?.message;
    return { status: 'running', progress: total, message: msg };
  }
  return { status: 'pending', progress: 0 };
}

export function ProcessingState() {
  const stages = useJobStore((s) => s.stages);
  return (
    <div className="space-y-3">
      {MAPPING.map(({ ui, stages: names, color }) => {
        const agg = aggregate(stages, names);
        return <StageCard key={ui} title={ui} {...agg} color={color} />;
      })}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/StageCard.tsx frontend/src/components/RightPanel
git commit -m "feat(frontend): add StageCard with UI→pipeline mapping, IdleState, ProcessingState"
```

---

### Task 23: Waveform + AssetCard + VideoPreview

**Files:**
- Create: `frontend/src/components/Waveform.tsx`
- Create: `frontend/src/components/AssetCard.tsx`
- Create: `frontend/src/components/VideoPreview.tsx`

- [ ] **Step 1: Create Waveform wrapper**

```tsx
// frontend/src/components/Waveform.tsx
import { useEffect, useImperativeHandle, useRef, forwardRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';

export interface WaveformHandle {
  playPause: () => void;
}

interface Props {
  url: string;
  color: string;        // hex or css color
  waveColor?: string;
  height?: number;
}

export const Waveform = forwardRef<WaveformHandle, Props>(function Waveform({ url, color, waveColor, height = 44 }, ref) {
  const el = useRef<HTMLDivElement>(null);
  const ws = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!el.current) return;
    const instance = WaveSurfer.create({
      container: el.current,
      url,
      waveColor: waveColor ?? `${color}60`,
      progressColor: color,
      height,
      barWidth: 2,
      barGap: 2,
      barRadius: 1,
      cursorColor: color,
      interact: true,
    });
    instance.on('play', () => setPlaying(true));
    instance.on('pause', () => setPlaying(false));
    instance.on('finish', () => setPlaying(false));
    ws.current = instance;
    return () => { instance.destroy(); };
  }, [url, color, waveColor, height]);

  useImperativeHandle(ref, () => ({
    playPause: () => ws.current?.playPause(),
  }));

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => ws.current?.playPause()}
        className="w-9 h-9 rounded-full bg-surface-3 border border-border grid place-items-center shrink-0"
        aria-label={playing ? 'Pause' : 'Play'}
      >
        {playing ? (
          <div className="flex gap-0.5"><div className="w-1 h-3 bg-text" /><div className="w-1 h-3 bg-text" /></div>
        ) : (
          <div className="w-0 h-0 border-y-[6px] border-y-transparent border-l-[9px] border-l-text ml-[2px]" />
        )}
      </button>
      <div ref={el} className="flex-1 min-w-0" />
    </div>
  );
});
```

- [ ] **Step 2: Create AssetCard**

```tsx
// frontend/src/components/AssetCard.tsx
import type { ReactNode } from 'react';

interface Props {
  title: string;
  subtitle?: string;
  color: 'speech' | 'music' | 'sfx';
  children: ReactNode;
  pills?: Array<{ label: string; href?: string }>;
}

const dotClass = { speech: 'bg-speech', music: 'bg-music', sfx: 'bg-sfx' };

export function AssetCard({ title, subtitle, color, children, pills }: Props) {
  return (
    <div className="bg-surface-2 border border-border-soft rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium truncate">{title}</div>
          {subtitle && <div className="text-[11px] text-text-mute mt-0.5">{subtitle}</div>}
        </div>
        <div className={`w-2 h-2 rounded-full ${dotClass[color]}`} />
      </div>
      {children}
      {pills && pills.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {pills.map((p, i) => p.href ? (
            <a key={i} href={p.href} download className="bg-surface-3 border border-border rounded px-2 py-1 text-[11px] text-text-dim hover:text-text">{p.label}</a>
          ) : (
            <span key={i} className="bg-surface-3 border border-border rounded px-2 py-1 text-[11px] text-text-dim">{p.label}</span>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create VideoPreview**

```tsx
// frontend/src/components/VideoPreview.tsx
interface Props { src: string; }
export function VideoPreview({ src }: Props) {
  return (
    <div className="bg-black rounded-xl overflow-hidden border border-border-soft">
      <video src={src} controls className="w-full max-h-[360px] object-contain" />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Waveform.tsx frontend/src/components/AssetCard.tsx frontend/src/components/VideoPreview.tsx
git commit -m "feat(frontend): add Waveform (wavesurfer.js), AssetCard, VideoPreview"
```

---

### Task 24: SfxTile + SfxGrid

**Files:**
- Create: `frontend/src/components/SfxTile.tsx`
- Create: `frontend/src/components/SfxGrid.tsx`

- [ ] **Step 1: Create SfxTile**

```tsx
// frontend/src/components/SfxTile.tsx
import { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { fmtDurationPrecise } from '@/lib/format';

interface Props {
  url: string;
  repeats: number;
  duration: number;
  index: number;
}

export function SfxTile({ url, repeats, duration, index }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const ws = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!el.current) return;
    const instance = WaveSurfer.create({
      container: el.current,
      url,
      waveColor: '#f472b660',
      progressColor: '#f472b6',
      height: 28,
      barWidth: 1.5,
      barGap: 1.5,
      cursorColor: '#f472b6',
      interact: true,
    });
    instance.on('play', () => setPlaying(true));
    instance.on('pause', () => setPlaying(false));
    instance.on('finish', () => setPlaying(false));
    ws.current = instance;
    return () => { instance.destroy(); };
  }, [url]);

  return (
    <button
      onClick={() => ws.current?.playPause()}
      className="bg-surface-3 border border-border-soft rounded-xl p-3 text-left hover:border-sfx transition-colors"
    >
      <div ref={el} className="mb-2" />
      <div className="flex justify-between text-[10px] text-text-mute font-mono">
        <span>sfx_{String(index).padStart(2, '0')}</span>
        <span>×{repeats} · {fmtDurationPrecise(duration)}</span>
      </div>
      {playing && <div className="text-[10px] text-sfx mt-1">Playing…</div>}
    </button>
  );
}
```

- [ ] **Step 2: Create SfxGrid**

```tsx
// frontend/src/components/SfxGrid.tsx
import type { Manifest } from '@/lib/api';
import { api } from '@/lib/api';
import { SfxTile } from './SfxTile';

interface Props { manifest: Manifest; jobDirName: string; }

export function SfxGrid({ manifest, jobDirName }: Props) {
  const sfx = manifest.assets.sfx;
  return (
    <div className="bg-surface-2 border border-border-soft rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium">Sound effects</div>
          <div className="text-[11px] text-text-mute mt-0.5">{sfx.length} deduped · extracted by repetition mining</div>
        </div>
        <div className="w-2 h-2 rounded-full bg-sfx" />
      </div>
      {sfx.length === 0 ? (
        <div className="text-xs text-text-mute">No repeated SFX detected.</div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {sfx.map((s, i) => (
            <SfxTile
              key={s.path}
              url={api.assetUrl(jobDirName, s.path)}
              repeats={s.repeats}
              duration={s.duration}
              index={i + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SfxTile.tsx frontend/src/components/SfxGrid.tsx
git commit -m "feat(frontend): add SfxTile and SfxGrid"
```

---

### Task 25: ResultsState (full results view)

**Files:**
- Create: `frontend/src/components/RightPanel/ResultsState.tsx`
- Create: `frontend/src/components/RightPanel/index.tsx`

- [ ] **Step 1: Create ResultsState**

```tsx
// frontend/src/components/RightPanel/ResultsState.tsx
import { api, type Manifest } from '@/lib/api';
import { VideoPreview } from '@/components/VideoPreview';
import { AssetCard } from '@/components/AssetCard';
import { Waveform } from '@/components/Waveform';
import { SfxGrid } from '@/components/SfxGrid';
import { fmtDuration } from '@/lib/format';

interface Props { manifest: Manifest; jobDirName: string; }

export function ResultsState({ manifest, jobDirName }: Props) {
  const { video, speech, music } = manifest.assets;
  const videoUrl = api.assetUrl(jobDirName, video.path);
  const speechUrl = api.assetUrl(jobDirName, speech.path);
  const musicUrl = api.assetUrl(jobDirName, music.path);
  const song = music.song;

  return (
    <div className="space-y-3">
      <VideoPreview src={videoUrl} />

      <AssetCard
        title="Speech"
        subtitle={fmtDuration(speech.duration)}
        color="speech"
        pills={[{ label: 'speech.wav', href: speechUrl }]}
      >
        <Waveform url={speechUrl} color="#60a5fa" />
      </AssetCard>

      <AssetCard
        title={song ? `Music — "${song.title}"` : 'Music'}
        subtitle={song ? [song.artist, 'via yt-dlp metadata'].filter(Boolean).join(' · ') : fmtDuration(music.duration)}
        color="music"
        pills={[{ label: 'music.wav', href: musicUrl }]}
      >
        <Waveform url={musicUrl} color="#fbbf24" />
      </AssetCard>

      <SfxGrid manifest={manifest} jobDirName={jobDirName} />
    </div>
  );
}
```

- [ ] **Step 2: Create RightPanel switcher**

```tsx
// frontend/src/components/RightPanel/index.tsx
import { useJobStore } from '@/hooks/useJobStore';
import { useJobSocket } from '@/hooks/useJobSocket';
import { IdleState } from './IdleState';
import { ProcessingState } from './ProcessingState';
import { ResultsState } from './ResultsState';

export function RightPanel() {
  useJobSocket();
  const status = useJobStore((s) => s.status);
  const manifest = useJobStore((s) => s.manifest);
  const jobDirName = useJobStore((s) => s.jobDirName);
  const error = useJobStore((s) => s.error);

  return (
    <main className="p-6 overflow-auto">
      {status === 'idle' && <IdleState />}
      {(status === 'running' || status === 'error') && (
        <div className="space-y-4">
          <ProcessingState />
          {error && (
            <div className="bg-red-500/10 border border-red-500/40 rounded-xl p-4 text-sm text-red-400">
              <div className="font-medium mb-1">{error.stage} failed</div>
              <div className="text-xs">{error.message}</div>
            </div>
          )}
        </div>
      )}
      {status === 'done' && manifest && jobDirName && (
        <ResultsState manifest={manifest} jobDirName={jobDirName} />
      )}
    </main>
  );
}
```

- [ ] **Step 3: Wire into App**

```tsx
// frontend/src/App.tsx — replace
import { LeftPanel } from '@/components/LeftPanel';
import { RightPanel } from '@/components/RightPanel';

export default function App() {
  return (
    <div className="min-h-screen grid grid-cols-[320px_1fr]">
      <LeftPanel />
      <RightPanel />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/RightPanel frontend/src/App.tsx
git commit -m "feat(frontend): wire ResultsState and full Right panel state machine"
```

---

### Task 26: Production build + FastAPI static serve

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Build frontend into backend static dir**

Run:
```bash
cd frontend && pnpm build
# Outputs to ../backend/app/static/ (per vite.config.ts outDir)
```

- [ ] **Step 2: Serve static files from FastAPI**

```python
# backend/app/main.py — replace
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import health, config, jobs, assets, ws

STATIC_DIR = Path(__file__).parent / "static"

def create_app() -> FastAPI:
    app = FastAPI(title="ExtractAssets")
    app.include_router(health.router)
    app.include_router(config.router)
    app.include_router(jobs.router)
    app.include_router(assets.router)
    app.include_router(ws.router)

    if STATIC_DIR.exists():
        app.mount("/assets_static", StaticFiles(directory=STATIC_DIR / "assets"), name="assets_static")

        @app.get("/")
        def index():
            return FileResponse(STATIC_DIR / "index.html")

        @app.get("/{full_path:path}")
        def spa_catch_all(full_path: str):
            # Anything not under /api/* or /assets_static/* falls back to index.html (SPA routing).
            candidate = STATIC_DIR / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(STATIC_DIR / "index.html")

    return app

app = create_app()
```

- [ ] **Step 3: Smoke test**

Run: `cd backend && uv run uvicorn app.main:app --port 8000`
Open: `http://localhost:8000`
Expected: the React app loads, LeftPanel + RightPanel render, `GET /api/health` returns `{"ok": true}`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(backend): serve built frontend as SPA with catch-all fallback"
```

---

## Phase 4 — Integration & Run UX (Tasks 27-28)

---

### Task 27: End-to-end fixture test

**Files:**
- Create: `backend/tests/test_e2e_fixture.py`

This test exercises the full pipeline — including the *real* Demucs call — against a tiny fixture. Marked slow; run on demand. Validates that Tasks 8-14 wire together.

- [ ] **Step 1: Write the slow test**

```python
# backend/tests/test_e2e_fixture.py
import pytest
from pathlib import Path
from app.pipeline.cli import build_default_stages
from app.pipeline.orchestrator import Orchestrator

FIXTURE_URL = "https://www.youtube.com/shorts/aqz-KE-bpKQ"  # a short CC-licensed YouTube clip; replace with any public short

@pytest.mark.slow
def test_full_pipeline_on_real_url(tmp_path: Path):
    events = []
    orch = Orchestrator(stages=build_default_stages(), emit=lambda e: events.append(e))
    result = orch.run(
        job_id="e2e",
        job_dir=tmp_path,
        params={
            "url": FIXTURE_URL,
            "source_url": FIXTURE_URL,
            "device": "cpu",  # avoid MPS availability assumptions on CI/dev
            "model": "htdemucs_ft",
            "min_cluster_size": 2,
            "clip_min_ms": 300,
            "clip_max_ms": 1500,
        },
    )
    assert result["success"], f"failed at {result.get('stage')}: {result.get('error')}"
    for name in ("source.mp4", "audio.wav", "speech.wav", "non_speech.wav", "music.wav", "metadata.json", "sfx_clusters.json"):
        assert (tmp_path / name).exists(), f"missing {name}"
    assert (tmp_path / "sfx").is_dir()
```

- [ ] **Step 2: Run on demand**

Run: `cd backend && uv run pytest tests/test_e2e_fixture.py -v -m slow`
Expected: passes in 1-3 minutes. If it fails, check `pipeline.log` in the tmp dir.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_e2e_fixture.py
git commit -m "test(e2e): add end-to-end pipeline test against real short URL"
```

---

### Task 28: Run scripts (setup.sh, run.sh, dev.sh)

**Files:**
- Create: `scripts/setup.sh`
- Create: `scripts/run.sh`
- Create: `scripts/dev.sh`
- Create: `scripts/update.sh`
- Create: `README.md`

- [ ] **Step 1: Create setup.sh**

```bash
# scripts/setup.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Installing backend deps (uv)"
( cd backend && uv venv --quiet && uv pip install -e ".[dev]" )

echo "==> Installing frontend deps (pnpm)"
( cd frontend && pnpm install --silent )

echo "==> Building frontend bundle"
( cd frontend && pnpm build )

echo "==> Priming Demucs weights (~2GB, one-time)"
( cd backend && uv run python -c "from demucs.pretrained import get_model; get_model('htdemucs_ft')" )

echo "Setup done. Run ./scripts/run.sh to start."
```

- [ ] **Step 2: Create run.sh**

```bash
# scripts/run.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=${PORT:-8000}
cd backend

# Rebuild frontend if stale
if [ ! -f app/static/index.html ] || [ "$(find ../frontend/src -newer app/static/index.html -print -quit 2>/dev/null)" ]; then
  ( cd ../frontend && pnpm build )
fi

# Start uvicorn, open browser once healthy
uv run uvicorn app.main:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null || true" EXIT

for i in $(seq 1 30); do
  if curl -s "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

open "http://localhost:$PORT"
wait $SERVER_PID
```

- [ ] **Step 3: Create dev.sh**

```bash
# scripts/dev.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Backend on 8000
( cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload ) &
BACK_PID=$!

# Frontend on 5173, proxies /api to 8000
( cd frontend && pnpm dev --port 5173 --host 127.0.0.1 ) &
FRONT_PID=$!

trap "kill $BACK_PID $FRONT_PID 2>/dev/null || true" EXIT
wait
```

- [ ] **Step 4: Create update.sh**

```bash
# scripts/update.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
echo "==> Updating yt-dlp to latest"
uv pip install -U yt-dlp
echo "Done."
```

- [ ] **Step 5: chmod + README**

Run: `chmod +x scripts/*.sh`

```markdown
# ExtractAssets

Local tool that splits Instagram Reels / YouTube Shorts audio into **speech**, deduplicated **sound effects**, and **music** — with a web UI.

## Requirements
- macOS (Apple Silicon recommended for MPS-accelerated Demucs)
- Python 3.11+, [uv](https://github.com/astral-sh/uv)
- Node 20+, [pnpm](https://pnpm.io)
- `ffmpeg` on your PATH (`brew install ffmpeg`)

## Install
```bash
./scripts/setup.sh
```

## Run
```bash
./scripts/run.sh
```
Opens `http://localhost:8000` in your browser.

## Dev
```bash
./scripts/dev.sh
```
Frontend on `:5173` with HMR, backend on `:8000` with reload.

## Design
Spec: [`docs/superpowers/specs/2026-04-16-extractassets-design.md`](docs/superpowers/specs/2026-04-16-extractassets-design.md)
Plan: [`docs/superpowers/plans/2026-04-16-extractassets.md`](docs/superpowers/plans/2026-04-16-extractassets.md)
```

- [ ] **Step 6: Final smoke run**

Run: `./scripts/run.sh`
Expected: uvicorn starts, browser opens to the app, you can paste a reel URL, watch stages light up, and see the three assets play back inline.

- [ ] **Step 7: Commit**

```bash
git add scripts/ README.md
git commit -m "feat: add setup/run/dev/update scripts and README"
```

---

## Summary & Execution

**Total tasks:** 28.
**Phase 1 (Tasks 1-14):** produces a CLI-testable extraction pipeline. Validate here before proceeding.
**Phase 2 (Tasks 15-18):** wraps pipeline in REST + WebSocket. `curl`-testable.
**Phase 3 (Tasks 19-26):** React SPA matching the approved mockup.
**Phase 4 (Tasks 27-28):** E2E test + run scripts.

Each task is self-contained with tests passing as the definition of done. Individual stages (especially SFX mining) can be iterated on by modifying a single file without touching the rest of the system — that's the whole point of the modular structure.
