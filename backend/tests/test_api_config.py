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
