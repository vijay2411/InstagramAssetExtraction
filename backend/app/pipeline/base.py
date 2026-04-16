from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, Any

StageName = str  # one of "download"|"audio"|"speech"|"sfx"|"music"|"finalize"

@dataclass
class StageEvent:
    """Emitted by a stage during run() via the emit callback."""
    type: str  # "progress"
    stage: StageName
    progress: float | None = None  # 0.0 - 1.0
    message: str | None = None

@dataclass
class JobContext:
    job_id: str
    job_dir: Path
    inputs: dict[str, Path] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    emit: Callable[[StageEvent], None] = lambda _e: None

@dataclass
class StageResult:
    artifacts: dict[str, Path] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

class Stage(Protocol):
    name: StageName
    def run(self, ctx: JobContext) -> StageResult: ...
