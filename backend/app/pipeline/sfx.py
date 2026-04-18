from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import librosa
import soundfile as sf
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError

N_MFCC = 13

# cosine distance threshold for cluster membership. This is a hyperparameter
# that will need tuning against real-world SFX in the e2e test (Task 27) — the
# default 0.35 is sized for the wide MFCC distributions of real audio (clicks,
# whooshes, musical hits). Synthetic pure-tone tests use a much tighter value
# (~0.01) because sinusoid MFCC vectors are unusually close. Callers override
# this via ctx.params["cluster_dist_threshold"].
DEFAULT_CLUSTER_DIST_THRESHOLD = 0.35

# TEMPORARY: SFX separation is disabled while we design a better algorithm.
# The current onset + MFCC approach mistakes musical drum hits and repeated
# riffs for SFX on music-heavy reels. Disabling keeps the pipeline intact
# and makes music.wav = the full non-speech stem (no holes cut into it).
#
# To re-enable: set SFX_ENABLED = True OR pass ctx.params["sfx_enabled"] = True.
# To redesign: start in this file — everything downstream (music stage, manifest,
# UI) already handles the "0 SFX detected" case cleanly.
SFX_ENABLED = False


class SfxStage:
    name = "sfx"

    def run(self, ctx: JobContext) -> StageResult:
        non_speech = ctx.inputs.get("non_speech")
        if not non_speech or not non_speech.exists():
            raise StageError("missing non_speech input", retriable=False)

        # Early-exit no-op path. Writes an empty clusters file so the music
        # stage reads it cleanly and leaves non_speech.wav untouched.
        if not bool(ctx.params.get("sfx_enabled", SFX_ENABLED)):
            sfx_dir = ctx.job_dir / "sfx"
            sfx_dir.mkdir(exist_ok=True)
            clusters_path = ctx.job_dir / "sfx_clusters.json"
            clusters_path.write_text(json.dumps([]))
            ctx.emit(StageEvent(
                type="progress", stage=self.name, progress=1.0,
                message="SFX extraction disabled (see sfx.py)",
            ))
            return StageResult(
                artifacts={"clusters_meta": Path("sfx_clusters.json")},
                extra={"sfx_count": 0},
            )

        min_members = int(ctx.params.get("min_cluster_size", 2))
        clip_min_ms = int(ctx.params.get("clip_min_ms", 300))
        clip_max_ms = int(ctx.params.get("clip_max_ms", 1500))
        dist_threshold = float(
            ctx.params.get("cluster_dist_threshold", DEFAULT_CLUSTER_DIST_THRESHOLD)
        )
        # Beat-grid filter reference (typically the pre-subtraction music.wav).
        # When set, we detect the song's beat positions and reject onsets that
        # land on-beat — those are almost always leaked drum hits rather than
        # creator-added SFX. Skipped automatically on arrhythmic tracks.
        beat_ref = ctx.params.get("beat_reference_path")

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0, message="loading audio"))

        y, sr = librosa.load(str(non_speech), sr=None, mono=True)
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.2, message="detecting onsets"))

        onsets = librosa.onset.onset_detect(y=y, sr=sr, units="samples", backtrack=True)
        clip_min = int(sr * clip_min_ms / 1000)
        clip_max = int(sr * clip_max_ms / 1000)

        # Apply beat-grid filter if a reference was supplied. We compute a
        # boolean mask on the onset-samples-in-seconds array and apply it
        # directly — no float equality games.
        beat_info = {"applied": False, "dropped": 0, "total": len(onsets), "tempo": None}
        if beat_ref and len(onsets) > 0:
            try:
                from app.sfx_extract.beat_filter import find_beats, off_beat_mask
                grid = find_beats(Path(beat_ref))
                if grid.has_beat:
                    onset_times_s = onsets / float(sr)
                    # Use every music onset (drum hits, note attacks) as the
                    # reject grid, not just detected beats. That's where
                    # leaked residue lives.
                    mask = off_beat_mask(onset_times_s, grid.onset_times_s)
                    before = len(onsets)
                    onsets = onsets[mask]
                    beat_info = {
                        "applied": True,
                        "dropped": int(before - len(onsets)),
                        "total": int(before),
                        "tempo": round(float(grid.tempo_bpm), 1),
                        "n_music_onsets": int(len(grid.onset_times_s)),
                    }
                    ctx.emit(StageEvent(
                        type="progress", stage=self.name, progress=0.3,
                        message=(
                            f"onset-grid filter ({beat_info['n_music_onsets']} music onsets @ "
                            f"{beat_info['tempo']} bpm): dropped {beat_info['dropped']}/{beat_info['total']}, "
                            f"{len(onsets)} survive"
                        ),
                    ))
                else:
                    ctx.emit(StageEvent(
                        type="progress", stage=self.name, progress=0.3,
                        message=f"beat filter: arrhythmic track (conf={grid.confidence:.2f}) — skipped",
                    ))
            except Exception as e:
                ctx.emit(StageEvent(
                    type="progress", stage=self.name, progress=0.3,
                    message=f"beat filter error, continuing unfiltered: {str(e)[:100]}",
                ))

        clips: list[dict] = []
        for i, start in enumerate(onsets):
            next_onset = onsets[i + 1] if i + 1 < len(onsets) else len(y)
            end = min(start + clip_max, next_onset, len(y))
            if end - start < clip_min:
                end = min(start + clip_min, len(y))
            if end - start < int(sr * 0.1):  # < 100ms, too short to be useful
                continue
            clip = y[start:end]
            mfcc = librosa.feature.mfcc(y=clip, sr=sr, n_mfcc=N_MFCC)
            feat = mfcc.mean(axis=1)
            clips.append({
                "start_s": float(start / sr),
                "end_s": float(end / sr),
                "feat": feat,
                "energy": float(np.sqrt((clip ** 2).mean())),
            })

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.5, message=f"clustering {len(clips)} candidates"))

        clusters_serialized: list[dict] = []
        sfx_dir = ctx.job_dir / "sfx"
        sfx_dir.mkdir(exist_ok=True)
        sfx_artifacts: dict[str, Path] = {}

        if len(clips) >= min_members:
            feats = np.vstack([c["feat"] for c in clips])
            dist = cosine_distances(feats)
            algo = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=dist_threshold,
                metric="precomputed",
                linkage="average",
            )
            labels = algo.fit_predict(dist)

            groups: dict[int, list[int]] = {}
            for idx, label in enumerate(labels):
                groups.setdefault(int(label), []).append(idx)

            # Density filter: genuine creator-added SFX repeat maybe once per
            # 2-10 seconds. Anything denser than ~1 per second is almost
            # certainly a rhythmic pattern (drums, hi-hats, bass bursts) that
            # leaked through subtraction, not an isolated sound effect.
            # Default off (very high) — backward compat with synthetic tests
            # that cluster many SFX in a short fixture. Orchestrator opts in
            # to a stricter value (~1.0/s) for real-world residuals.
            max_density = float(ctx.params.get("max_cluster_density_per_s", 999.0))
            kept: list[tuple[int, list[int]]] = []
            rejected_dense = 0
            for label, indices in groups.items():
                if len(indices) < min_members:
                    continue
                starts = sorted(clips[i]["start_s"] for i in indices)
                span = max(0.001, starts[-1] - starts[0])
                density = len(indices) / span
                if density > max_density:
                    rejected_dense += 1
                    continue
                kept.append((label, indices))
            kept.sort(key=lambda x: len(x[1]), reverse=True)
            if rejected_dense > 0:
                ctx.emit(StageEvent(
                    type="progress", stage=self.name, progress=0.6,
                    message=f"dropped {rejected_dense} rhythm-pattern clusters (density > {max_density}/s)",
                ))

            y_stereo, sr_stereo = sf.read(str(non_speech))
            if y_stereo.ndim == 1:
                y_stereo = np.stack([y_stereo, y_stereo], axis=1)

            for n, (label, indices) in enumerate(kept, start=1):
                rep = max(indices, key=lambda i: clips[i]["energy"])
                c = clips[rep]
                start_samp = int(c["start_s"] * sr_stereo)
                end_samp = int(c["end_s"] * sr_stereo)
                clip_audio = y_stereo[start_samp:end_samp]
                fname = f"sfx_{n:02d}.wav"
                sf.write(str(sfx_dir / fname), clip_audio, sr_stereo)
                sfx_artifacts[f"sfx_{n:02d}"] = Path("sfx") / fname
                clusters_serialized.append({
                    "index": n,
                    "count": len(indices),
                    "representative_path": f"sfx/{fname}",
                    "onset_times_s": [clips[i]["start_s"] for i in indices],
                    "offset_times_s": [clips[i]["end_s"] for i in indices],
                })

        (ctx.job_dir / "sfx_clusters.json").write_text(json.dumps(clusters_serialized, indent=2))
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0,
                            message=f"{len(clusters_serialized)} clusters"))
        return StageResult(
            artifacts={**sfx_artifacts, "clusters_meta": Path("sfx_clusters.json")},
            extra={"sfx_count": len(clusters_serialized)},
        )
