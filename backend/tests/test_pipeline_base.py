from pathlib import Path
from app.pipeline.base import JobContext, StageResult, StageEvent, Stage
from app.core.errors import StageError

def test_stage_error_defaults_retriable_true():
    err = StageError("boom")
    assert err.retriable is True
    assert err.message == "boom"

def test_stage_error_non_retriable():
    err = StageError("permanent", retriable=False)
    assert err.retriable is False

def test_job_context_defaults():
    ctx = JobContext(job_id="j1", job_dir=Path("/tmp/j1"))
    assert ctx.inputs == {}
    assert ctx.params == {}
    # default emit is a no-op
    ctx.emit(StageEvent(type="progress", stage="download", progress=0.5))

def test_stage_result_defaults():
    res = StageResult()
    assert res.artifacts == {}
    assert res.extra == {}

def test_stage_protocol_compliance():
    class DummyStage:
        name = "download"
        def run(self, ctx: JobContext) -> StageResult:
            return StageResult()
    stage: Stage = DummyStage()
    assert stage.name == "download"
