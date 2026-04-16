from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Protocol

class AssetNotFound(Exception): pass
class PathTraversal(Exception): pass

def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9-]+", "-", s.lower()).strip("-")
    return (s or "untitled")[:40]

class AssetStorage(Protocol):
    def create_job_dir(self, job_id: str, slug: str) -> Path: ...
    def resolve(self, job_dir_name: str, relpath: str) -> Path: ...

class LocalAssetStorage:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_job_dir(self, job_id: str, slug: str) -> Path:
        date = datetime.utcnow().strftime("%Y-%m-%d")
        name = f"{date}_{_slugify(slug)}_{job_id[:6]}"
        p = self.base_dir / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def resolve(self, job_dir_name: str, relpath: str) -> Path:
        job_dir = (self.base_dir / job_dir_name).resolve()
        if not job_dir.exists() or not job_dir.is_dir():
            raise AssetNotFound(job_dir_name)
        target = (job_dir / relpath).resolve()
        try:
            target.relative_to(job_dir)
        except ValueError:
            raise PathTraversal(relpath)
        return target
