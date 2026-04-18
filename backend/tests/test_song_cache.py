from pathlib import Path
import numpy as np
import soundfile as sf
from app.sfx_extract.song_cache import (
    LocalFileSongCache, cache_key, normalize,
)

SR = 44100


def _make_wav(path: Path, dur_s: float = 2.0):
    sf.write(str(path), np.zeros((int(SR * dur_s), 2), dtype=np.float32), SR)


def test_normalize_case_and_punctuation():
    assert normalize("Boney M.") == "boney m"
    assert normalize("BONEY   M!!!") == "boney m"
    assert normalize("  Rasputin (Instrumental) ") == "rasputin instrumental"


def test_cache_key_stable_across_variations():
    # Different casing and punctuation → same cache key.
    k1 = cache_key("Boney M.", "Rasputin (Instrumental)")
    k2 = cache_key("BONEY M!", "rasputin instrumental")
    assert k1 == k2


def test_cache_key_differs_by_title():
    assert cache_key("Artist", "Song A") != cache_key("Artist", "Song B")


def test_get_returns_none_when_missing(tmp_path: Path):
    cache = LocalFileSongCache(tmp_path)
    assert cache.get("Boney M.", "Rasputin") is None


def test_put_then_get_roundtrip(tmp_path: Path):
    src = tmp_path / "src.wav"
    _make_wav(src, 5.0)
    cache = LocalFileSongCache(tmp_path / "cache")
    entry = cache.put("Boney M.", "Rasputin (Instrumental)", src, source="ig", duration_s=5.0)

    assert entry.source == "ig"
    assert entry.duration_s == 5.0
    assert Path(entry.audio_path).exists()

    # Different casing → same entry returned.
    hit = cache.get("BONEY  m!", "rasputin (instrumental)")
    assert hit is not None
    assert hit.cache_key == entry.cache_key
    assert Path(hit.audio_path).exists()


def test_put_overwrites_existing(tmp_path: Path):
    src1 = tmp_path / "a.wav"
    src2 = tmp_path / "b.wav"
    _make_wav(src1, 2.0)
    sf.write(str(src2), np.ones((SR * 3, 2), dtype=np.float32) * 0.5, SR)
    cache = LocalFileSongCache(tmp_path / "cache")

    cache.put("A", "B", src1, source="yt", duration_s=2.0)
    cache.put("A", "B", src2, source="yt", duration_s=3.0)

    hit = cache.get("A", "B")
    assert hit is not None
    assert hit.duration_s == 3.0
    # The file should now contain the second audio's content.
    data, _ = sf.read(hit.audio_path)
    assert data.max() > 0.4  # src2 was 0.5


def test_cache_hit_across_fresh_instance(tmp_path: Path):
    """Simulate a process restart — cache on disk should survive."""
    src = tmp_path / "s.wav"
    _make_wav(src, 1.0)
    base = tmp_path / "persist"
    LocalFileSongCache(base).put("X", "Y", src, source="ig", duration_s=1.0)

    # Fresh instance, same base.
    cache2 = LocalFileSongCache(base)
    hit = cache2.get("X", "Y")
    assert hit is not None
    assert hit.artist == "X"
