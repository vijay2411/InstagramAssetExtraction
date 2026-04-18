from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import pytest
import soundfile as sf

from app.music_id.window import pick_best_window, cut_window
from app.music_id.links import (
    spotify_search_url, apple_music_search_url, youtube_search_url, all_search_links,
)
from app.music_id.audd import identify, AudDError

SR = 44100


def _write_wav_with_loud_region(path: Path, total_s: float, loud_start_s: float, loud_len_s: float):
    """Make a track that is mostly quiet but has a loud region — used to
    verify pick_best_window picks the right chunk."""
    n = int(total_s * SR)
    audio = np.random.randn(n, 2).astype(np.float32) * 0.02  # quiet noise floor
    ls = int(loud_start_s * SR)
    le = min(n, ls + int(loud_len_s * SR))
    audio[ls:le] *= 20.0  # loud region
    sf.write(str(path), audio, SR)


def test_pick_best_window_finds_loud_region(tmp_path: Path):
    wav = tmp_path / "music.wav"
    # Track: 60s total, loud region from 30s to 52s → the 20s window starting
    # near 30s should be the loudest.
    _write_wav_with_loud_region(wav, total_s=60, loud_start_s=30, loud_len_s=22)
    start, end = pick_best_window(wav, window_s=20.0, stride_s=2.0, skip_s=3.0)
    assert 28 <= start <= 34, f"expected start near 30s, got {start}"
    assert abs((end - start) - 20.0) < 0.5


def test_pick_best_window_short_track(tmp_path: Path):
    wav = tmp_path / "short.wav"
    sf.write(str(wav), np.zeros((SR * 5, 2), dtype=np.float32), SR)
    start, end = pick_best_window(wav, window_s=20.0)
    # Short track: return whole track.
    assert start == 0.0
    assert abs(end - 5.0) < 0.01


def test_cut_window_writes_correct_duration(tmp_path: Path):
    src = tmp_path / "src.wav"
    dst = tmp_path / "cut.wav"
    sf.write(str(src), np.zeros((SR * 10, 2), dtype=np.float32), SR)
    cut_window(src, dst, start_s=2.0, end_s=7.0)
    info = sf.info(str(dst))
    assert info.samplerate == SR
    assert abs(info.duration - 5.0) < 0.01


def test_cut_window_applies_gain(tmp_path: Path):
    # Quiet input @ 0.1 amplitude, 2x gain → peaks ~0.2, no clipping.
    src = tmp_path / "q.wav"
    dst = tmp_path / "q_amp.wav"
    sf.write(str(src), np.ones((SR * 2, 2), dtype=np.float32) * 0.1, SR)
    cut_window(src, dst, 0.0, 2.0, gain=2.0)
    data, _ = sf.read(str(dst))
    assert abs(data.max() - 0.2) < 0.01


def test_cut_window_clips_on_overgain(tmp_path: Path):
    # Loud input @ 0.8, 3x gain → would be 2.4 → clipped to 1.0.
    src = tmp_path / "l.wav"
    dst = tmp_path / "l_amp.wav"
    sf.write(str(src), np.ones((SR, 2), dtype=np.float32) * 0.8, SR)
    cut_window(src, dst, 0.0, 1.0, gain=3.0)
    data, _ = sf.read(str(dst))
    assert data.max() <= 1.0 and data.max() >= 0.99


def test_search_urls_escape_query():
    assert spotify_search_url("Bad Guy", "Billie Eilish") == \
        "https://open.spotify.com/search/Bad+Guy+Billie+Eilish"
    assert "music.apple.com" in apple_music_search_url("Bad Guy", "Billie Eilish")
    assert "youtube.com/results" in youtube_search_url("Bad Guy", "Billie Eilish")


def test_all_search_links_shape():
    links = all_search_links("Espresso", "Sabrina Carpenter")
    assert set(links.keys()) == {"spotify", "apple_music", "youtube"}
    for url in links.values():
        assert url.startswith("https://")


def test_audd_raises_without_api_key(tmp_path: Path):
    wav = tmp_path / "x.wav"
    sf.write(str(wav), np.zeros((SR, 2), dtype=np.float32), SR)
    with pytest.raises(AudDError, match="no AudD API key"):
        identify(wav, api_key="")


@patch("app.music_id.audd.httpx.post")
def test_audd_success(mock_post, tmp_path: Path):
    wav = tmp_path / "x.wav"
    sf.write(str(wav), np.zeros((SR, 2), dtype=np.float32), SR)
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "status": "success",
        "result": {
            "title": "Espresso",
            "artist": "Sabrina Carpenter",
            "album": "Short n' Sweet",
            "release_date": "2024-04-11",
            "song_link": "https://lis.tn/espresso",
            "spotify": {"external_urls": {"spotify": "https://open.spotify.com/track/abc"}},
            "apple_music": {"url": "https://music.apple.com/us/album/xyz"},
        },
    }
    mock_post.return_value = mock_resp
    match = identify(wav, api_key="fake")
    assert match is not None
    assert match.title == "Espresso"
    assert match.artist == "Sabrina Carpenter"
    assert match.spotify_url == "https://open.spotify.com/track/abc"
    assert match.apple_music_url == "https://music.apple.com/us/album/xyz"


@patch("app.music_id.audd.httpx.post")
def test_audd_no_match(mock_post, tmp_path: Path):
    wav = tmp_path / "x.wav"
    sf.write(str(wav), np.zeros((SR, 2), dtype=np.float32), SR)
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"status": "success", "result": None}
    mock_post.return_value = mock_resp
    match = identify(wav, api_key="fake")
    assert match is None


@patch("app.music_id.audd.httpx.post")
def test_audd_error_response(mock_post, tmp_path: Path):
    wav = tmp_path / "x.wav"
    sf.write(str(wav), np.zeros((SR, 2), dtype=np.float32), SR)
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "status": "error",
        "error": {"error_code": 901, "error_message": "API token is missing"},
    }
    mock_post.return_value = mock_resp
    with pytest.raises(AudDError, match="API token is missing"):
        identify(wav, api_key="bad")
