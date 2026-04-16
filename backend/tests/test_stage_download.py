import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from app.pipeline.base import JobContext
from app.pipeline.download import DownloadStage
from app.core.errors import StageError


def _ctx(tmp_path: Path, url: str) -> JobContext:
    return JobContext(
        job_id="j1",
        job_dir=tmp_path,
        params={"url": url},
    )


@patch("app.pipeline.download.subprocess.run")
def test_download_success_writes_mp4_and_meta(mock_run, tmp_path: Path):
    def side_effect(cmd, *a, **kw):
        if "--write-info-json" in cmd:
            (tmp_path / "source.mp4").write_bytes(b"fakevideo")
            (tmp_path / "source.info.json").write_text(json.dumps({
                "title": "Demo Reel",
                "track": "Espresso",
                "artist": "Sabrina Carpenter"
            }))
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect
    stage = DownloadStage()
    result = stage.run(_ctx(tmp_path, "https://instagram.com/reel/abc"))

    assert "video" in result.artifacts
    assert (tmp_path / result.artifacts["video"]).exists()
    assert "meta" in result.artifacts
    meta = json.loads((tmp_path / result.artifacts["meta"]).read_text())
    assert meta["track"] == "Espresso"


@patch("app.pipeline.download.subprocess.run")
def test_download_failure_raises_stage_error(mock_run, tmp_path: Path):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR: Private video")
    stage = DownloadStage()
    with pytest.raises(StageError) as exc:
        stage.run(_ctx(tmp_path, "https://instagram.com/reel/private"))
    assert "Private" in exc.value.message


def test_download_requires_url_param(tmp_path: Path):
    stage = DownloadStage()
    with pytest.raises(StageError):
        stage.run(JobContext(job_id="j1", job_dir=tmp_path, params={}))
