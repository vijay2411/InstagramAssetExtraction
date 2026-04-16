import shutil
from pathlib import Path
import soundfile as sf
from app.pipeline.base import JobContext
from app.pipeline.audio import AudioStage

FIXTURE = Path(__file__).parent / "fixtures" / "tiny.mp4"


def _ctx_with_video(tmp_path: Path) -> JobContext:
    shutil.copy(FIXTURE, tmp_path / "source.mp4")
    return JobContext(
        job_id="j1",
        job_dir=tmp_path,
        inputs={"video": tmp_path / "source.mp4"},
    )


def test_audio_produces_wav(tmp_path: Path):
    stage = AudioStage()
    result = stage.run(_ctx_with_video(tmp_path))
    out = tmp_path / result.artifacts["audio"]
    assert out.exists()
    data, sr = sf.read(out)
    assert sr == 44100
    assert data.ndim == 2  # stereo
    assert abs(len(data) / sr - 2.0) < 0.1  # ~2 seconds
