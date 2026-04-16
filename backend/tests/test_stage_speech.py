from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
from app.pipeline.base import JobContext
from app.pipeline.speech import SpeechStage


def _prep_audio(tmp_path: Path) -> JobContext:
    # 2s of stereo silence, 44.1kHz
    sf.write(tmp_path / "audio.wav", np.zeros((88200, 2), dtype=np.float32), 44100)
    return JobContext(
        job_id="j1",
        job_dir=tmp_path,
        inputs={"audio": tmp_path / "audio.wav"},
        params={"model": "htdemucs_ft", "device": "cpu"},
    )


@patch("app.pipeline.speech._run_demucs")
def test_speech_produces_vocals_and_non_speech(mock_run, tmp_path: Path):
    # Fake Demucs: writes vocals.wav and a no_vocals.wav
    def fake_run(audio_path, out_dir, model, device):
        out_dir.mkdir(parents=True, exist_ok=True)
        sf.write(out_dir / "vocals.wav", np.zeros((88200, 2), dtype=np.float32), 44100)
        sf.write(out_dir / "no_vocals.wav", np.ones((88200, 2), dtype=np.float32) * 0.1, 44100)
    mock_run.side_effect = fake_run

    stage = SpeechStage()
    result = stage.run(_prep_audio(tmp_path))
    assert (tmp_path / result.artifacts["speech"]).exists()
    assert (tmp_path / result.artifacts["non_speech"]).exists()
    # non_speech.wav should not be all zeros
    data, _ = sf.read(tmp_path / result.artifacts["non_speech"])
    assert data.any()
