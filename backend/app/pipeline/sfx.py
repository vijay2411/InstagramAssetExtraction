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

class SfxStage:
    name = "sfx"

    def run(self, ctx: JobContext) -> StageResult:
        non_speech = ctx.inputs.get("non_speech")
        if not non_speech or not non_speech.exists():
            raise StageError("missing non_speech input", retriable=False)

        min_members = int(ctx.params.get("min_cluster_size", 2))
        clip_min_ms = int(ctx.params.get("clip_min_ms", 300))
        clip_max_ms = int(ctx.params.get("clip_max_ms", 1500))
        dist_threshold = float(
            ctx.params.get("cluster_dist_threshold", DEFAULT_CLUSTER_DIST_THRESHOLD)
        )

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0, message="loading audio"))

        y, sr = librosa.load(str(non_speech), sr=None, mono=True)
        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.2, message="detecting onsets"))

        onsets = librosa.onset.onset_detect(y=y, sr=sr, units="samples", backtrack=True)
        clip_min = int(sr * clip_min_ms / 1000)
        clip_max = int(sr * clip_max_ms / 1000)

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

            kept = [(label, indices) for label, indices in groups.items() if len(indices) >= min_members]
            kept.sort(key=lambda x: len(x[1]), reverse=True)

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
