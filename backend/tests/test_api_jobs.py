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
