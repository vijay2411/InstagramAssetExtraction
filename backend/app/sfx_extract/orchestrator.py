"""
SFX extraction orchestrator.

Given a job that already has music.wav + a confirmed song (title + artist):
  1. Check cache for reference audio. If miss, download YouTube top-3.
  2. Align reel-music inside whichever candidate scores highest.
  3. Spectral subtraction → residual.wav (music + sfx) − reference = sfx-ish.
  4. Run existing SFX clustering on the residual (re-enables sfx_enabled=True
     just for this invocation so we reuse the battle-tested module).
  5. Update the job's metadata.json with the new SFX entries so the
     frontend picks them up.

Each step emits a progress event via the shared EventBus so the UI's
StageCards can animate. Bails cleanly on alignment failure or bad
subtraction, leaving the job's previous SFX entries untouched.
"""
from __future__ import annotations
import json
import shutil
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable

from app.sfx_extract.song_cache import SongCache, LocalFileSongCache
from app.sfx_extract.yt_download import fetch_top_candidates, YtDownloadError
from app.sfx_extract.align import align_best_of_candidates, MIN_CONFIDENCE, AlignmentResult
from app.sfx_extract.subtract import subtract, FAILURE_THRESHOLD
from app.pipeline.sfx import SfxStage
from app.pipeline.base import JobContext, StageEvent


Emit = Callable[[dict], None]


@dataclass
class ExtractResult:
    ok: bool
    stage_failed: str | None = None
    error: str | None = None
    sfx_count: int = 0
    cache_hit: bool = False
    alignment: AlignmentResult | None = None
    residual_rms_ratio: float | None = None


def _emit(emit: Emit | None, stage: str, progress: float, message: str = "") -> None:
    if emit:
        emit({"type": "sfx_extract.progress", "stage": stage, "progress": progress, "message": message})


