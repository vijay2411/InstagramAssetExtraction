"""
Build search URLs for a known song title + artist on Spotify / Apple Music
/ YouTube. Used in two places:

1. Case 2 (IG library track): yt-dlp gives us title/artist but no direct
   links. We synthesise search URLs so the user can click through.
2. Case 1 (AudD match): AudD returns Spotify + Apple URLs directly; we
   still add YouTube since AudD doesn't return it.
"""
from __future__ import annotations
from urllib.parse import quote_plus


def spotify_search_url(title: str, artist: str | None = None) -> str:
    q = f"{title} {artist}" if artist else title
    return f"https://open.spotify.com/search/{quote_plus(q.strip())}"


def apple_music_search_url(title: str, artist: str | None = None) -> str:
    q = f"{title} {artist}" if artist else title
    return f"https://music.apple.com/us/search?term={quote_plus(q.strip())}"


def youtube_search_url(title: str, artist: str | None = None) -> str:
    q = f"{title} {artist}" if artist else title
    return f"https://www.youtube.com/results?search_query={quote_plus(q.strip())}"


def all_search_links(title: str, artist: str | None = None) -> dict[str, str]:
    return {
        "spotify": spotify_search_url(title, artist),
        "apple_music": apple_music_search_url(title, artist),
        "youtube": youtube_search_url(title, artist),
    }
