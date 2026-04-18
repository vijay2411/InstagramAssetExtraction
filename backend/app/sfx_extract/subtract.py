"""
Spectral subtraction of a reference music track from a mix containing music + sfx.

Problem: reel-music.wav = scale(eq(reference[offset:offset+len])) + residue.
Direct time-domain subtraction fails because tiny phase offsets (< 1 ms) cause
the difference signal to be nearly as loud as the mix. Spectral subtraction
operates on magnitudes and keeps the mix's phase — standard noise-reduction
technique applied to a known-reference cancellation problem.

Algorithm:
  1. Load both signals at a common sample rate (22050 Hz — sufficient for
     music-bandwidth work and keeps STFT cheap).
  2. Crop reference to the aligned window (same length as mix).
  3. STFT both. Window 2048, hop 512.
  4. Estimate per-frequency-bin gain g(f) that best explains mix as
     g(f) * reference:
        g(f) = sum_t |mix(t,f)| * |ref(t,f)|  /  sum_t |ref(t,f)|^2
     This is the least-squares fit on magnitudes (EQ absorption).
  5. Compute residual magnitude:
        |residual(t,f)| = max(|mix(t,f)| - alpha * g(f) * |ref(t,f)|, beta * |mix(t,f)|)
     where alpha is an over-subtraction factor (~1.2) and beta is a noise
     floor (~0.05) to avoid killing genuine SFX energy entirely.
  6. Reconstruct: residual(t,f) with mix's phase, then ISTFT.

Output comes back as a stereo WAV matching the mix sample rate.

Subtraction quality depends heavily on alignment accuracy. If alignment is
off by > ~100ms the residue will still contain strong music. We measure
residual RMS / mix RMS and return it as a quality signal.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa


DEFAULT_SR = 22050
DEFAULT_N_FFT = 2048
DEFAULT_HOP = 512
DEFAULT_ALPHA = 1.2   # over-subtraction factor
DEFAULT_BETA = 0.05   # noise floor — retain at least this fraction of mix

# Subtraction fails cleanly if the residual is still louder than this fraction
# of the mix. 0.6 = "residual is 60%+ of mix" → alignment was off or wrong song.
FAILURE_THRESHOLD = 0.6


@dataclass
class SubtractionResult:
    residual_path: Path
    residual_rms_ratio: float   # residual RMS / mix RMS, 0..1
    ok: bool                    # residual_rms_ratio < FAILURE_THRESHOLD


def _load_mono(path: Path, sr: int) -> np.ndarray:
    y, _ = librosa.load(str(path), sr=sr, mono=True)
    return y


def _stft(y: np.ndarray, n_fft: int, hop: int) -> np.ndarray:
    return librosa.stft(y, n_fft=n_fft, hop_length=hop)


def _istft(spec: np.ndarray, hop: int, length: int) -> np.ndarray:
    return librosa.istft(spec, hop_length=hop, length=length)


def _fit_gain(mix_mag: np.ndarray, ref_mag: np.ndarray) -> np.ndarray:
    """Per-bin least-squares gain: g(f) = sum_t |m||r| / sum_t |r|^2.
    Returns an array of length n_bins."""
    num = (mix_mag * ref_mag).sum(axis=1)
    den = (ref_mag ** 2).sum(axis=1) + 1e-9
    return num / den


def subtract(
    mix_path: Path,
    ref_path: Path,
    ref_offset_s: float,
    dst_path: Path,
    sr: int = DEFAULT_SR,
    n_fft: int = DEFAULT_N_FFT,
    hop: int = DEFAULT_HOP,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
) -> SubtractionResult:
    """Subtract ref_path[ref_offset_s : ref_offset_s + mix_duration] from
    mix_path and write the residual to dst_path."""
    mix = _load_mono(mix_path, sr)
    ref_full = _load_mono(ref_path, sr)
    mix_len = len(mix)

    # Crop reference to the aligned window.
    s = max(0, int(ref_offset_s * sr))
    e = min(len(ref_full), s + mix_len)
    ref = ref_full[s:e]
    if len(ref) < mix_len:
        # Pad reference with zeros so shapes match (rare — only near ref end).
        ref = np.pad(ref, (0, mix_len - len(ref)))

    mix_spec = _stft(mix, n_fft, hop)
    ref_spec = _stft(ref, n_fft, hop)

    mix_mag = np.abs(mix_spec)
    ref_mag = np.abs(ref_spec)
    mix_phase = np.angle(mix_spec)

    gain = _fit_gain(mix_mag, ref_mag)[:, None]  # shape (n_bins, 1)
    residual_mag = np.maximum(
        mix_mag - alpha * gain * ref_mag,
        beta * mix_mag,
    )

    residual_spec = residual_mag * np.exp(1j * mix_phase)
    residual = _istft(residual_spec, hop, mix_len)

    # Quality metric: how much energy is left relative to the mix.
    mix_rms = float(np.sqrt(np.mean(mix ** 2))) or 1e-9
    res_rms = float(np.sqrt(np.mean(residual ** 2)))
    ratio = res_rms / mix_rms

    # Write stereo (duplicate mono).
    out = np.stack([residual, residual], axis=1).astype(np.float32)
    out = np.clip(out, -1.0, 1.0)
    sf.write(str(dst_path), out, sr)

    return SubtractionResult(
        residual_path=dst_path,
        residual_rms_ratio=ratio,
        ok=ratio < FAILURE_THRESHOLD,
    )
