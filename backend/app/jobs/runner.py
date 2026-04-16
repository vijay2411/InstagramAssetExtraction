from __future__ import annotations
import asyncio
import threading
from pathlib import Path
from app.pipeline.cli import build_default_stages
from app.pipeline.orchestrator import Orchestrator
from app.storage.job_store import InMemoryJobStore, JobStatus
from app.ws.event_bus import EventBus
from app.storage.config_store import FileConfigStore

class JobRunner:
    """
    Runs a pipeline in a background thread and bridges its sync `emit` callback
    back into the FastAPI asyncio event loop via run_coroutine_threadsafe.

    The event loop MUST be passed in (captured by the caller via
    asyncio.get_running_loop()). Do not try to grab the loop inside this thread —
    threads don't have a default running loop.
    """
    # Module-level registries so cancel() works across requests with a fresh
    # JobRunner instance (cheap, keyed by job_id).
    _cancel_events: dict[str, threading.Event] = {}
    _threads: dict[str, threading.Thread] = {}

    def __init__(
        self,
        job_store: InMemoryJobStore,
        event_bus: EventBus,
        config_store: FileConfigStore,
        loop: asyncio.AbstractEventLoop,
    ):
        self.jobs = job_store
        self.bus = event_bus
        self.config = config_store
        self.loop = loop

    def start(self, job_id: str, url: str, job_dir: Path) -> None:
        cancel_event = threading.Event()
        JobRunner._cancel_events[job_id] = cancel_event
        loop = self.loop

        def emit(event: dict):
            asyncio.run_coroutine_threadsafe(self.bus.publish(job_id, event), loop)
            if event.get("type") == "stage.start":
                self.jobs.set_current_stage(job_id, event["stage"])
                self.jobs.set_status(job_id, JobStatus.RUNNING)
            elif event.get("type") == "job.done":
                self.jobs.set_status(job_id, JobStatus.DONE)
            elif event.get("type") == "job.error":
                self.jobs.set_status(job_id, JobStatus.ERROR, error=event.get("message"))
            elif event.get("type") == "job.canceled":
                self.jobs.set_status(job_id, JobStatus.CANCELED)

        cfg = self.config.load()

        def _run():
            orch = Orchestrator(
                stages=build_default_stages(),
                emit=emit,
                cancel_event=cancel_event,
            )
            orch.run(
                job_id=job_id,
                job_dir=job_dir,
                params={
                    "url": url,
                    "source_url": url,
                    "device": cfg.demucs_device,
                    "model": cfg.demucs_model,
                    "min_cluster_size": cfg.sfx_min_cluster_size,
                    "clip_min_ms": cfg.sfx_clip_min_ms,
                    "clip_max_ms": cfg.sfx_clip_max_ms,
                },
            )

        t = threading.Thread(target=_run, daemon=True)
        JobRunner._threads[job_id] = t
        t.start()

    @classmethod
    def cancel(cls, job_id: str) -> bool:
        ev = cls._cancel_events.get(job_id)
        if ev:
            ev.set()
            return True
        return False
