"""
YouTube song reference download via yt-dlp.

Given (artist, title), search YouTube for `ytsearchN:<query>` and download up
to N audio candidates as WAVs. The alignment stage downstream will pick
whichever candidate best correlates with the reel's music stem.

Why top-N: YouTube's top result for a song isn't always the correct version —
could be a live cover, instrumental, lyric video with intro, or wrong artist
with same title. Pulling multiple candidates and letting correlation pick
is cheaper than getting fancy with query rewriting.
"""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class YtCandidate:
    """A downloaded YouTube audio candidate awaiting alignment scoring."""
    index: int                 # 1..N, order as YouTube returned them
    video_id: str
    title: str
    uploader: str | None
    duration_s: float
    audio_path: Path           # local WAV file


class YtDownloadError(Exception):
    """Raised when all candidate downloads fail."""


def build_query(artist: str, title: str) -> str:
    """Compose the yt-dlp search query. Quotes around artist and title so
    matches prefer results with both tokens present."""
    return f'"{artist}" "{title}"'


def _yt_dlp(args: list[str], timeout_s: int = 120) -> subprocess.CompletedProcess:
    """Invoke yt-dlp with the venv's python. Capture stdout/stderr."""
    cmd = [sys.executable, "-m", "yt_dlp", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)


def search_candidates(artist: str, title: str, top_n: int = 3) -> list[dict]:
    """
    Run a yt-dlp search for up to top_n candidates. Returns the parsed info
    dicts (one per line of --print-json output) without downloading audio yet.
    """
    query = f"ytsearch{top_n}:{build_query(artist, title)}"
    proc = _yt_dlp(
        [
            "--no-playlist",
            "--no-warnings",
            "--skip-download",
            "--print-json",
            query,
        ],
        timeout_s=60,
    )
    if proc.returncode != 0:
        raise YtDownloadError(
            f"ytsearch failed for {artist!r} / {title!r}: {proc.stderr.strip()[:300]}"
        )
    entries = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries[:top_n]


def download_as_wav(video_id: str, dst_dir: Path) -> Path:
    """Download a single YouTube video's audio as WAV into dst_dir. Returns
    the resulting WAV path. Raises YtDownloadError on failure."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    # Use the video_id as the filename stem so candidates don't collide.
    out_template = str(dst_dir / f"{video_id}.%(ext)s")
    proc = _yt_dlp(
        [
            "--no-playlist",
            "--no-warnings",
            "-x",
            "--audio-format", "wav",
            "--audio-quality", "0",
            "-o", out_template,
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        timeout_s=180,
    )
    if proc.returncode != 0:
        raise YtDownloadError(
            f"yt-dlp audio download failed for {video_id}: {proc.stderr.strip()[:300]}"
        )
    wav_path = dst_dir / f"{video_id}.wav"
    if not wav_path.exists():
        # yt-dlp sometimes picks a different extension; find whatever landed.
        found = next((p for p in dst_dir.glob(f"{video_id}.*") if p.suffix != ".json"), None)
        if not found:
            raise YtDownloadError(f"download succeeded but no audio file found for {video_id}")
        shutil.move(str(found), str(wav_path))
    return wav_path


def fetch_top_candidates(
    artist: str,
    title: str,
    top_n: int = 3,
    dst_dir: Path | None = None,
) -> list[YtCandidate]:
    """
    End-to-end: search + download top_n audio candidates.

    Returns whichever candidates downloaded successfully (may be fewer than
    top_n). Raises YtDownloadError only if *all* downloads fail.
    """
    if dst_dir is None:
        dst_dir = Path(tempfile.mkdtemp(prefix="yt_candidates_"))
    dst_dir = Path(dst_dir)

    entries = search_candidates(artist, title, top_n=top_n)
    if not entries:
        raise YtDownloadError(f"no YouTube results for {artist!r} / {title!r}")

    candidates: list[YtCandidate] = []
    errors: list[str] = []
    for i, info in enumerate(entries, start=1):
        vid = info.get("id")
        if not vid:
            continue
        try:
            audio = download_as_wav(vid, dst_dir)
        except YtDownloadError as e:
            errors.append(str(e))
            continue
        candidates.append(
            YtCandidate(
                index=i,
                video_id=vid,
                title=info.get("title", ""),
                uploader=info.get("uploader"),
                duration_s=float(info.get("duration") or 0.0),
                audio_path=audio,
            )
        )

    if not candidates:
        raise YtDownloadError(
            f"all {len(entries)} candidate downloads failed: {' | '.join(errors[:3])}"
        )
    return candidates
