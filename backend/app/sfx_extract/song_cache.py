"""
Song reference cache.

Problem: identifying "Boney M. – Rasputin" across 10 different reels shouldn't
re-download Rasputin 10 times. Cache keyed by normalized (artist, title) so
the same song matches regardless of case or punctuation.

Interface-first so the local-disk impl today can swap for S3/R2 when we
deploy. Same pattern as JobStore / AssetStorage.

Keys are derived purely from artist+title (not from the user, not from the
job). That means the cache is content-addressable and shares cleanly across
users when we go multi-tenant.
"""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Protocol


@dataclass
class CachedSong:
    """Metadata for a cached reference audio file."""
    cache_key: str
    artist: str
    title: str
    audio_path: str            # absolute path on disk (or URL when S3)
    source: str                # "ig" | "youtube" | ...
    duration_s: float
    downloaded_at: float       # unix timestamp
    # The original query used to fetch this — helps debug bad matches.
    query: str | None = None


def normalize(s: str) -> str:
    """Fold casing, strip punctuation, collapse spaces for robust cache keys."""
    s = (s or "").lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)   # drop punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s


def cache_key(artist: str, title: str) -> str:
    """Content-addressable key. Same input → same key forever."""
    normalized = f"{normalize(artist)}|{normalize(title)}"
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


class SongCache(Protocol):
    def get(self, artist: str, title: str) -> CachedSong | None: ...
    def put(
        self,
        artist: str,
        title: str,
        audio_src: Path,
        source: str,
        duration_s: float,
        query: str | None = None,
    ) -> CachedSong: ...


class LocalFileSongCache:
    """
    Disk-backed cache. Layout:

        base_dir/
          by-key/
            <key>.wav              # the audio
            <key>.json             # CachedSong metadata

    Atomic put: write to a temp name, rename into place. Read-through via get.
    """
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir) / "by-key"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _paths(self, key: str) -> tuple[Path, Path]:
        return (self.base_dir / f"{key}.wav", self.base_dir / f"{key}.json")

    def get(self, artist: str, title: str) -> CachedSong | None:
        key = cache_key(artist, title)
        audio_p, meta_p = self._paths(key)
        if not (audio_p.exists() and meta_p.exists()):
            return None
        try:
            data = json.loads(meta_p.read_text())
            # Adapt audio_path to current absolute location — cache might have
            # been moved / synced from another machine.
            data["audio_path"] = str(audio_p)
            return CachedSong(**data)
        except Exception:
            # Corrupt metadata — treat as miss; caller will re-cache.
            return None

    def put(
        self,
        artist: str,
        title: str,
        audio_src: Path,
        source: str,
        duration_s: float,
        query: str | None = None,
    ) -> CachedSong:
        key = cache_key(artist, title)
        audio_p, meta_p = self._paths(key)
        # Atomic copy: write to .tmp then rename so readers never see partial.
        tmp = audio_p.with_suffix(".wav.tmp")
        shutil.copyfile(audio_src, tmp)
        tmp.replace(audio_p)

        entry = CachedSong(
            cache_key=key,
            artist=artist,
            title=title,
            audio_path=str(audio_p),
            source=source,
            duration_s=float(duration_s),
            downloaded_at=time.time(),
            query=query,
        )
        meta_p.write_text(json.dumps(asdict(entry), indent=2))
        return entry
