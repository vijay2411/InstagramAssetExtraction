from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from app import deps
from app.main import app
from app.storage.config_store import FileConfigStore
from app.storage.job_store import InMemoryJobStore, JobState, JobStatus
from app.ws.event_bus import EventBus
from app.storage.asset_storage import LocalAssetStorage
from app.music_id.audd import AudDMatch

SR = 44100


def _setup(tmp_path: Path, audd_key: str = "fake-key"):
    cfg_store = FileConfigStore(tmp_path / "cfg.json")
    cfg_store.update({
        "output_base_dir": str(tmp_path / "outs"),
        "audd_api_key": audd_key,
    })
    job_store = InMemoryJobStore()
    bus = EventBus()
    asset_storage = LocalAssetStorage(tmp_path / "outs")
    app.dependency_overrides[deps.get_config_store] = lambda: cfg_store
    app.dependency_overrides[deps.get_job_store] = lambda: job_store
    app.dependency_overrides[deps.get_event_bus] = lambda: bus
    app.dependency_overrides[deps.get_asset_storage] = lambda: asset_storage

    # Fake a completed job with a music.wav present.
    job_dir = asset_storage.create_job_dir(job_id="abc123", slug="x")
    sf.write(str(job_dir / "music.wav"), np.random.randn(SR * 30, 2).astype(np.float32) * 0.3, SR)
    state = JobState(job_id="abc123", url="https://example.com/r/1", job_dir=str(job_dir))
    state.status = JobStatus.DONE
    job_store._jobs[state.job_id] = state  # bypass create() "one at a time" guard
    return job_store, job_dir


def _teardown():
    app.dependency_overrides.clear()


def test_identify_404_on_missing_job(tmp_path: Path):
    _setup(tmp_path)
    client = TestClient(app)
    resp = client.post("/api/jobs/nope/identify-music", json={})
    assert resp.status_code == 404
    _teardown()


def test_identify_400_when_key_missing(tmp_path: Path):
    _setup(tmp_path, audd_key="")
    client = TestClient(app)
    resp = client.post("/api/jobs/abc123/identify-music", json={})
    assert resp.status_code == 400
    assert "audd" in resp.json()["detail"].lower()
    _teardown()


def test_identify_409_when_music_missing(tmp_path: Path):
    job_store, job_dir = _setup(tmp_path)
    (job_dir / "music.wav").unlink()
    client = TestClient(app)
    resp = client.post("/api/jobs/abc123/identify-music", json={})
    assert resp.status_code == 409
    _teardown()


@patch("app.api.jobs.audd_identify")
def test_identify_auto_window_success(mock_identify, tmp_path: Path):
    _setup(tmp_path)
    mock_identify.return_value = AudDMatch(
        title="Espresso",
        artist="Sabrina Carpenter",
        album="Short n' Sweet",
        spotify_url="https://open.spotify.com/track/abc",
        apple_music_url="https://music.apple.com/us/album/xyz",
    )
    client = TestClient(app)
    resp = client.post("/api/jobs/abc123/identify-music", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is True
    assert body["song"]["title"] == "Espresso"
    assert body["song"]["spotify_url"] == "https://open.spotify.com/track/abc"
    assert body["song"]["youtube_url"].startswith("https://www.youtube.com/results")
    assert body["window"]["auto"] is True
    _teardown()


@patch("app.api.jobs.audd_identify")
def test_identify_manual_window(mock_identify, tmp_path: Path):
    _setup(tmp_path)
    mock_identify.return_value = None  # no match
    client = TestClient(app)
    resp = client.post("/api/jobs/abc123/identify-music", json={"start_s": 5.0, "window_s": 10.0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is False
    assert body["window"] == {"start_s": 5.0, "end_s": 15.0, "auto": False, "gain": 1.0}
    _teardown()


@patch("app.api.jobs.audd_identify")
def test_identify_persists_match(mock_identify, tmp_path: Path):
    _, job_dir = _setup(tmp_path)
    mock_identify.return_value = AudDMatch(title="T", artist="A")
    client = TestClient(app)
    resp = client.post("/api/jobs/abc123/identify-music", json={})
    assert resp.status_code == 200
    assert (job_dir / "music_match.json").exists()
    _teardown()


@patch("app.api.jobs.audd_identify")
def test_identify_forwards_gain_param(mock_identify, tmp_path: Path):
    """When gain > 1 is passed, the clip written to disk (and sent to AudD)
    should be amplified. We verify via the file handed to audd_identify."""
    _setup(tmp_path)
    captured = {}

    def fake(clip_path, api_key):
        # Read the clip back to confirm it's been amplified.
        import soundfile as sf2
        data, _ = sf2.read(str(clip_path))
        captured["peak"] = float(data.max())
        return None
    mock_identify.side_effect = fake

    client = TestClient(app)
    # Music.wav in the fixture is random * 0.3 → peak around 0.3.
    # 2x gain → ~0.6 peak.
    resp = client.post("/api/jobs/abc123/identify-music", json={"gain": 2.0})
    assert resp.status_code == 200
    assert resp.json()["window"]["gain"] == 2.0
    assert captured["peak"] > 0.5, f"expected amplified peak > 0.5, got {captured['peak']}"
    _teardown()


@patch("app.api.jobs.audd_identify")
def test_identify_upstream_error_returns_502(mock_identify, tmp_path: Path):
    _setup(tmp_path)
    from app.music_id.audd import AudDError
    mock_identify.side_effect = AudDError("rate limited")
    client = TestClient(app)
    resp = client.post("/api/jobs/abc123/identify-music", json={})
    assert resp.status_code == 502
    assert "rate limited" in resp.json()["detail"]
    _teardown()
