from unittest.mock import patch, MagicMock
from app.music_id.ig_attribution import (
    parse_attribution_html,
    shortcode_from_url,
    fetch_ig_music_attribution,
)

# Fixture HTML fragments mimicking real IG embed responses.
LIBRARY_TRACK_HTML = (
    '<html><body>'
    '<div class="Header">'
    '<a><span class="UsernameText">newlifewitharpit</span></a>'
    '<div class="HeaderSecondaryContent"><span>Boney M. \u00b7 Rasputin (Instrumental)</span></div>'
    '</div></body></html>'
)

ORIGINAL_AUDIO_HTML = (
    '<html><body>'
    '<div class="Header">'
    '<a><span class="UsernameText">some_creator</span></a>'
    '<div class="HeaderSecondaryContent"><span>Original audio</span></div>'
    '</div></body></html>'
)

NO_SECONDARY_HTML = (
    '<html><body>'
    '<div class="Header"><span class="UsernameText">user</span></div>'
    '</body></html>'
)

HYPHEN_SEPARATOR_HTML = (
    '<html><body>'
    '<div class="HeaderSecondaryContent"><span>Artist Name - Song Title</span></div>'
    '</body></html>'
)


def test_shortcode_extraction():
    assert shortcode_from_url("https://www.instagram.com/reel/DXHPTIigTwB/") == "DXHPTIigTwB"
    assert shortcode_from_url("https://instagram.com/reel/abc_123/?x=y") == "abc_123"
    assert shortcode_from_url("https://www.instagram.com/p/ABCdef/") == "ABCdef"
    assert shortcode_from_url("https://example.com/not-instagram") is None
    assert shortcode_from_url("") is None


def test_parse_library_track_middle_dot():
    music = parse_attribution_html(LIBRARY_TRACK_HTML)
    assert music is not None
    assert music.artist == "Boney M."
    assert music.title == "Rasputin (Instrumental)"


def test_parse_original_audio_returns_none():
    """Creator-uploaded 'Original audio' is case 1 — should not be treated as a known song."""
    assert parse_attribution_html(ORIGINAL_AUDIO_HTML) is None


def test_parse_missing_secondary_content():
    assert parse_attribution_html(NO_SECONDARY_HTML) is None


def test_parse_hyphen_separator():
    music = parse_attribution_html(HYPHEN_SEPARATOR_HTML)
    assert music is not None
    assert music.artist == "Artist Name"
    assert music.title == "Song Title"


@patch("app.music_id.ig_attribution.httpx.get")
def test_fetch_happy_path(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text=LIBRARY_TRACK_HTML)
    music = fetch_ig_music_attribution("https://www.instagram.com/reel/DXHPTIigTwB/")
    assert music is not None
    assert music.artist == "Boney M."
    assert music.title == "Rasputin (Instrumental)"


@patch("app.music_id.ig_attribution.httpx.get")
def test_fetch_returns_none_for_original_audio(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text=ORIGINAL_AUDIO_HTML)
    assert fetch_ig_music_attribution("https://www.instagram.com/reel/abc/") is None


@patch("app.music_id.ig_attribution.httpx.get")
def test_fetch_returns_none_on_http_error(mock_get):
    mock_get.return_value = MagicMock(status_code=404, text="")
    assert fetch_ig_music_attribution("https://www.instagram.com/reel/abc/") is None


def test_fetch_returns_none_for_bad_url():
    assert fetch_ig_music_attribution("not-a-valid-url") is None
    assert fetch_ig_music_attribution("") is None
