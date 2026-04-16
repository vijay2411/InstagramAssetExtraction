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
