from __future__ import annotations
import re
import shutil
import subprocess
import sys
from pathlib import Path
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError


# Lines matching this pattern are tqdm progress bars — they drown out the
# actual traceback when surfaced in an error message. Filter them out.
_TQDM_LINE = re.compile(r"^\s*\d+%\|[\s\S]*?\|\s*[\d.]+/[\d.]+\s*\[[^\]]+\]\s*$")


def _clean_stderr_tail(stderr: str, limit: int = 500) -> str:
    """Return the last ~500 chars of stderr with tqdm progress lines removed.
    This surfaces the actual Python traceback instead of progress noise."""
    if not stderr:
        return "(no stderr)"
    # tqdm uses carriage returns to overwrite — split on \r AND \n
    parts: list[str] = []
    for line in re.split(r"[\r\n]+", stderr):
        line = line.strip()
        if not line:
            continue
        if _TQDM_LINE.match(line):
            continue
        parts.append(line)
    tail = "\n".join(parts)[-limit:]
    return tail or stderr.strip()[-limit:]


def _run_demucs(audio_path: Path, out_dir: Path, model: str, device: str) -> None:
    """Actual Demucs invocation. Isolated so tests can mock it."""
    cmd = [
        sys.executable, "-m", "demucs",
        "-n", model,
        "-d", device,
        "--two-stems=vocals",
        "-o", str(out_dir),
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise StageError(f"demucs failed ({device}): {_clean_stderr_tail(proc.stderr)}")


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
        try:
            _run_demucs(audio, demucs_out, model, device)
        except StageError as err:
            # MPS can OOM on long/heavy audio. Fall back to CPU once before giving up.
            msg = str(err.message).lower()
            mps_oom = device == "mps" and any(
                token in msg for token in ("mps", "out of memory", "allocator", "cannot allocate")
            )
            if not mps_oom:
                raise
            shutil.rmtree(demucs_out, ignore_errors=True)
            ctx.emit(StageEvent(
                type="progress", stage=self.name, progress=0.0,
                message="MPS failed — retrying on CPU (slower)",
            ))
            _run_demucs(audio, demucs_out, model, "cpu")

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
