"""Tests for the YouTube download module. All network/subprocess calls are
mocked — the real integration is exercised manually / by the e2e test."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import numpy as np
import pytest
import soundfile as sf

from app.sfx_extract.yt_download import (
    build_query,
    search_candidates,
    download_as_wav,
    fetch_top_candidates,
    YtDownloadError,
)

SR = 44100


def test_build_query_quotes_both_tokens():
    assert build_query("Boney M.", "Rasputin (Instrumental)") == '"Boney M." "Rasputin (Instrumental)"'


@patch("app.sfx_extract.yt_download._yt_dlp")
def test_search_returns_top_n(mock_run):
    # Each line of yt-dlp --print-json is a separate entry.
    entries = [
        {"id": "aaa", "title": "Rasputin - Boney M", "duration": 244, "uploader": "Official"},
        {"id": "bbb", "title": "Rasputin remix", "duration": 180, "uploader": "Remix"},
        {"id": "ccc", "title": "Rasputin cover", "duration": 210, "uploader": "Cover"},
        {"id": "ddd", "title": "4th result", "duration": 100, "uploader": "Nope"},
    ]
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="\n".join(json.dumps(e) for e in entries),
        stderr="",
    )
    results = search_candidates("Boney M.", "Rasputin", top_n=3)
    assert len(results) == 3
    assert results[0]["id"] == "aaa"


@patch("app.sfx_extract.yt_download._yt_dlp")
def test_search_raises_on_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR: blocked")
    with pytest.raises(YtDownloadError, match="blocked"):
        search_candidates("A", "B")


@patch("app.sfx_extract.yt_download._yt_dlp")
def test_search_skips_malformed_json_lines(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='{"id":"ok"}\n<html>garbage</html>\n{"id":"also_ok"}',
        stderr="",
    )
    results = search_candidates("A", "B", top_n=5)
    assert [r["id"] for r in results] == ["ok", "also_ok"]


@patch("app.sfx_extract.yt_download._yt_dlp")
def test_download_writes_wav(mock_run, tmp_path: Path):
    def fake_run(cmd, *a, **kw):
        # Emulate yt-dlp producing the expected output file.
        out_arg = cmd[cmd.index("-o") + 1]
        stem = out_arg.replace(".%(ext)s", "")
        sf.write(f"{stem}.wav", np.zeros((SR, 2), dtype=np.float32), SR)
        return MagicMock(returncode=0, stdout="", stderr="")
    mock_run.side_effect = fake_run

    path = download_as_wav("vid123", tmp_path)
    assert path.exists()
    assert path.suffix == ".wav"


@patch("app.sfx_extract.yt_download._yt_dlp")
def test_download_raises_on_failure(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR: 404")
    with pytest.raises(YtDownloadError, match="vid404"):
        download_as_wav("vid404", tmp_path)


@patch("app.sfx_extract.yt_download.search_candidates")
@patch("app.sfx_extract.yt_download.download_as_wav")
def test_fetch_top_candidates_happy_path(mock_dl, mock_search, tmp_path: Path):
    mock_search.return_value = [
        {"id": "a", "title": "A", "duration": 200, "uploader": "u1"},
        {"id": "b", "title": "B", "duration": 180, "uploader": "u2"},
        {"id": "c", "title": "C", "duration": 220, "uploader": "u3"},
    ]
    def fake_dl(vid, dst):
        p = Path(dst) / f"{vid}.wav"
        sf.write(str(p), np.zeros((SR, 2), dtype=np.float32), SR)
        return p
    mock_dl.side_effect = fake_dl

    cands = fetch_top_candidates("Artist", "Title", top_n=3, dst_dir=tmp_path)
    assert len(cands) == 3
    assert [c.video_id for c in cands] == ["a", "b", "c"]
    assert all(c.audio_path.exists() for c in cands)
    assert cands[0].index == 1


@patch("app.sfx_extract.yt_download.search_candidates")
@patch("app.sfx_extract.yt_download.download_as_wav")
def test_fetch_partial_failures_ok(mock_dl, mock_search, tmp_path: Path):
    """If some candidates fail to download, return the ones that worked."""
    mock_search.return_value = [
        {"id": "a", "title": "A", "duration": 200, "uploader": "u1"},
        {"id": "b", "title": "B", "duration": 180, "uploader": "u2"},
        {"id": "c", "title": "C", "duration": 220, "uploader": "u3"},
    ]
    def fake_dl(vid, dst):
        if vid == "b":
            raise YtDownloadError("region blocked")
        p = Path(dst) / f"{vid}.wav"
        sf.write(str(p), np.zeros((SR, 2), dtype=np.float32), SR)
        return p
    mock_dl.side_effect = fake_dl

    cands = fetch_top_candidates("Artist", "Title", top_n=3, dst_dir=tmp_path)
    assert [c.video_id for c in cands] == ["a", "c"]


@patch("app.sfx_extract.yt_download.search_candidates")
@patch("app.sfx_extract.yt_download.download_as_wav")
def test_fetch_all_failures_raises(mock_dl, mock_search, tmp_path: Path):
    mock_search.return_value = [{"id": "a", "title": "A", "duration": 200, "uploader": "u"}]
    mock_dl.side_effect = YtDownloadError("blocked everywhere")
    with pytest.raises(YtDownloadError, match="all 1 candidate downloads failed"):
        fetch_top_candidates("Artist", "Title", top_n=1, dst_dir=tmp_path)


@patch("app.sfx_extract.yt_download.search_candidates")
def test_fetch_empty_search_raises(mock_search, tmp_path: Path):
    mock_search.return_value = []
    with pytest.raises(YtDownloadError, match="no YouTube results"):
        fetch_top_candidates("A", "B", dst_dir=tmp_path)
