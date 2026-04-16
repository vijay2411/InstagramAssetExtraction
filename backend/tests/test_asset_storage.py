from pathlib import Path
import pytest
from app.storage.asset_storage import LocalAssetStorage, AssetNotFound, PathTraversal

def test_create_job_dir_returns_path(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    p = s.create_job_dir(job_id="abc", slug="reel-demo")
    assert p.exists()
    assert p.parent == tmp_path
    assert "abc" in p.name
    assert "reel-demo" in p.name

def test_resolve_within_job_dir(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    p = s.create_job_dir(job_id="abc", slug="x")
    (p / "foo.wav").write_bytes(b"data")
    resolved = s.resolve(p.name, "foo.wav")
    assert resolved == p / "foo.wav"

def test_resolve_nested_subpath(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    p = s.create_job_dir(job_id="abc", slug="x")
    (p / "sfx").mkdir()
    (p / "sfx" / "sfx_01.wav").write_bytes(b"d")
    resolved = s.resolve(p.name, "sfx/sfx_01.wav")
    assert resolved == p / "sfx" / "sfx_01.wav"

def test_resolve_rejects_traversal(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    p = s.create_job_dir(job_id="abc", slug="x")
    with pytest.raises(PathTraversal):
        s.resolve(p.name, "../../etc/passwd")

def test_resolve_raises_on_missing_job(tmp_path: Path):
    s = LocalAssetStorage(base_dir=tmp_path)
    with pytest.raises(AssetNotFound):
        s.resolve("nonexistent", "foo.wav")
