"""
Tests for the alignment module.

Strategy: synthesise a "reference" song (120s of sine-chord) and carve out a
known 20s slice as the "reel music". Alignment should recover the slice's
original offset to within ±1 hop.
"""
from pathlib import Path
import numpy as np
import soundfile as sf

from app.sfx_extract.align import align, align_best_of_candidates

SR = 22050  # match the module default to keep test fast


def _synthesise_reference(path: Path, total_s: float = 30.0, seed: int = 0):
    """Produce a reference track with percussive onsets at pseudo-random
    times — gives the onset-strength curve a distinctive 'fingerprint'
    that cross-correlation can latch onto."""
    rng = np.random.default_rng(seed)
    n = int(SR * total_s)
    audio = np.zeros(n, dtype=np.float32)

    # Base bed: quiet sustained chord so the signal isn't empty.
    t = np.linspace(0, total_s, n, endpoint=False)
    audio += 0.05 * np.sin(2 * np.pi * 220.0 * t).astype(np.float32)
    audio += 0.05 * np.sin(2 * np.pi * 330.0 * t).astype(np.float32)

    # Onset events: short percussive bursts at pseudo-random positions.
    onset_times = rng.uniform(0.1, total_s - 0.1, size=int(total_s * 3))  # ~3/s
    for onset_s in onset_times:
        start = int(onset_s * SR)
        dur = int(0.08 * SR)  # 80ms burst
        end = min(start + dur, n)
        env = np.exp(-np.linspace(0, 6, end - start))
        freq = float(rng.uniform(200, 2000))
        burst = env * np.sin(2 * np.pi * freq * np.arange(end - start) / SR)
        audio[start:end] += 0.4 * burst.astype(np.float32)

    audio = np.clip(audio, -1, 1)
    sf.write(str(path), np.stack([audio, audio], axis=1), SR)


def _slice_as_reel(src_path: Path, dst_path: Path, start_s: float, dur_s: float):
    """Cut [start_s, start_s + dur_s) from src into dst."""
    audio, sr = sf.read(str(src_path), always_2d=True)
    s = int(start_s * sr)
    e = s + int(dur_s * sr)
    sf.write(str(dst_path), audio[s:e], sr)


def test_align_finds_correct_offset_no_pitch(tmp_path: Path):
    ref = tmp_path / "ref.wav"
    reel = tmp_path / "reel.wav"
    _synthesise_reference(ref, total_s=30.0)
    _slice_as_reel(ref, reel, start_s=12.0, dur_s=8.0)

    result = align(reel, ref)
    assert abs(result.offset_s - 12.0) < 0.25, f"expected offset near 12s, got {result.offset_s}"
    # Exact slice should score well above the MIN_CONFIDENCE threshold.
    from app.sfx_extract.align import MIN_CONFIDENCE
    assert result.confidence > MIN_CONFIDENCE, f"expected strong confidence, got {result.confidence}"
    assert result.pitch_shift == 0


def test_align_matched_scores_higher_than_unrelated(tmp_path: Path):
    """Matched content should score meaningfully higher than unrelated
    noise. Absolute thresholds vary wildly between synthetic and real
    signals (see MIN_CONFIDENCE comments); the relative ordering is what's
    load-bearing for `align_best_of_candidates` picking correctly."""
    ref = tmp_path / "ref.wav"
    matched = tmp_path / "matched.wav"
    noise_reel = tmp_path / "noise.wav"
    _synthesise_reference(ref, total_s=30.0)
    _slice_as_reel(ref, matched, start_s=10.0, dur_s=6.0)
    # White noise as the "unrelated" content.
    noise = np.random.randn(int(SR * 6), 2).astype(np.float32) * 0.1
    sf.write(str(noise_reel), noise, SR)

    matched_r = align(matched, ref)
    noise_r = align(noise_reel, ref)
    assert matched_r.confidence > noise_r.confidence, (
        f"matched z={matched_r.confidence} should beat unrelated z={noise_r.confidence}"
    )


def test_align_best_of_candidates_picks_correct(tmp_path: Path):
    """Two candidates — one is the right song, one is unrelated. Picker
    should pick the right one."""
    right_ref = tmp_path / "right.wav"
    wrong_ref = tmp_path / "wrong.wav"
    reel = tmp_path / "reel.wav"
    _synthesise_reference(right_ref, total_s=30.0)
    # 'wrong_ref' is shifted version of a totally different chord set.
    t = np.linspace(0, 30.0, int(SR * 30.0), endpoint=False)
    other = 0.3 * np.sin(2 * np.pi * 110.0 * t)
    sf.write(str(wrong_ref), np.stack([other, other], axis=1).astype(np.float32), SR)
    _slice_as_reel(right_ref, reel, start_s=7.0, dur_s=6.0)

    idx, result = align_best_of_candidates(reel, [wrong_ref, right_ref])
    assert idx == 1, "should pick the right candidate"
    assert abs(result.offset_s - 7.0) < 0.25


def test_align_raises_when_reel_longer_than_reference(tmp_path: Path):
    short_ref = tmp_path / "short.wav"
    long_reel = tmp_path / "long.wav"
    _synthesise_reference(short_ref, total_s=5.0)
    _synthesise_reference(long_reel, total_s=20.0)
    import pytest
    with pytest.raises(ValueError, match="reel music is longer"):
        align(long_reel, short_ref)


def test_align_result_reports_hop_and_ref_duration(tmp_path: Path):
    ref = tmp_path / "r.wav"
    reel = tmp_path / "reel.wav"
    _synthesise_reference(ref, total_s=20.0)
    _slice_as_reel(ref, reel, start_s=3.0, dur_s=4.0)

    result = align(reel, ref)
    assert abs(result.reference_duration_s - 20.0) < 0.2
    assert 0 < result.hop_s < 0.1  # ~23 ms at 22050/512


def test_align_best_of_candidates_empty_list_raises(tmp_path: Path):
    reel = tmp_path / "reel.wav"
    _synthesise_reference(reel, total_s=2.0)
    import pytest
    with pytest.raises(ValueError, match="no candidates"):
        align_best_of_candidates(reel, [])
