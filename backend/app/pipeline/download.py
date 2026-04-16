from __future__ import annotations
import subprocess
import shutil
from pathlib import Path
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError


class DownloadStage:
    name = "download"

    def run(self, ctx: JobContext) -> StageResult:
        url = ctx.params.get("url")
        if not url:
            raise StageError("missing url param", retriable=False)

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0, message="starting"))

        out_template = str(ctx.job_dir / "source.%(ext)s")
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--no-warnings",
            "--write-info-json",
            "--restrict-filenames",
            "-o", out_template,
            "-f", "mp4/best[ext=mp4]/best",
            url,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise StageError(f"yt-dlp failed: {proc.stderr.strip()[:200]}")

        video = ctx.job_dir / "source.mp4"
        meta = ctx.job_dir / "source.info.json"
        if not video.exists():
            candidates = [p for p in ctx.job_dir.glob("source.*") if p.suffix != ".json"]
            if not candidates:
                raise StageError("download succeeded but no video file found", retriable=False)
            shutil.move(str(candidates[0]), str(video))

        if not meta.exists():
            raise StageError("download succeeded but no info JSON found", retriable=False)

        dst_meta = ctx.job_dir / "source_meta.json"
        shutil.move(str(meta), str(dst_meta))

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0, message="done"))
        return StageResult(
            artifacts={"video": Path("source.mp4"), "meta": Path("source_meta.json")},
        )
