from __future__ import annotations
import asyncio
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import get_job_store, get_event_bus, get_asset_storage, get_config_store
from app.storage.job_store import InMemoryJobStore
from app.storage.asset_storage import LocalAssetStorage
from app.ws.event_bus import EventBus
from app.storage.config_store import FileConfigStore
from app.jobs.runner import JobRunner

router = APIRouter(prefix="/jobs", tags=["jobs"])

class CreateJobRequest(BaseModel):
    url: str

def _run_pipeline_async(
    job_id: str, url: str, job_dir: Path,
    jobs: InMemoryJobStore, bus: EventBus, config: FileConfigStore,
    loop: asyncio.AbstractEventLoop,
):
    """Indirection that tests can monkeypatch to no-op."""
    JobRunner(jobs, bus, config, loop).start(job_id, url, job_dir)

@router.post("", status_code=201)
async def create_job(
    req: CreateJobRequest,
    jobs: InMemoryJobStore = Depends(get_job_store),
    bus: EventBus = Depends(get_event_bus),
    storage: LocalAssetStorage = Depends(get_asset_storage),
    config: FileConfigStore = Depends(get_config_store),
):
    if jobs.get_current() is not None:
        raise HTTPException(409, "a job is already running")
    loop = asyncio.get_running_loop()
    state = jobs.create(url=req.url, job_dir="(pending)")
    job_dir = storage.create_job_dir(job_id=state.job_id, slug=_slug_from_url(req.url))
    state.job_dir = str(job_dir)
    _run_pipeline_async(state.job_id, req.url, job_dir, jobs, bus, config, loop)
    return {"job_id": state.job_id, "job_dir": str(job_dir)}

@router.get("/current")
def get_current(jobs: InMemoryJobStore = Depends(get_job_store)):
    state = jobs.get_current()
    if state is None:
        raise HTTPException(404, "no active job")
    return {
        "job_id": state.job_id,
        "url": state.url,
        "status": state.status.value,
        "current_stage": state.current_stage,
        "job_dir": state.job_dir,
    }

@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, jobs: InMemoryJobStore = Depends(get_job_store)):
    if jobs.get(job_id) is None:
        raise HTTPException(404, "job not found")
    ok = JobRunner.cancel(job_id)
    return {"ok": ok}

def _slug_from_url(url: str) -> str:
    seg = url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^a-zA-Z0-9]+", "-", seg.lower())[:40] or "job"
