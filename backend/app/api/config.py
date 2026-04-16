from fastapi import APIRouter, Depends
from dataclasses import asdict
from app.deps import get_config_store
from app.storage.config_store import FileConfigStore

router = APIRouter(prefix="/config", tags=["config"])

@router.get("")
def get_config(store: FileConfigStore = Depends(get_config_store)):
    return asdict(store.load())

@router.put("")
def put_config(patch: dict, store: FileConfigStore = Depends(get_config_store)):
    cfg = store.update(patch)
    return asdict(cfg)
