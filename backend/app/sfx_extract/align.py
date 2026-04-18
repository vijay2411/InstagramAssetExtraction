"""
Align a short reel-music clip inside a full reference song.

Problem: reel-music.wav is ~15-60s of demucs-separated music. reference.wav
is a 3-4 minute YouTube download. Find the offset where the reel lives
inside the reference, even if the reel is pitched up for IG/TikTok Content
ID dodging (+2..+5 semitones is common).

Algorithm:
  1. Compute log-mel spectrograms at ~50 frames/s for both signals.
  2. For each pitch shift in the candidate set, shift the reel's mel bins
     (cheap approximation: roll the mel axis). Score = max of FFT-based
     cross-correlation between the reel's mean-over-bins frame curve and
     the reference's.
  3. Pick the (pitch, offset) with the highest peak-to-mean ratio.
     That ratio is the 'confidence' — > 3.0 is a strong match, < 2.0 is
     likely noise.

This is NOT exact-sample alignment — the mel hop (~20 ms) is the limit.
That's fine for spectral subtraction downstream since subtraction operates
on STFT frames anyway.

Pitch shift via mel-bin roll is an approximation; true pitch shift also
scales tempo. For the small ±5 semitone range we care about, it's close
enough to find the correct offset; the subtraction stage then re-fits EQ.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import librosa

DEFAULT_SR = 22050           # mel features don't benefit from 44.1k
DEFAULT_HOP = 512            # 22050/512 = ~43 frames/s
DEFAULT_N_MELS = 128
# Semitone range to search. Empirically covers IG/TikTok pitch-ups and minor
# pitch-downs. Going wider is cheap but rarely useful.
DEFAULT_PITCH_RANGE = tuple(range(-3, 6))  # -3..+5 inclusive = 9 shifts

# Z-score threshold above which an alignment is considered reliable.
# Empirical calibration:
#   - matched slice of a percussive reference: z ≈ 13-40
#   - unrelated white noise against a reference: z ≈ 4-7 (max-of-N variance)
#   - unrelated music against a reference: z ≈ 3-8
# 8.0 separates the two regimes with clear margin.
MIN_CONFIDENCE = 8.0


@dataclass
class AlignmentResult:
    offset_s: float            # start of the reel within the reference
    pitch_shift: int           # semitones the reel was shifted to match
    confidence: float          # peak-to-mean ratio; > 3.0 is a strong match
    reference_duration_s: float
    hop_s: float


def _load_mono(path: Path, sr: int) -> np.ndarray:
    y, _ = librosa.load(str(path), sr=sr, mono=True)
    return y


def _onset_curve(y: np.ndarray, sr: int, hop: int) -> np.ndarray:
    """Onset-strength envelope — one value per STFT frame, spikes on
    percussive / new-note events. Much more time-distinctive than
    mel-energy mean for music alignment."""
    return librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)


def _pitch_shift_audio(y: np.ndarray, sr: int, semitones: int) -> np.ndarray:
    """True pitch shift (preserves tempo) via librosa.effects.pitch_shift.
    Heavier than a mel-bin roll but accurate enough that the onset-curve
    downstream still lines up to the reference."""
    if semitones == 0:
        return y
    return librosa.effects.pitch_shift(y, sr=sr, n_steps=float(semitones))


def _cross_correlate_valid(short: np.ndarray, long: np.ndarray) -> np.ndarray:
    """Return cross-correlation of short inside long (mode='valid').
    Output length = len(long) - len(short) + 1. Peak index = offset in frames."""
    if short.size > long.size:
        return np.array([])
    return np.correlate(long, short, mode="valid")


def _z_confidence(corr: np.ndarray) -> tuple[int, float]:
    """Given a correlation array, return (peak_idx, z_score) where
    z_score = (peak - mean) / std. A z-score above ~5 is a strong match;
    below ~3 is noise."""
    if corr.size == 0:
        return 0, 0.0
    peak_idx = int(np.argmax(corr))
    peak = float(corr[peak_idx])
    mean = float(corr.mean())
    std = float(corr.std()) or 1e-9
    return peak_idx, (peak - mean) / std


def align(
    reel_music_path: Path,
    reference_path: Path,
    sr: int = DEFAULT_SR,
    hop: int = DEFAULT_HOP,
    pitch_range: tuple[int, ...] = DEFAULT_PITCH_RANGE,
) -> AlignmentResult:
    """Find the best (pitch, offset) for reel_music_path within reference_path.

    Uses onset-strength curves + z-score for peak significance. Confidence
    (z-score) >5 = strong match, 3-5 = plausible, <3 = likely unrelated.
    """
    reel_y = _load_mono(reel_music_path, sr)
    ref_y = _load_mono(reference_path, sr)
    hop_s = hop / sr
    ref_duration_s = len(ref_y) / sr

    if len(reel_y) > len(ref_y):
        raise ValueError("reel music is longer than reference song")

    ref_curve = _onset_curve(ref_y, sr, hop)

    best: AlignmentResult | None = None
    for semitones in pitch_range:
        shifted_y = _pitch_shift_audio(reel_y, sr, semitones)
        reel_curve = _onset_curve(shifted_y, sr, hop)

        # Mean-center so loudness differences don't dominate.
        r = reel_curve - reel_curve.mean()
        s = ref_curve - ref_curve.mean()

        corr = _cross_correlate_valid(r, s)
        peak_idx, z = _z_confidence(corr)
        if best is None or z > best.confidence:
            best = AlignmentResult(
                offset_s=peak_idx * hop_s,
                pitch_shift=semitones,
                confidence=z,
                reference_duration_s=ref_duration_s,
                hop_s=hop_s,
            )

    assert best is not None
    return best


def align_best_of_candidates(
    reel_music_path: Path,
    candidate_paths: list[Path],
    pitch_range: tuple[int, ...] = DEFAULT_PITCH_RANGE,
) -> tuple[int, AlignmentResult]:
    """Align against multiple reference candidates and return the index
    (into candidate_paths) with the highest confidence, plus its result."""
    if not candidate_paths:
        raise ValueError("no candidates to align against")

    best_i = 0
    best_result: AlignmentResult | None = None
    for i, path in enumerate(candidate_paths):
        try:
            result = align(reel_music_path, path, pitch_range=pitch_range)
        except Exception:
            continue
        if best_result is None or result.confidence > best_result.confidence:
            best_result = result
            best_i = i

    if best_result is None:
        raise RuntimeError("alignment failed for every candidate")
    return best_i, best_result
