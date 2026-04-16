from pathlib import Path
import pytest
from app.pipeline.base import JobContext, StageResult, Stage, StageEvent
from app.pipeline.orchestrator import Orchestrator
from app.core.errors import StageError


class FakeStage:
    def __init__(self, name: str, artifacts: dict, fail: bool = False, retriable: bool = True):
        self.name = name
        self._artifacts = artifacts
        self._fail = fail
        self._retriable = retriable

    def run(self, ctx: JobContext) -> StageResult:
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.5))
        if self._fail:
            raise StageError(f"{self.name} boom", retriable=self._retriable)
        return StageResult(artifacts={k: Path(v) for k, v in self._artifacts.items()})


def test_orchestrator_runs_stages_in_order(tmp_path: Path):
    events = []
    orch = Orchestrator(
        stages=[
            FakeStage("download", {"video": "source.mp4"}),
            FakeStage("audio", {"audio": "audio.wav"}),
        ],
        emit=lambda e: events.append(e),
    )
    (tmp_path / "source.mp4").write_bytes(b"x")
    (tmp_path / "audio.wav").write_bytes(b"x")
    result = orch.run(job_id="j1", job_dir=tmp_path, params={})
    # Events should show both stage.start and stage.done for each
    types = [(e["type"], e["stage"]) for e in events if "stage" in e]
    assert ("stage.start", "download") in types
    assert ("stage.done", "download") in types
    assert ("stage.start", "audio") in types
    assert ("stage.done", "audio") in types
    assert result["success"]


def test_orchestrator_passes_artifacts_between_stages(tmp_path: Path):
    observed_inputs = {}

    class RecordingStage:
        name = "audio"

        def run(self, ctx):
            observed_inputs.update(ctx.inputs)
            return StageResult()

    (tmp_path / "source.mp4").write_bytes(b"x")
    orch = Orchestrator(stages=[FakeStage("download", {"video": "source.mp4"}), RecordingStage()])
    orch.run(job_id="j1", job_dir=tmp_path, params={})
    assert "video" in observed_inputs
    assert observed_inputs["video"] == tmp_path / "source.mp4"


def test_orchestrator_stops_on_stage_error_and_emits_job_error(tmp_path: Path):
    events = []
    orch = Orchestrator(
        stages=[FakeStage("download", {}, fail=True, retriable=True), FakeStage("audio", {})],
        emit=lambda e: events.append(e),
    )
    result = orch.run(job_id="j1", job_dir=tmp_path, params={})
    assert not result["success"]
    assert any(e["type"] == "stage.error" and e["stage"] == "download" for e in events)
    # audio stage should never start
    assert not any(e.get("stage") == "audio" and e["type"] == "stage.start" for e in events)


def test_orchestrator_can_be_canceled(tmp_path: Path):
    from threading import Event
    cancel = Event()

    class SlowStage:
        name = "download"

        def run(self, ctx):
            cancel.wait(timeout=0.5)
            return StageResult()

    events = []
    orch = Orchestrator(stages=[SlowStage()], emit=lambda e: events.append(e), cancel_event=cancel)
    cancel.set()
    result = orch.run(job_id="j1", job_dir=tmp_path, params={})
    assert any(e["type"] in ("job.canceled", "job.error") for e in events)
