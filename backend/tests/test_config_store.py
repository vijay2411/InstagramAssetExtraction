import json
from pathlib import Path
import pytest
from app.storage.config_store import Config, ConfigStore, FileConfigStore, DEFAULT_CONFIG

def test_default_config_has_expected_fields():
    assert DEFAULT_CONFIG.output_base_dir
    assert DEFAULT_CONFIG.demucs_model == "htdemucs_ft"
    assert DEFAULT_CONFIG.demucs_device in ("mps", "cpu")
    assert DEFAULT_CONFIG.sfx_min_cluster_size == 2
    assert DEFAULT_CONFIG.sfx_clip_min_ms == 300
    assert DEFAULT_CONFIG.sfx_clip_max_ms == 1500

def test_file_config_store_loads_defaults_when_missing(tmp_path: Path):
    store = FileConfigStore(tmp_path / "config.json")
    cfg = store.load()
    assert cfg.demucs_model == "htdemucs_ft"

def test_file_config_store_saves_and_loads(tmp_path: Path):
    p = tmp_path / "config.json"
    store = FileConfigStore(p)
    cfg = store.load()
    cfg.sfx_min_cluster_size = 3
    store.save(cfg)
    store2 = FileConfigStore(p)
    cfg2 = store2.load()
    assert cfg2.sfx_min_cluster_size == 3

def test_file_config_store_partial_update(tmp_path: Path):
    p = tmp_path / "config.json"
    store = FileConfigStore(p)
    store.update({"demucs_device": "cpu"})
    cfg = store.load()
    assert cfg.demucs_device == "cpu"
    assert cfg.demucs_model == "htdemucs_ft"

def test_file_config_store_expands_tilde(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = tmp_path / "config.json"
    store = FileConfigStore(p)
    store.update({"output_base_dir": "~/my-assets"})
    cfg = store.load()
    assert cfg.output_base_dir == str(tmp_path / "my-assets")
