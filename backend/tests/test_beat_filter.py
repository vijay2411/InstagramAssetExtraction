"""
Tests for the beat-grid filter.

Strategy: synthesise audio with a known tempo (beats at 0.5s, 1.0s, 1.5s, …),
and a mix of onsets — some ON the beats, some clearly off-beat. The filter
should keep only the off-beat ones.
"""
from pathlib import Path
import numpy as np
import soundfile as sf

from app.sfx_extract.beat_filter import (
    find_beats,
    filter_off_beat,
    apply_beat_filter,
    MIN_BEAT_STRENGTH,
    DEFAULT_TOLERANCE_S,
)

SR = 22050


def _synth_120bpm_beats(dst: Path, total_s: float = 10.0):
    """120 BPM = beat every 0.5s. Place a sharp kick-drum-like click at
    each beat so librosa's beat tracker can lock on."""
    n = int(SR * total_s)
    audio = np.zeros(n, dtype=np.float32)
    # Soft harmonic bed so the track isn't pure silence between beats.
    t = np.linspace(0, total_s, n, endpoint=False)
    audio += 0.02 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    # Kicks on each beat.
    beat_period_s = 0.5
    beat = 0.0
    while beat < total_s:
        s = int(beat * SR)
        dur = int(0.05 * SR)
        env = np.exp(-np.linspace(0, 8, dur))
        burst = env * np.sin(2 * np.pi * 60 * np.arange(dur) / SR)
        audio[s:s + dur] += 0.8 * burst.astype(np.float32)
        beat += beat_period_s
    sf.write(str(dst), np.stack([audio, audio], axis=1), SR)


def _synth_ambient(dst: Path, total_s: float = 10.0):
    """Slow sustained pad — no detectable beat. find_beats should declare
    has_beat=False for this."""
    n = int(SR * total_s)
    t = np.linspace(0, total_s, n, endpoint=False)
    audio = (
        0.2 * np.sin(2 * np.pi * 220 * t) +
        0.15 * np.sin(2 * np.pi * 330 * t) +
        0.1 * np.sin(2 * np.pi * 440 * t)
    ).astype(np.float32)
    sf.write(str(dst), np.stack([audio, audio], axis=1), SR)


def test_find_beats_detects_120bpm(tmp_path: Path):
    p = tmp_path / "120bpm.wav"
    _synth_120bpm_beats(p, total_s=8.0)
    grid = find_beats(p)
    assert grid.has_beat, f"should detect a beat on 120bpm track, got confidence={grid.confidence}"
    assert abs(grid.tempo_bpm - 120.0) < 10, f"expected ~120 BPM, got {grid.tempo_bpm}"
    # Beats should land near 0, 0.5, 1.0, ... give ±80ms slop for libonset.
    assert len(grid.beat_times_s) >= 10
    gaps = np.diff(grid.beat_times_s)
    assert abs(gaps.mean() - 0.5) < 0.05, f"mean beat gap should be ~0.5s, got {gaps.mean()}"


def test_find_beats_marks_ambient_as_no_beat(tmp_path: Path):
    p = tmp_path / "ambient.wav"
    _synth_ambient(p, total_s=10.0)
    grid = find_beats(p)
    # Confidence is low on pure sustained tones — no percussive events at detected 'beats'.
    assert grid.confidence < MIN_BEAT_STRENGTH or not grid.has_beat, (
        f"ambient track should be flagged arrhythmic; confidence={grid.confidence} has_beat={grid.has_beat}"
    )


def test_filter_off_beat_keeps_only_off_beat_onsets():
    # Beats at 0.0, 0.5, 1.0, 1.5
    beats = np.array([0.0, 0.5, 1.0, 1.5])
    # Mix of onsets: two on-beat (within tolerance), three off-beat, one right at tolerance edge.
    onsets = np.array([
        0.01,    # ON beat 0 (1 cm)
        0.25,    # OFF — between beat 0 and 1
        0.48,    # ON beat 1 (20 ms before)
        0.70,    # OFF
        1.00,    # ON beat 2 exactly
        1.23,    # OFF
    ])
    kept = filter_off_beat(onsets, beats, tolerance_s=0.04)
    assert list(kept) == [0.25, 0.70, 1.23], kept


def test_filter_off_beat_handles_empty_beats():
    # Empty beat list = nothing to filter against; all onsets should pass.
    onsets = np.array([0.1, 0.2, 0.3])
    kept = filter_off_beat(onsets, np.array([]), tolerance_s=0.04)
    assert list(kept) == [0.1, 0.2, 0.3]


def test_filter_off_beat_handles_empty_onsets():
    kept = filter_off_beat(np.array([]), np.array([0.0, 0.5, 1.0]), tolerance_s=0.04)
    assert len(kept) == 0


def test_apply_beat_filter_passthrough_on_ambient(tmp_path: Path):
    """On an arrhythmic track, the filter should NOT discard any onsets."""
    ref = tmp_path / "ambient.wav"
    _synth_ambient(ref, total_s=8.0)
    onsets = np.array([0.1, 0.5, 1.0, 1.5, 2.0])
    kept, grid = apply_beat_filter(onsets, ref)
    assert not grid.has_beat
    assert len(kept) == len(onsets), "ambient should pass all onsets through"


def test_apply_beat_filter_removes_on_beat_onsets(tmp_path: Path):
    """Percussive 120bpm track: on-beat onsets should be dropped."""
    ref = tmp_path / "120bpm.wav"
    _synth_120bpm_beats(ref, total_s=8.0)
    grid = find_beats(ref)
    assert grid.has_beat

    # Build onsets that are deliberately on vs off the detected beats.
    beats = grid.beat_times_s
    # Take every second beat as on-beat, plus off-beat events midway between beats.
    on_beat = beats[::2]
    off_beat = (beats[:-1] + beats[1:]) / 2
    all_onsets = np.sort(np.concatenate([on_beat, off_beat]))
    kept, _ = apply_beat_filter(all_onsets, ref, tolerance_s=DEFAULT_TOLERANCE_S)
    # Off-beats (midpoints) should all survive; on-beats should all be rejected.
    for t in off_beat:
        assert any(abs(k - t) < 1e-6 for k in kept), f"off-beat onset {t:.3f}s was dropped"
    for t in on_beat:
        assert not any(abs(k - t) < 1e-6 for k in kept), f"on-beat onset {t:.3f}s survived"


def test_beat_grid_shape(tmp_path: Path):
    p = tmp_path / "x.wav"
    _synth_120bpm_beats(p, total_s=5.0)
    grid = find_beats(p)
    assert isinstance(grid.tempo_bpm, float)
    assert grid.beat_times_s.ndim == 1
    assert grid.confidence >= 0.0
    assert isinstance(grid.has_beat, bool)
