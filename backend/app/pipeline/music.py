from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from app.pipeline.base import JobContext, StageResult, StageEvent
from app.core.errors import StageError

CROSSFADE_MS = 20

class MusicStage:
    name = "music"

    def run(self, ctx: JobContext) -> StageResult:
        non_speech = ctx.inputs.get("non_speech")
        clusters_meta = ctx.inputs.get("clusters_meta")
        source_meta = ctx.inputs.get("meta")
        if not non_speech or not clusters_meta or not source_meta:
            raise StageError("missing inputs for music stage", retriable=False)

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.0))

        audio, sr = sf.read(str(non_speech))
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        audio = audio.astype(np.float32).copy()

        clusters = json.loads(clusters_meta.read_text())
        crossfade_samples = int(sr * CROSSFADE_MS / 1000)

        for cluster in clusters:
            for start_s, end_s in zip(cluster["onset_times_s"], cluster["offset_times_s"]):
                s = max(0, int(start_s * sr))
                e = min(len(audio), int(end_s * sr))
                if e <= s:
                    continue
                fade_in_end = min(e, s + crossfade_samples)
                fade_out_start = max(s, e - crossfade_samples)
                if fade_in_end > s:
                    ramp = np.linspace(1.0, 0.0, fade_in_end - s)[:, None]
                    audio[s:fade_in_end] *= ramp
                if e > fade_out_start:
                    ramp = np.linspace(0.0, 1.0, e - fade_out_start)[:, None]
                    audio[fade_out_start:e] *= ramp
                if fade_out_start > fade_in_end:
                    audio[fade_in_end:fade_out_start] = 0.0

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=0.7))

        out_path = ctx.job_dir / "music.wav"
        sf.write(str(out_path), audio, sr)

        meta = json.loads(source_meta.read_text())
        song = None
        title = meta.get("track") or meta.get("song_title")
        artist = meta.get("artist") or meta.get("creator")
        if title:
            from app.music_id.links import all_search_links
            links = all_search_links(title, artist)
            song = {
                "title": title,
                "artist": artist,
                "album": meta.get("album"),
                "source": "yt_dlp_meta",
                # For case 2 we don't have direct URLs — surface search URLs so
                # the user can click through to Spotify / Apple / YouTube.
                "spotify_url": links["spotify"],
                "apple_music_url": links["apple_music"],
                "youtube_url": links["youtube"],
            }

        ctx.emit(StageEvent(type="progress", stage=self.name, progress=1.0))
        return StageResult(
            artifacts={"music": Path("music.wav")},
            extra={"song": song} if song else {"song": None},
        )
