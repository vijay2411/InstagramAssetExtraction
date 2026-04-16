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
    # Fake prior-stage outputs. The mp4 only needs to exist as a path target;
    # _duration() returns 0.0 on unreadable files and the test doesn't assert
    # on video duration, so a stub byte file is sufficient.
    (tmp_path / "source.mp4").write_bytes(b"\x00" * 64)
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
