from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
import soundfile as sf
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError

def _duration(p: Path) -> float:
    try:
        info = sf.info(str(p))
        return float(info.duration)
    except Exception:
        return 0.0

class FinalizeStage:
    name = "finalize"

    def run(self, ctx: JobContext) -> StageResult:
        speech = ctx.inputs.get("speech")
        music = ctx.inputs.get("music")
        clusters_meta = ctx.inputs.get("clusters_meta")
        video = ctx.inputs.get("video")
        source_url = ctx.params.get("source_url", "")
        song = ctx.params.get("song")

        if not (speech and music and clusters_meta):
            raise StageError("missing inputs for finalize", retriable=False)

        clusters = json.loads(clusters_meta.read_text())
        sfx_entries = []
        for c in clusters:
            rel = c["representative_path"]
            abs_p = ctx.job_dir / rel
            sfx_entries.append({
                "path": rel,
                "duration": _duration(abs_p),
                "repeats": c["count"],
                "onset_times": c["onset_times_s"],
            })

        manifest = {
            "job_id": ctx.job_id,
            "source_url": source_url,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "duration_seconds": _duration(speech) if speech else 0.0,
            "assets": {
                "video": {"path": "source.mp4", "duration": _duration(video) if video else 0.0},
                "speech": {"path": "speech.wav", "duration": _duration(speech)},
                "music": {
                    "path": "music.wav",
                    "duration": _duration(music),
                    **({"song": song} if song else {}),
                },
                "sfx": sfx_entries,
            },
        }

        out = ctx.job_dir / "metadata.json"
        out.write_text(json.dumps(manifest, indent=2))
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0))
        return StageResult(artifacts={"manifest": Path("metadata.json")}, extra={"manifest": manifest})
