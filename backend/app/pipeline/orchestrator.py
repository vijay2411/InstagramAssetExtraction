from __future__ import annotations
from pathlib import Path
from threading import Event
from typing import Callable, Any
from app.pipeline.base import Stage, JobContext, StageEvent
from app.core.errors import StageError

Emit = Callable[[dict[str, Any]], None]


class Orchestrator:
    def __init__(
        self,
        stages: list[Stage],
        emit: Emit | None = None,
        cancel_event: Event | None = None,
    ):
        self.stages = stages
        self.emit = emit or (lambda _e: None)
        self.cancel_event = cancel_event

    def run(self, job_id: str, job_dir: Path, params: dict) -> dict:
        inputs: dict[str, Path] = {}
        shared_params: dict[str, Any] = dict(params)

        def _stage_emit(event: StageEvent):
            self.emit({
                "type": "stage.progress",
                "stage": event.stage,
                "progress": event.progress,
                "message": event.message,
            })

        for stage in self.stages:
            if self.cancel_event and self.cancel_event.is_set():
                self.emit({"type": "job.canceled"})
                return {"success": False, "canceled": True}

            self.emit({"type": "stage.start", "stage": stage.name})

            ctx = JobContext(
                job_id=job_id,
                job_dir=job_dir,
                inputs={**inputs},
                params={**shared_params},
                emit=_stage_emit,
            )

            try:
                result = stage.run(ctx)
            except StageError as e:
                self.emit({
                    "type": "stage.error",
                    "stage": stage.name,
                    "message": e.message,
                    "retriable": e.retriable,
                })
                self.emit({"type": "job.error", "stage": stage.name, "message": e.message})
                return {"success": False, "stage": stage.name, "error": e.message}

            # Convert relative artifact paths to absolute; accumulate inputs
            for name, rel_path in result.artifacts.items():
                inputs[name] = job_dir / rel_path

            # Propagate stage extras into shared params for later stages
            for key, value in result.extra.items():
                shared_params[key] = value

            self.emit({
                "type": "stage.done",
                "stage": stage.name,
                "artifacts": {name: str(p) for name, p in result.artifacts.items()},
            })

        self.emit({"type": "job.done", "manifest": shared_params.get("manifest", {})})
        return {"success": True}
