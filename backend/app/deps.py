"""FastAPI dependency providers. Replace these in tests to swap impls."""
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from app.storage.config_store import FileConfigStore
from app.storage.job_store import InMemoryJobStore
from app.storage.asset_storage import LocalAssetStorage
from app.ws.event_bus import EventBus
from app.core.user_context import DefaultUserContext

CONFIG_PATH = Path("~/.extract-assets/config.json").expanduser()

@lru_cache(maxsize=1)
def get_config_store() -> FileConfigStore:
    return FileConfigStore(CONFIG_PATH)

@lru_cache(maxsize=1)
def get_job_store() -> InMemoryJobStore:
    return InMemoryJobStore()

@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    return EventBus()

def get_asset_storage() -> LocalAssetStorage:
    cfg = get_config_store().load()
    return LocalAssetStorage(Path(cfg.output_base_dir).expanduser())

def get_user_context() -> DefaultUserContext:
    return DefaultUserContext()
