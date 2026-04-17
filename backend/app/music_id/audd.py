"""
Minimal AudD API client.

https://docs.audd.io/ — `/` endpoint accepts an audio file upload and returns
JSON with `status: "success"` and a `result` object (title, artist, album,
spotify, apple_music, song_link, etc.) or `result: null` when no match.

Tiny surface area on purpose — easy to swap for ACRCloud later.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import httpx

AUDD_URL = "https://api.audd.io/"
# Ask AudD to include richer metadata so we can surface links.
DEFAULT_RETURN = "spotify,apple_music,deezer"
REQUEST_TIMEOUT_S = 30.0


class AudDError(Exception):
    """Raised when AudD returns an error response or the request fails."""


@dataclass
class AudDMatch:
    """Normalised shape we surface to the frontend."""
    title: str
    artist: str
    album: str | None = None
    release_date: str | None = None
    label: str | None = None
    song_link: str | None = None
    spotify_url: str | None = None
    apple_music_url: str | None = None
    youtube_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def identify(clip_path: Path, api_key: str, return_fields: str = DEFAULT_RETURN) -> AudDMatch | None:
    """
    Upload `clip_path` to AudD. Return AudDMatch on success, None on no-match.
    Raises AudDError on API-level failures (bad key, rate limit, network).
    """
    if not api_key:
        raise AudDError("no AudD API key configured")

    try:
        with clip_path.open("rb") as fh:
            files = {"file": (clip_path.name, fh, "audio/wav")}
            data = {"api_token": api_key, "return": return_fields}
            resp = httpx.post(AUDD_URL, data=data, files=files, timeout=REQUEST_TIMEOUT_S)
    except httpx.HTTPError as e:
        raise AudDError(f"AudD request failed: {e}") from e

    if resp.status_code != 200:
        raise AudDError(f"AudD returned HTTP {resp.status_code}: {resp.text[:200]}")

    body = resp.json()
    if body.get("status") != "success":
        msg = body.get("error", {}).get("error_message") or str(body.get("error") or body)
        raise AudDError(f"AudD error: {msg}")

    result = body.get("result")
    if not result:
        return None

    return _normalise(result)


def _normalise(result: dict[str, Any]) -> AudDMatch:
    spotify = result.get("spotify") or {}
    apple = result.get("apple_music") or {}
    return AudDMatch(
        title=result.get("title", ""),
        artist=result.get("artist", ""),
        album=result.get("album"),
        release_date=result.get("release_date"),
        label=result.get("label"),
        song_link=result.get("song_link"),
        spotify_url=(spotify.get("external_urls") or {}).get("spotify"),
        apple_music_url=apple.get("url"),
        youtube_url=None,  # AudD doesn't return YT directly; we'll compute a search link
        raw=result,
    )
