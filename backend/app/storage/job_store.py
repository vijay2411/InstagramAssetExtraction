from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELED = "canceled"

@dataclass
class JobState:
    job_id: str
    url: str
    job_dir: str
    status: JobStatus = JobStatus.PENDING
    current_stage: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

class JobStore(Protocol):
    def create(self, url: str, job_dir: str) -> JobState: ...
    def get(self, job_id: str) -> JobState | None: ...
    def get_current(self) -> JobState | None: ...
    def set_status(self, job_id: str, status: JobStatus, error: str | None = None) -> None: ...
    def set_current_stage(self, job_id: str, stage: str) -> None: ...

ACTIVE = {JobStatus.PENDING, JobStatus.RUNNING}

class InMemoryJobStore:
    def __init__(self):
        self._jobs: dict[str, JobState] = {}

    def create(self, url: str, job_dir: str) -> JobState:
        if self.get_current() is not None:
            raise RuntimeError("a job is already running")
        job_id = uuid.uuid4().hex[:12]
        state = JobState(job_id=job_id, url=url, job_dir=job_dir)
        self._jobs[job_id] = state
        return state

    def get(self, job_id: str) -> JobState | None:
        return self._jobs.get(job_id)

    def get_current(self) -> JobState | None:
        for j in self._jobs.values():
            if j.status in ACTIVE:
                return j
        return None

    def set_status(self, job_id: str, status: JobStatus, error: str | None = None) -> None:
        job = self._jobs[job_id]
        job.status = status
        if error:
            job.error_message = error

    def set_current_stage(self, job_id: str, stage: str) -> None:
        self._jobs[job_id].current_stage = stage
