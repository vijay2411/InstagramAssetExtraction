import json
from pathlib import Path
import numpy as np
import soundfile as sf
from app.pipeline.base import JobContext
from app.pipeline.sfx import SfxStage

SR = 44100

def _beep(freq: float, dur_s: float, sr: int = SR) -> np.ndarray:
    t = np.linspace(0, dur_s, int(sr * dur_s), endpoint=False)
    env = np.hanning(len(t))
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
        # Synthetic sine-wave MFCCs cluster MUCH tighter than real SFX.
        # Tests use 0.01 to separate 800Hz from 2000Hz beeps; production
        # default is 0.35 (see DEFAULT_CLUSTER_DIST_THRESHOLD in sfx.py).
        # Explicitly enable SFX since the stage defaults to disabled until the
        # algorithm is improved (see SFX_ENABLED in sfx.py).
        params={
            "sfx_enabled": True,
            "min_cluster_size": 2,
            "clip_min_ms": 300,
            "clip_max_ms": 1500,
            "cluster_dist_threshold": 0.01,
        },
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
    assert len(exported) == 1

def test_sfx_empty_output_when_no_clusters(tmp_path: Path):
    # Only 1 beep, min_cluster_size=2 → no clusters
    audio = np.concatenate([_silence(0.5), _beep(800, 0.4), _silence(0.5)], axis=0)
    sf.write(tmp_path / "non_speech.wav", audio, SR)
    ctx = JobContext(
        job_id="j1", job_dir=tmp_path,
        inputs={"non_speech": tmp_path / "non_speech.wav"},
        params={
            "sfx_enabled": True,
            "min_cluster_size": 2,
            "clip_min_ms": 300,
            "clip_max_ms": 1500,
            "cluster_dist_threshold": 0.01,
        },
    )
    stage = SfxStage()
    result = stage.run(ctx)

    clusters = json.loads((tmp_path / "sfx_clusters.json").read_text())
    assert clusters == []
    sfx_dir = tmp_path / "sfx"
    assert sfx_dir.exists()
    assert list(sfx_dir.glob("*.wav")) == []


def test_sfx_disabled_is_noop_even_with_repeats(tmp_path: Path):
    # Same beep-repeat fixture that would cluster when enabled. With
    # sfx_enabled=False (the current default), the stage must NOT run
    # clustering — just write empty sfx_clusters.json and return.
    segments = [
        _silence(0.5), _beep(800, 0.4),
        _silence(1.0), _beep(800, 0.4),
        _silence(1.0), _beep(800, 0.4),
    ]
    audio = np.concatenate(segments, axis=0)
    sf.write(tmp_path / "non_speech.wav", audio, SR)
    ctx = JobContext(
        job_id="j1", job_dir=tmp_path,
        inputs={"non_speech": tmp_path / "non_speech.wav"},
        # no sfx_enabled → falls back to module default (False)
        params={"min_cluster_size": 2},
    )
    result = SfxStage().run(ctx)

    clusters = json.loads((tmp_path / "sfx_clusters.json").read_text())
    assert clusters == [], "disabled SFX stage must not produce clusters"
    assert result.extra == {"sfx_count": 0}
    assert not list((tmp_path / "sfx").glob("*.wav"))
