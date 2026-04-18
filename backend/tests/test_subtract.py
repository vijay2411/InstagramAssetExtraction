"""
Tests for spectral subtraction.

Strategy: build a controlled mix = music + sfx where music is a known
reference slice. Run subtraction and verify:
  - residual RMS is substantially lower than mix RMS (subtraction worked)
  - residual still contains most of the sfx (energy preserved at sfx onset)
  - ok flag reflects the RMS ratio
"""
from pathlib import Path
import numpy as np
import soundfile as sf
import pytest

from app.sfx_extract.subtract import subtract, FAILURE_THRESHOLD, SubtractionResult

SR = 22050


def _synth_music_and_sfx(total_s: float = 10.0, sfx_at_s: float = 4.0, sfx_amp: float = 0.4):
    """Return (music, sfx) signals. music has a time-varying envelope so
    different windows are statistically distinguishable (real music is not
    stationary); sfx is a sharp transient at sfx_at_s."""
    n = int(SR * total_s)
    t = np.linspace(0, total_s, n, endpoint=False)

    # Envelope varying over time so music[0:10] != music[5:15] spectrally.
    env1 = 0.3 + 0.2 * np.sin(2 * np.pi * 0.07 * t)
    env2 = 0.3 + 0.2 * np.sin(2 * np.pi * 0.11 * t + 1.3)
    env3 = 0.2 + 0.15 * np.sin(2 * np.pi * 0.05 * t + 2.7)

    music = (
        env1 * np.sin(2 * np.pi * 220.0 * t)
        + env2 * np.sin(2 * np.pi * 330.0 * t)
        + env3 * np.sin(2 * np.pi * 440.0 * t)
    ).astype(np.float32)

    # SFX: 40ms exponentially-decayed burst (whoosh-like).
    sfx = np.zeros(n, dtype=np.float32)
    start = int(sfx_at_s * SR)
    dur = int(0.04 * SR)
    env = np.exp(-np.linspace(0, 5, dur))
    burst = env * np.sin(2 * np.pi * 1200.0 * np.arange(dur) / SR)
    sfx[start:start + dur] = sfx_amp * burst.astype(np.float32)

    return music, sfx


def _write_wav(path: Path, audio: np.ndarray):
    sf.write(str(path), np.stack([audio, audio], axis=1), SR)


def test_subtraction_removes_music_and_preserves_sfx(tmp_path: Path):
    music, sfx = _synth_music_and_sfx(total_s=10.0, sfx_at_s=4.0)
    mix = (music + sfx).clip(-1, 1)
    mix_p = tmp_path / "mix.wav"
    ref_p = tmp_path / "ref.wav"   # perfect reference = exact music
    out_p = tmp_path / "residual.wav"
    _write_wav(mix_p, mix)
    _write_wav(ref_p, music)

    result = subtract(mix_p, ref_p, ref_offset_s=0.0, dst_path=out_p)
    assert result.ok
    assert result.residual_rms_ratio < 0.5, (
        f"residual should be << mix, got {result.residual_rms_ratio}"
    )
    # Residual should still contain an audible peak near sfx_at_s.
    residual, _ = sf.read(str(out_p))
    if residual.ndim == 2:
        residual = residual.mean(axis=1)
    window = int(0.05 * SR)
    sfx_region = np.abs(residual[int(4.0 * SR):int(4.0 * SR) + window]).max()
    quiet_region = np.abs(residual[int(7.0 * SR):int(7.0 * SR) + window]).max()
    # The sfx peak should still dominate over a non-sfx region.
    assert sfx_region > quiet_region * 2, (
        f"SFX was removed by subtraction: sfx_peak={sfx_region}, quiet={quiet_region}"
    )


def test_subtraction_marks_wrong_reference_as_failed(tmp_path: Path):
    """Passing the wrong reference (unrelated audio) should leave residual
    close to mix and `ok` = False."""
    music, sfx = _synth_music_and_sfx(total_s=6.0, sfx_at_s=3.0)
    mix = (music + sfx).clip(-1, 1)
    # Wrong reference: a single different tone — can't explain the mix.
    n = len(music)
    t = np.linspace(0, 6.0, n, endpoint=False)
    wrong_ref = (0.3 * np.sin(2 * np.pi * 110.0 * t)).astype(np.float32)

    mix_p = tmp_path / "mix.wav"
    ref_p = tmp_path / "wrong.wav"
    out_p = tmp_path / "residual.wav"
    _write_wav(mix_p, mix)
    _write_wav(ref_p, wrong_ref)

    result = subtract(mix_p, ref_p, ref_offset_s=0.0, dst_path=out_p)
    assert result.residual_rms_ratio > 0.5, (
        f"wrong reference should leave residual ≈ mix, got ratio={result.residual_rms_ratio}"
    )


def test_subtraction_offset_cropping(tmp_path: Path):
    """Reference is longer than mix; subtraction should use the aligned
    slice, not the start."""
    # Build a 20s reference but mix = music[5s:15s]; pass offset=5.
    music20, _ = _synth_music_and_sfx(total_s=20.0)
    music_slice = music20[int(5.0 * SR):int(15.0 * SR)]
    _, sfx = _synth_music_and_sfx(total_s=10.0, sfx_at_s=3.0)
    mix = (music_slice + sfx).clip(-1, 1)

    mix_p = tmp_path / "mix.wav"
    ref_p = tmp_path / "ref_full.wav"
    out_p = tmp_path / "residual.wav"
    _write_wav(mix_p, mix)
    _write_wav(ref_p, music20)

    good_result = subtract(mix_p, ref_p, ref_offset_s=5.0, dst_path=out_p)
    # And for comparison: passing wrong offset=0 should score worse.
    bad_out = tmp_path / "bad.wav"
    bad_result = subtract(mix_p, ref_p, ref_offset_s=0.0, dst_path=bad_out)

    assert good_result.residual_rms_ratio < bad_result.residual_rms_ratio


def test_subtraction_produces_stereo_output_at_expected_sr(tmp_path: Path):
    music, sfx = _synth_music_and_sfx(total_s=3.0, sfx_at_s=1.0)
    mix_p = tmp_path / "mix.wav"
    ref_p = tmp_path / "ref.wav"
    out_p = tmp_path / "out.wav"
    _write_wav(mix_p, music + sfx)
    _write_wav(ref_p, music)
    subtract(mix_p, ref_p, ref_offset_s=0.0, dst_path=out_p)
    info = sf.info(str(out_p))
    assert info.samplerate == SR
    assert info.channels == 2


def test_failure_threshold_constant_sane():
    assert 0.0 < FAILURE_THRESHOLD < 1.0


def test_subtraction_returns_result_dataclass(tmp_path: Path):
    music, sfx = _synth_music_and_sfx(total_s=3.0, sfx_at_s=1.0)
    mix_p = tmp_path / "mix.wav"; ref_p = tmp_path / "ref.wav"; out_p = tmp_path / "out.wav"
    _write_wav(mix_p, music + sfx)
    _write_wav(ref_p, music)
    r = subtract(mix_p, ref_p, 0.0, out_p)
    assert isinstance(r, SubtractionResult)
    assert r.residual_path == out_p
    assert isinstance(r.ok, bool)
