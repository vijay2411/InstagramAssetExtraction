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
