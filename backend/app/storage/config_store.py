from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import Protocol, Any

@dataclass
class Config:
    output_base_dir: str = "~/Desktop/assets"
    demucs_model: str = "htdemucs_ft"
    demucs_device: str = "mps"
    sfx_min_cluster_size: int = 2
    sfx_clip_min_ms: int = 300
    sfx_clip_max_ms: int = 1500

DEFAULT_CONFIG = Config()

def _expand(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("~"):
        return os.path.expanduser(value)
    return value

class ConfigStore(Protocol):
    def load(self) -> Config: ...
    def save(self, cfg: Config) -> None: ...
    def update(self, patch: dict[str, Any]) -> Config: ...

class FileConfigStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> Config:
        if not self.path.exists():
            return Config()
        data = json.loads(self.path.read_text())
        merged = asdict(Config())
        merged.update({k: _expand(v) for k, v in data.items() if k in merged})
        return Config(**merged)

    def save(self, cfg: Config) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(cfg), indent=2))

    def update(self, patch: dict[str, Any]) -> Config:
        cfg = self.load()
        valid = {f.name for f in fields(Config)}
        for k, v in patch.items():
            if k in valid:
                setattr(cfg, k, _expand(v))
        self.save(cfg)
        return cfg
