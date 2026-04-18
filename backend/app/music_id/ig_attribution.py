"""
Scrape Instagram's embed/captioned endpoint for a reel's music attribution.

Why: yt-dlp's IG extractor does not populate `track`/`artist` fields for reels
that use Instagram's library audio. The same data IS present on the embed
endpoint — in a `<div class="HeaderSecondaryContent">` span as "Artist · Title".

This is the anonymous, server-renderable endpoint IG uses for third-party
embeds, so it doesn't require login. IG could break it at any time; fail
gracefully when it does.

Only intended for case-2 detection: if the embed shows a real artist · title,
we have case 2 (library track). If the span is missing or says "Original
audio", we're in case 1 and the caller should fall back to AudD fingerprinting.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
import httpx

EMBED_URL_TEMPLATE = "https://www.instagram.com/reel/{code}/embed/captioned/"
EMBED_URL_FALLBACK = "https://www.instagram.com/p/{code}/embed/captioned/"
HEADER_SECONDARY_RE = re.compile(
    r'<div class="HeaderSecondaryContent"><span>([^<]+)</span></div>'
)
# Phrases Instagram uses when the reel is a creator-uploaded mix (case 1).
# We treat any of these as "no library track attribution".
ORIGINAL_AUDIO_MARKERS = (
    "original audio",
    "original sound",
)
_SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)")
REQUEST_TIMEOUT_S = 8.0
# Counter-intuitive: IG serves the server-rendered embed (with the music
# attribution in the HTML) only when the User-Agent does NOT look like a real
# browser. Full-browser UAs get a JS-heavy SPA shell that populates
# attribution client-side, which we can't parse. A minimal UA string wins.
UA = "Mozilla/5.0 (compatible; ExtractAssets/1.0)"


@dataclass
class IgMusic:
    title: str
    artist: str | None
    raw: str  # the unparsed span contents, for debugging


def shortcode_from_url(url: str) -> str | None:
    m = _SHORTCODE_RE.search(url or "")
    return m.group(1) if m else None


def parse_attribution_html(html: str) -> IgMusic | None:
    """Extract {artist, title} from a reel-embed HTML body. None if missing or
    if the attribution indicates a creator-uploaded original mix."""
    m = HEADER_SECONDARY_RE.search(html)
    if not m:
        return None
    raw = m.group(1).strip()
    low = raw.lower()
    if any(marker in low for marker in ORIGINAL_AUDIO_MARKERS):
        return None  # case 1, not a library track
    # Instagram uses U+00B7 MIDDLE DOT (·) to separate artist · title.
    # Also accept a plain "-" fallback.
    for sep in ("\u00b7", " - "):
        if sep in raw:
            artist, _, title = raw.partition(sep)
            artist = artist.strip()
            title = title.strip()
            if artist and title:
                return IgMusic(title=title, artist=artist, raw=raw)
    # No separator — treat the whole thing as a title, no artist.
    return IgMusic(title=raw, artist=None, raw=raw)


def fetch_ig_music_attribution(url: str) -> IgMusic | None:
    """Fetch the embed page for a reel URL and parse out the music attribution."""
    code = shortcode_from_url(url)
    if not code:
        return None
    headers = {"User-Agent": UA, "Accept": "text/html"}
    for template in (EMBED_URL_TEMPLATE, EMBED_URL_FALLBACK):
        try:
            resp = httpx.get(template.format(code=code), headers=headers, timeout=REQUEST_TIMEOUT_S, follow_redirects=True)
        except httpx.HTTPError:
            continue
        if resp.status_code != 200 or not resp.text:
            continue
        parsed = parse_attribution_html(resp.text)
        if parsed:
            return parsed
    return None
