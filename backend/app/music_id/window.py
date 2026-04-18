"""
Pick the most music-rich window of a WAV for fingerprinting.

Heuristic: slide a fixed-size window (default 20s) across the track,
compute RMS energy in each window, and return the loudest one. Skip
the first `skip_s` seconds to avoid intros/silence. If the track is
shorter than the window, return the whole track.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import soundfile as sf


def pick_best_window(
    wav_path: Path,
    window_s: float = 20.0,
    stride_s: float = 2.0,
    skip_s: float = 3.0,
) -> tuple[float, float]:
    """Return (start_s, end_s) of the highest-RMS window in wav_path."""
    info = sf.info(str(wav_path))
    sr = info.samplerate
    duration = info.frames / sr

    if duration <= window_s:
        return (0.0, duration)

    # Load mono for the energy analysis. Downmix if stereo.
    audio, _ = sf.read(str(wav_path), always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)

    window_n = int(window_s * sr)
    stride_n = int(stride_s * sr)
    skip_n = min(int(skip_s * sr), len(audio) - window_n)

    best_start = skip_n
    best_rms = -1.0

    pos = skip_n
    while pos + window_n <= len(audio):
        chunk = audio[pos:pos + window_n]
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms > best_rms:
            best_rms = rms
            best_start = pos
        pos += stride_n

    start_s = best_start / sr
    end_s = min(start_s + window_s, duration)
    return (start_s, end_s)


def cut_window(
    src_path: Path,
    dst_path: Path,
    start_s: float,
    end_s: float,
    gain: float = 1.0,
) -> None:
    """Write the [start_s, end_s) slice of src_path to dst_path.

    If `gain` != 1.0, the slice is multiplied by `gain` and hard-clipped to
    [-1, 1] before writing. Used so AudD receives the amplified clip that
    matches what the user is hearing.
    """
    audio, sr = sf.read(str(src_path), always_2d=True)
    s = max(0, int(start_s * sr))
    e = min(len(audio), int(end_s * sr))
    slice_ = audio[s:e]
    if gain != 1.0:
        slice_ = np.clip(slice_ * float(gain), -1.0, 1.0)
    sf.write(str(dst_path), slice_, sr)
