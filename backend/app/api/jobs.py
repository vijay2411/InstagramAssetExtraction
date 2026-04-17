from __future__ import annotations
import asyncio
import json
import re
from dataclasses import asdict
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import get_job_store, get_event_bus, get_asset_storage, get_config_store
from app.storage.job_store import InMemoryJobStore
from app.storage.asset_storage import LocalAssetStorage
from app.ws.event_bus import EventBus
from app.storage.config_store import FileConfigStore
from app.jobs.runner import JobRunner
from app.music_id.audd import identify as audd_identify, AudDError
from app.music_id.window import pick_best_window, cut_window
from app.music_id.links import youtube_search_url

router = APIRouter(prefix="/jobs", tags=["jobs"])

class CreateJobRequest(BaseModel):
    url: str

class IdentifyMusicRequest(BaseModel):
    start_s: float | None = None  # auto-pick if omitted
    window_s: float = 20.0

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


@router.post("/{job_id}/identify-music")
def identify_music(
    job_id: str,
    req: IdentifyMusicRequest,
    jobs: InMemoryJobStore = Depends(get_job_store),
    config: FileConfigStore = Depends(get_config_store),
):
    """
    Run AudD fingerprint against a window of the job's music.wav. If start_s
    is null, we auto-pick the highest-RMS window. Result is cached per
    (job_id, start_s, window_s) in music_match.json.
    """
    state = jobs.get(job_id)
    if state is None:
        raise HTTPException(404, "job not found")
    job_dir = Path(state.job_dir)
    music_path = job_dir / "music.wav"
    if not music_path.exists():
        raise HTTPException(409, "music.wav not available yet — pipeline may not be done")

    cfg = config.load()
    if not cfg.audd_api_key:
        raise HTTPException(400, "AudD API key not configured — set audd_api_key in Settings")

    # Pick window: explicit from request or auto.
    if req.start_s is None:
        start_s, end_s = pick_best_window(music_path, window_s=req.window_s)
        auto = True
    else:
        start_s = float(req.start_s)
        end_s = start_s + float(req.window_s)
        auto = False

    clip_path = job_dir / f"_music_clip_{int(start_s)}_{int(end_s)}.wav"
    cut_window(music_path, clip_path, start_s, end_s)

    try:
        match = audd_identify(clip_path, api_key=cfg.audd_api_key)
    except AudDError as e:
        raise HTTPException(502, f"AudD error: {e}")
    finally:
        # Clean up the intermediate clip — we don't need to keep it.
        try:
            clip_path.unlink(missing_ok=True)
        except Exception:
            pass

    response: dict = {
        "matched": match is not None,
        "window": {"start_s": round(start_s, 2), "end_s": round(end_s, 2), "auto": auto},
    }
    if match is not None:
        match_dict = asdict(match)
        # Fill in YouTube search link (AudD doesn't return YT directly).
        match_dict["youtube_url"] = youtube_search_url(match.title, match.artist)
        response["song"] = match_dict
        # Persist so the frontend can reload without re-spending API calls.
        (job_dir / "music_match.json").write_text(json.dumps(response, indent=2))

    return response
