from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError


def _run_demucs(audio_path: Path, out_dir: Path, model: str, device: str) -> None:
    """Actual Demucs invocation. Isolated so tests can mock it."""
    cmd = [
        "python", "-m", "demucs",
        "-n", model,
        "-d", device,
        "--two-stems=vocals",
        "-o", str(out_dir),
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise StageError(f"demucs failed: {proc.stderr.strip()[:300]}")


class SpeechStage:
    name = "speech"

    def run(self, ctx: JobContext) -> StageResult:
        audio = ctx.inputs.get("audio")
        if not audio or not audio.exists():
            raise StageError("missing audio input", retriable=False)

        model = ctx.params.get("model", "htdemucs_ft")
        device = ctx.params.get("device", "mps")
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0, message=f"running {model} on {device}"))

        demucs_out = ctx.job_dir / "_demucs"
        _run_demucs(audio, demucs_out, model, device)

        vocals = _find(demucs_out, "vocals.wav")
        no_vocals = _find(demucs_out, "no_vocals.wav")
        if not vocals or not no_vocals:
            raise StageError("demucs output files not found", retriable=False)

        speech_path = ctx.job_dir / "speech.wav"
        non_speech_path = ctx.job_dir / "non_speech.wav"
        shutil.move(str(vocals), str(speech_path))
        shutil.move(str(no_vocals), str(non_speech_path))
        shutil.rmtree(demucs_out, ignore_errors=True)

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0))
        return StageResult(
            artifacts={
                "speech": Path("speech.wav"),
                "non_speech": Path("non_speech.wav"),
            }
        )


def _find(root: Path, name: str) -> Path | None:
    for p in root.rglob(name):
        return p
    return None
