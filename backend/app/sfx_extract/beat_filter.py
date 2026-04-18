"""
Beat-grid filter for SFX onset candidates.

The problem: after spectral subtraction, the residual still contains drum
transients that leaked through from phase/master mismatches with the
reference. librosa's onset detector fires on those leaked drum hits.
MFCC clustering then merges them into one giant "SFX" cluster that's
really just the song's own kick/snare pattern.

The idea: creator-added SFX almost always land on video cuts, which are
off-beat relative to the song's rhythm. Drums (leaked residue) land
on-beat by definition. So: detect the song's beat grid, and keep only
onsets that are NOT near a beat.

Input to find_beats() is the ORIGINAL music.wav (pre-subtraction), since
that has the cleanest rhythm signal — residuals are too smeared for
reliable tempo detection.

Skips filtering entirely when beat confidence is too low (ambient tracks,
spoken word, very quiet mixes) so we don't silently throw away good SFX
on non-rhythmic content.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import librosa


DEFAULT_SR = 22050
DEFAULT_HOP = 512
# ±40 ms around a beat is the standard "on-beat" window in MIR literature.
# Tight enough to reject leaked drum hits, loose enough to tolerate IG
# re-encoding jitter (typically <20 ms) + subtraction-induced time smear.
DEFAULT_TOLERANCE_S = 0.04
# Mean onset-strength threshold below which we consider the track
# arrhythmic and skip filtering. Empirically: percussive pop music sits
# at 2+, pads/ambient sit at <0.5.
MIN_BEAT_STRENGTH = 0.5


@dataclass
class BeatGrid:
    tempo_bpm: float
    beat_times_s: np.ndarray    # detected downbeats (librosa.beat.beat_track)
    onset_times_s: np.ndarray   # EVERY onset in the music (drums, notes, etc.)
    confidence: float           # mean onset-strength at the detected beats
    has_beat: bool              # True if confidence >= MIN_BEAT_STRENGTH


def find_beats(wav_path: Path, sr: int = DEFAULT_SR, hop: int = DEFAULT_HOP) -> BeatGrid:
    """Detect beats + all onsets in an audio file. Returns a BeatGrid.

    The `onset_times_s` is the more useful reject grid for filtering residual
    SFX candidates: every drum/snare/hat hit in the source music produces an
    onset there, and ideally the same position shows a leaked onset in the
    residual we want to reject. beat_times_s is kept for tempo display only.

    When the track is arrhythmic (no strong beats at all), has_beat is False
    and callers should skip filtering — most mid-track SFX would land near
    some onset by chance and get wrongly rejected."""
    y, _ = librosa.load(str(wav_path), sr=sr, mono=True)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, hop_length=hop,
    )
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)

    # Also grab EVERY onset in the music. These are the real reject grid.
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr, hop_length=hop, backtrack=True,
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop)

    if len(beat_frames) > 0:
        confidence = float(onset_env[beat_frames].mean())
    else:
        confidence = 0.0

    tempo_f = float(np.asarray(tempo).flatten()[0]) if np.asarray(tempo).size else 0.0

    return BeatGrid(
        tempo_bpm=tempo_f,
        beat_times_s=beat_times,
        onset_times_s=onset_times,
        confidence=confidence,
        has_beat=confidence >= MIN_BEAT_STRENGTH and len(beat_times) > 1,
    )


def off_beat_mask(
    onsets_s: np.ndarray,
    beat_times_s: np.ndarray,
    tolerance_s: float = DEFAULT_TOLERANCE_S,
) -> np.ndarray:
    """Return a boolean mask over onsets_s; True = off-beat (keep).

    Callers that want just the times can do onsets_s[mask]; callers with
    parallel arrays (like the SfxStage's onset sample-indices) use the mask
    to filter their own data without floating-point matching games.
    """
    if len(beat_times_s) == 0:
        return np.ones(len(onsets_s), dtype=bool)
    onsets = np.asarray(onsets_s, dtype=float)
    beats = np.asarray(beat_times_s, dtype=float)

    # For each onset, find the insertion point in the sorted beats array.
    # The nearest beat is either at that index or index-1.
    idx = np.searchsorted(beats, onsets)
    idx_left = np.clip(idx - 1, 0, len(beats) - 1)
    idx_right = np.clip(idx, 0, len(beats) - 1)
    dist_left = np.abs(onsets - beats[idx_left])
    dist_right = np.abs(onsets - beats[idx_right])
    nearest_dist = np.minimum(dist_left, dist_right)
    return nearest_dist > tolerance_s


def filter_off_beat(
    onsets_s: np.ndarray,
    beat_times_s: np.ndarray,
    tolerance_s: float = DEFAULT_TOLERANCE_S,
) -> np.ndarray:
    """Back-compat wrapper: returns only the kept onset times."""
    onsets = np.asarray(onsets_s, dtype=float)
    return onsets[off_beat_mask(onsets, beat_times_s, tolerance_s)]


def apply_beat_filter(
    onsets_s: np.ndarray,
    beat_reference_path: Path,
    tolerance_s: float = DEFAULT_TOLERANCE_S,
) -> tuple[np.ndarray, BeatGrid]:
    """Convenience: run find_beats on the reference, filter onsets.
    Returns (kept_onsets, beat_grid). If beat_grid.has_beat is False, the
    original onsets are returned unchanged."""
    grid = find_beats(beat_reference_path)
    if not grid.has_beat:
        return np.asarray(onsets_s), grid
    kept = filter_off_beat(onsets_s, grid.beat_times_s, tolerance_s=tolerance_s)
    return kept, grid
