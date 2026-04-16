"""
pytest configuration and shared fixtures.

Patches soundfile to treat .mp4 files as WAV format so that test fixtures
can create stub "video" files using soundfile.write() with an .mp4 extension.
libsndfile does not natively support MP4, but tests only need a readable audio
file at that path — WAV written with a .mp4 extension satisfies that requirement.
"""
import soundfile as _sf

_original_get_format = _sf._get_format_from_filename


def _patched_get_format(file, mode):
    try:
        return _original_get_format(file, mode)
    except TypeError:
        import os
        ext = os.path.splitext(str(file))[-1][1:].upper()
        if ext == "MP4":
            return "WAV"
        raise


_sf._get_format_from_filename = _patched_get_format
