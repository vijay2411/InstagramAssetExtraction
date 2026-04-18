"""
Integration tests for the SFX extraction orchestrator, and for the HTTP
endpoint that wraps it. Heavy stages (download, align, subtract) are
mocked — we exercise the glue and error paths.
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import soundfile as sf
import pytest
from fastapi.testclient import TestClient

from app import deps
from app.main import app
from app.storage.config_store import FileConfigStore
from app.storage.job_store import InMemoryJobStore, JobState, JobStatus
from app.ws.event_bus import EventBus
from app.storage.asset_storage import LocalAssetStorage
from app.sfx_extract.orchestrator import extract_sfx, ExtractResult
from app.sfx_extract.song_cache import LocalFileSongCache
from app.sfx_extract.align import AlignmentResult
from app.sfx_extract.yt_download import YtCandidate

SR = 22050


def _make_music_wav(path: Path, dur_s: float = 10.0):
    t = np.linspace(0, dur_s, int(SR * dur_s), endpoint=False)
    y = 0.2 * np.sin(2 * np.pi * 330 * t)
    sf.write(str(path), np.stack([y, y], axis=1).astype(np.float32), SR)


# ---------- orchestrator direct tests ----------

def test_extract_sfx_returns_precheck_error_when_no_music(tmp_path: Path):
    cache = LocalFileSongCache(tmp_path / "cache")
    result = extract_sfx(tmp_path, "A", "B", cache=cache)
    assert result.ok is False
    assert result.stage_failed == "precheck"


@patch("app.sfx_extract.orchestrator.subtract")
@patch("app.sfx_extract.orchestrator.align")
@patch("app.sfx_extract.orchestrator.fetch_top_candidates")
@patch("app.sfx_extract.orchestrator.SfxStage")
def test_extract_sfx_happy_path_no_cache(
    mock_sfx_stage_cls, mock_fetch, mock_align, mock_sub, tmp_path: Path,
):
    _make_music_wav(tmp_path / "music.wav")
    cache = LocalFileSongCache(tmp_path / "cache")

    # Mock: download returns one candidate.
    cand_audio = tmp_path / "cand.wav"
    _make_music_wav(cand_audio, dur_s=30.0)
    mock_fetch.return_value = [
        YtCandidate(index=1, video_id="aaa", title="Rasputin", uploader="x",
                    duration_s=244.0, audio_path=cand_audio)
    ]
    # Align picks it with high confidence.
    mock_align.return_value = AlignmentResult(
        offset_s=5.0, pitch_shift=0, confidence=20.0,
        reference_duration_s=30.0, hop_s=0.023,
    )
    # Subtraction succeeds. Probe files land at _probe_residual_<i>.wav;
    # orchestrator moves the winning probe into sfx_residual.wav.
    def fake_subtract(mix_path, ref_path, ref_offset_s, dst_path):
        sf.write(str(dst_path), np.zeros((SR, 2), dtype=np.float32), SR)
        return MagicMock(ok=True, residual_rms_ratio=0.1, residual_path=dst_path)
    mock_sub.side_effect = fake_subtract
    # SfxStage instance returns a result with 3 sfx clusters.
    stage_instance = MagicMock()
    stage_instance.run.return_value = MagicMock(
        artifacts={"clusters_meta": Path("sfx_clusters.json")},
        extra={"sfx_count": 3},
    )
    mock_sfx_stage_cls.return_value = stage_instance
    (tmp_path / "sfx_clusters.json").write_text("[]")

    events = []
    result = extract_sfx(tmp_path, "Boney M.", "Rasputin", cache=cache,
                        emit=lambda e: events.append(e))

    assert result.ok
    assert result.sfx_count == 3
    assert result.cache_hit is False
    # Cache was populated.
    assert cache.get("Boney M.", "Rasputin") is not None
    # Progress events covered every stage.
    stages_seen = {e.get("stage") for e in events}
    assert {"cache", "download", "align", "subtract", "mine"}.issubset(stages_seen)


@patch("app.sfx_extract.orchestrator.fetch_top_candidates")
def test_extract_sfx_bails_on_download_failure(mock_fetch, tmp_path: Path):
    _make_music_wav(tmp_path / "music.wav")
    from app.sfx_extract.yt_download import YtDownloadError
    mock_fetch.side_effect = YtDownloadError("blocked")

    cache = LocalFileSongCache(tmp_path / "cache")
    result = extract_sfx(tmp_path, "A", "B", cache=cache)
    assert not result.ok
    assert result.stage_failed == "download"
    assert "blocked" in (result.error or "")


@patch("app.sfx_extract.orchestrator.align")
@patch("app.sfx_extract.orchestrator.fetch_top_candidates")
def test_extract_sfx_bails_on_low_alignment_confidence(mock_fetch, mock_align, tmp_path: Path):
    _make_music_wav(tmp_path / "music.wav")
    cand = tmp_path / "c.wav"; _make_music_wav(cand, dur_s=30.0)
    mock_fetch.return_value = [YtCandidate(1, "x", "T", "u", 200.0, cand)]
    mock_align.return_value = AlignmentResult(
        offset_s=5.0, pitch_shift=0, confidence=1.0,  # below MIN_CONFIDENCE 2.5
        reference_duration_s=30.0, hop_s=0.023,
    )
    cache = LocalFileSongCache(tmp_path / "cache")
    result = extract_sfx(tmp_path, "A", "B", cache=cache)
    assert not result.ok
    assert result.stage_failed == "align"


@patch("app.sfx_extract.orchestrator.subtract")
@patch("app.sfx_extract.orchestrator.align")
@patch("app.sfx_extract.orchestrator.fetch_top_candidates")
def test_extract_sfx_bails_on_bad_subtraction(mock_fetch, mock_align, mock_sub, tmp_path: Path):
    _make_music_wav(tmp_path / "music.wav")
    cand = tmp_path / "c.wav"; _make_music_wav(cand, dur_s=30.0)
    mock_fetch.return_value = [YtCandidate(1, "x", "T", "u", 200.0, cand)]
    mock_align.return_value = AlignmentResult(
        offset_s=0, pitch_shift=0, confidence=15.0,
        reference_duration_s=30.0, hop_s=0.023,
    )
    def bad_sub(mix_path, ref_path, ref_offset_s, dst_path):
        sf.write(str(dst_path), np.zeros((SR, 2), dtype=np.float32), SR)
        return MagicMock(ok=False, residual_rms_ratio=0.8, residual_path=dst_path)
    mock_sub.side_effect = bad_sub

    cache = LocalFileSongCache(tmp_path / "cache")
    result = extract_sfx(tmp_path, "A", "B", cache=cache)
    assert not result.ok
    assert result.stage_failed == "subtract"


@patch("app.sfx_extract.orchestrator.subtract")
@patch("app.sfx_extract.orchestrator.align")
@patch("app.sfx_extract.orchestrator.SfxStage")
def test_extract_sfx_uses_cache_when_available(
    mock_sfx_stage_cls, mock_align, mock_sub, tmp_path: Path,
):
    _make_music_wav(tmp_path / "music.wav")
    cache = LocalFileSongCache(tmp_path / "cache")
    # Preload cache.
    src = tmp_path / "cached.wav"; _make_music_wav(src, dur_s=30.0)
    cache.put("A", "B", src, source="youtube", duration_s=30.0)

    mock_align.return_value = AlignmentResult(
        offset_s=3.0, pitch_shift=0, confidence=12.0,
        reference_duration_s=30.0, hop_s=0.023,
    )
    def good_sub(mix_path, ref_path, ref_offset_s, dst_path):
        sf.write(str(dst_path), np.zeros((SR, 2), dtype=np.float32), SR)
        return MagicMock(ok=True, residual_rms_ratio=0.1, residual_path=dst_path)
    mock_sub.side_effect = good_sub

    stage_instance = MagicMock()
    stage_instance.run.return_value = MagicMock(
        artifacts={"clusters_meta": Path("sfx_clusters.json")},
        extra={"sfx_count": 1},
    )
    mock_sfx_stage_cls.return_value = stage_instance
    (tmp_path / "sfx_clusters.json").write_text("[]")

    result = extract_sfx(tmp_path, "A", "B", cache=cache)
    assert result.ok
    assert result.cache_hit is True


# ---------- endpoint tests ----------

def _setup_job_with_song(tmp_path: Path, song: dict | None, audd_song: dict | None = None):
    """Create a complete job directory with music.wav + manifest + optional audd match."""
    cfg = FileConfigStore(tmp_path / "cfg.json")
    cfg.update({"output_base_dir": str(tmp_path / "outs")})
    job_store = InMemoryJobStore()
    bus = EventBus()
    asset_storage = LocalAssetStorage(tmp_path / "outs")
    app.dependency_overrides[deps.get_config_store] = lambda: cfg
    app.dependency_overrides[deps.get_job_store] = lambda: job_store
    app.dependency_overrides[deps.get_event_bus] = lambda: bus
    app.dependency_overrides[deps.get_asset_storage] = lambda: asset_storage

    job_dir = asset_storage.create_job_dir(job_id="jobX", slug="test")
    _make_music_wav(job_dir / "music.wav", dur_s=10.0)

    manifest = {"assets": {"music": {"path": "music.wav", "duration": 10.0}}}
    if song:
        manifest["assets"]["music"]["song"] = song
    (job_dir / "metadata.json").write_text(json.dumps(manifest))

    if audd_song:
        (job_dir / "music_match.json").write_text(json.dumps({"song": audd_song}))

    state = JobState(job_id="jobX", url="u", job_dir=str(job_dir))
    state.status = JobStatus.DONE
    job_store._jobs["jobX"] = state
    return job_store, job_dir


def _teardown():
    app.dependency_overrides.clear()


def test_endpoint_400_when_no_song(tmp_path: Path):
    _setup_job_with_song(tmp_path, song=None)
    client = TestClient(app)
    resp = client.post("/api/jobs/jobX/extract-sfx", json={})
    assert resp.status_code == 400
    assert "find song" in resp.json()["detail"].lower()
    _teardown()


def test_endpoint_404_on_missing_job(tmp_path: Path):
    _setup_job_with_song(tmp_path, song={"title": "T", "artist": "A"})
    client = TestClient(app)
    resp = client.post("/api/jobs/wrongID/extract-sfx", json={})
    assert resp.status_code == 404
    _teardown()


@patch("app.api.jobs.extract_sfx")
def test_endpoint_uses_case2_song_from_manifest(mock_extract, tmp_path: Path):
    _setup_job_with_song(tmp_path, song={"title": "Rasputin", "artist": "Boney M."})
    mock_extract.return_value = ExtractResult(ok=True, sfx_count=2)

    client = TestClient(app)
    resp = client.post("/api/jobs/jobX/extract-sfx", json={})
    assert resp.status_code == 200
    # Verify orchestrator was called with the manifest song.
    kwargs = mock_extract.call_args.kwargs
    assert kwargs["artist"] == "Boney M."
    assert kwargs["title"] == "Rasputin"
    _teardown()


@patch("app.api.jobs.extract_sfx")
def test_endpoint_prefers_audd_match_over_manifest(mock_extract, tmp_path: Path):
    _setup_job_with_song(
        tmp_path,
        song={"title": "Wrong", "artist": "Wrong"},
        audd_song={"title": "Correct", "artist": "Audd"},
    )
    mock_extract.return_value = ExtractResult(ok=True, sfx_count=1)
    client = TestClient(app)
    resp = client.post("/api/jobs/jobX/extract-sfx", json={})
    assert resp.status_code == 200
    kwargs = mock_extract.call_args.kwargs
    assert kwargs["title"] == "Correct"
    assert kwargs["artist"] == "Audd"
    _teardown()


@patch("app.api.jobs.extract_sfx")
def test_endpoint_accepts_explicit_override(mock_extract, tmp_path: Path):
    _setup_job_with_song(tmp_path, song={"title": "T1", "artist": "A1"})
    mock_extract.return_value = ExtractResult(ok=True, sfx_count=0)
    client = TestClient(app)
    resp = client.post("/api/jobs/jobX/extract-sfx",
                       json={"title": "Override Title", "artist": "Override Artist"})
    assert resp.status_code == 200
    kwargs = mock_extract.call_args.kwargs
    assert kwargs["title"] == "Override Title"
    _teardown()


@patch("app.api.jobs.extract_sfx")
def test_endpoint_returns_failure_payload(mock_extract, tmp_path: Path):
    _setup_job_with_song(tmp_path, song={"title": "T", "artist": "A"})
    mock_extract.return_value = ExtractResult(
        ok=False, stage_failed="align", error="no match",
    )
    client = TestClient(app)
    resp = client.post("/api/jobs/jobX/extract-sfx", json={})
    # Endpoint returns 200 with ok=False so the frontend can show the reason.
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["stage_failed"] == "align"
    _teardown()
