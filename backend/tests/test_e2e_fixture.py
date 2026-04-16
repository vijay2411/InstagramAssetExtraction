# backend/tests/test_e2e_fixture.py
"""
End-to-end pipeline test against a real YouTube Shorts URL.

Marked @pytest.mark.slow — not run in the default pytest invocation.
Run explicitly with:   cd backend && uv run pytest tests/test_e2e_fixture.py -v -m slow

Prerequisites:
- yt-dlp, ffmpeg, demucs installed (i.e. setup.sh has been run)
- Demucs htdemucs_ft weights cached locally (one-time ~2GB download)
- Network access

Typical runtime: 1–3 minutes (dominated by Demucs).
"""
import pytest
from pathlib import Path
from app.pipeline.cli import build_default_stages
from app.pipeline.orchestrator import Orchestrator

# Short, CC-licensed public YouTube clip. Replace with any public Short if this
# video becomes unavailable — test only cares about the pipeline shape.
FIXTURE_URL = "https://www.youtube.com/shorts/aqz-KE-bpKQ"

@pytest.mark.slow
def test_full_pipeline_on_real_url(tmp_path: Path):
    events: list[dict] = []
    orch = Orchestrator(
        stages=build_default_stages(),
        emit=lambda e: events.append(e),
    )
    result = orch.run(
        job_id="e2e",
        job_dir=tmp_path,
        params={
            "url": FIXTURE_URL,
            "source_url": FIXTURE_URL,
            "device": "cpu",  # avoid MPS availability assumptions on CI/dev
            "model": "htdemucs_ft",
            "min_cluster_size": 2,
            "clip_min_ms": 300,
            "clip_max_ms": 1500,
        },
    )
    assert result["success"], f"failed at {result.get('stage')}: {result.get('error')}"
    for name in (
        "source.mp4", "audio.wav", "speech.wav", "non_speech.wav",
        "music.wav", "metadata.json", "sfx_clusters.json",
    ):
        assert (tmp_path / name).exists(), f"missing {name}"
    assert (tmp_path / "sfx").is_dir()
