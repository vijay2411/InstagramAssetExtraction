from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.deps import get_asset_storage
from app.storage.asset_storage import LocalAssetStorage, AssetNotFound, PathTraversal

router = APIRouter(prefix="/assets", tags=["assets"])

@router.get("/{job_dir_name}/{path:path}")
def stream_asset(
    job_dir_name: str,
    path: str,
    storage: LocalAssetStorage = Depends(get_asset_storage),
):
    try:
        p = storage.resolve(job_dir_name, path)
    except PathTraversal:
        raise HTTPException(400, "invalid path")
    except AssetNotFound:
        raise HTTPException(404, "job not found")
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "asset not found")
    return FileResponse(p)
