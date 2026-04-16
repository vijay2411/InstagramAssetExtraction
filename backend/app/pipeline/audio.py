from __future__ import annotations
import subprocess
from pathlib import Path
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError


class AudioStage:
    name = "audio"

    def run(self, ctx: JobContext) -> StageResult:
        video = ctx.inputs.get("video")
        if not video or not video.exists():
            raise StageError("missing video input", retriable=False)

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0))
        out = ctx.job_dir / "audio.wav"
        cmd = [
            "ffmpeg", "-y", "-i", str(video),
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise StageError(f"ffmpeg failed: {proc.stderr.strip()[:200]}")
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0))
        return StageResult(artifacts={"audio": Path("audio.wav")})