def extract_sfx(
    job_dir: Path,
    artist: str,
    title: str,
    cache: SongCache,
    sfx_params: dict | None = None,
    emit: Emit | None = None,
) -> ExtractResult:
    """
    Run the full download → align → subtract → mine pipeline for a job.

    Inputs:
      job_dir: directory containing music.wav (and where outputs land)
      artist, title: identified song metadata
      cache: SongCache (looked up first, populated on miss)
      sfx_params: forwarded to SfxStage (min_cluster_size, clip_min_ms, etc.)
      emit: optional progress callback. Events have type
        'sfx_extract.progress' with stage in {'cache','download','align',
        'subtract','mine'} and progress 0..1.
    """
    music_path = job_dir / "music.wav"
    if not music_path.exists():
        return ExtractResult(ok=False, stage_failed="precheck", error="music.wav not found")

    # --- 1. Cache check ---
    _emit(emit, "cache", 0.0, f"checking cache for {artist} — {title}")
    cached = cache.get(artist, title)
    cache_hit = cached is not None
    if cache_hit:
        reference_path = Path(cached.audio_path)
        _emit(emit, "cache", 1.0, "cache hit — skipping download")
    else:
        # --- 2. Download top-3 from YouTube ---
        _emit(emit, "download", 0.0, "searching YouTube")
        try:
            download_dir = Path(tempfile.mkdtemp(prefix="yt_cands_", dir=str(job_dir)))
            candidates = fetch_top_candidates(artist, title, top_n=3, dst_dir=download_dir)
        except YtDownloadError as e:
            return ExtractResult(ok=False, stage_failed="download", error=str(e))
        _emit(emit, "download", 0.7, f"got {len(candidates)} candidates — picking best")

        # --- 3. Align (picks best candidate from the top-3) ---
        _emit(emit, "align", 0.0, "cross-correlating against reel music")
        candidate_paths = [c.audio_path for c in candidates]
        try:
            best_i, alignment = align_best_of_candidates(music_path, candidate_paths)
        except Exception as e:
            return ExtractResult(ok=False, stage_failed="align", error=str(e))

        if alignment.confidence < MIN_CONFIDENCE:
            return ExtractResult(
                ok=False, stage_failed="align",
                error=f"no candidate aligned reliably (best z-score={alignment.confidence:.1f}, threshold={MIN_CONFIDENCE})",
                alignment=alignment,
            )

        best_candidate = candidates[best_i]
        _emit(emit, "align", 1.0,
              f"matched {best_candidate.title[:40]} (z={alignment.confidence:.1f}, pitch {alignment.pitch_shift:+d})")

        # Populate cache for next time.
        cache.put(
            artist=artist,
            title=title,
            audio_src=best_candidate.audio_path,
            source="youtube",
            duration_s=best_candidate.duration_s,
            query=f"{artist} {title}",
        )
        reference_path = best_candidate.audio_path

    # --- 4. If cache hit, align once; otherwise we already aligned above. ---
    if cache_hit:
        _emit(emit, "align", 0.0, "aligning against cached reference")
        try:
            _, alignment = align_best_of_candidates(music_path, [reference_path])
        except Exception as e:
            return ExtractResult(ok=False, stage_failed="align", error=str(e))
        if alignment.confidence < MIN_CONFIDENCE:
            return ExtractResult(
                ok=False, stage_failed="align",
                error=f"cached reference doesn't align (z={alignment.confidence:.1f})",
                alignment=alignment,
            )
        _emit(emit, "align", 1.0, f"aligned (z={alignment.confidence:.1f}, pitch {alignment.pitch_shift:+d})")

    # --- 5. Spectral subtraction ---
    _emit(emit, "subtract", 0.0, "subtracting reference from mix")
    residual_path = job_dir / "sfx_residual.wav"
    sub_result = subtract(
        mix_path=music_path,
        ref_path=reference_path,
        ref_offset_s=alignment.offset_s,
        dst_path=residual_path,
    )
    if not sub_result.ok:
        return ExtractResult(
            ok=False, stage_failed="subtract",
            error=f"residual too loud (ratio={sub_result.residual_rms_ratio:.2f}) — alignment may be off",
            alignment=alignment,
            residual_rms_ratio=sub_result.residual_rms_ratio,
        )
    _emit(emit, "subtract", 1.0, f"residual RMS ratio {sub_result.residual_rms_ratio:.2f}")

    # --- 6. SFX mining on the residual ---
    _emit(emit, "mine", 0.0, "mining repeated SFX in residual")
    # Clean any old sfx/ clips from previous runs.
    sfx_dir = job_dir / "sfx"
    if sfx_dir.exists():
        shutil.rmtree(sfx_dir)

    # Reuse SfxStage but point it at the residual instead of non_speech.
    # Explicitly enable — the stage default is off because the naive
    # mining on the raw non_speech stem confuses drum hits as SFX, but
    # the residual here has already had the drums subtracted.
    params = dict(sfx_params or {})
    params.setdefault("sfx_enabled", True)
    params.setdefault("min_cluster_size", 2)
    params.setdefault("clip_min_ms", 300)
    params.setdefault("clip_max_ms", 1500)
    params.setdefault("cluster_dist_threshold", 0.35)

    ctx = JobContext(
        job_id="sfx-extract",
        job_dir=job_dir,
        inputs={"non_speech": residual_path},
        params=params,
        emit=lambda _e: None,  # swallow inner stage events; we emit our own
    )
    sfx_result = SfxStage().run(ctx)
    sfx_count = int(sfx_result.extra.get("sfx_count", 0))
    _emit(emit, "mine", 1.0, f"{sfx_count} sfx found")

    # --- 7. Update manifest so the frontend picks up the new SFX ---
    _update_manifest_with_sfx(job_dir)

    return ExtractResult(
        ok=True,
        sfx_count=sfx_count,
        cache_hit=cache_hit,
        alignment=alignment,
        residual_rms_ratio=sub_result.residual_rms_ratio,
    )


def _update_manifest_with_sfx(job_dir: Path) -> None:
    """Read sfx_clusters.json (just written by SfxStage) and fold the entries
    into metadata.json's assets.sfx array so the frontend sees them."""
    manifest_p = job_dir / "metadata.json"
    clusters_p = job_dir / "sfx_clusters.json"
    if not (manifest_p.exists() and clusters_p.exists()):
        return
    try:
        manifest = json.loads(manifest_p.read_text())
        clusters = json.loads(clusters_p.read_text())
    except Exception:
        return

    import soundfile as sf
    sfx_entries = []
    for c in clusters:
        rel = c["representative_path"]
        abs_p = job_dir / rel
        try:
            dur = float(sf.info(str(abs_p)).duration)
        except Exception:
            dur = 0.0
        sfx_entries.append({
            "path": rel,
            "duration": dur,
            "repeats": c["count"],
            "onset_times": c["onset_times_s"],
        })

    manifest.setdefault("assets", {})["sfx"] = sfx_entries
    manifest_p.write_text(json.dumps(manifest, indent=2))
