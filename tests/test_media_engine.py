"""Unit tests for file_alchemy.engines.media_engine.

Tests that require FFmpeg on PATH are automatically skipped when it is not
available, so the suite can pass in CI environments that do not bundle FFmpeg.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from file_alchemy.engines import media_engine

# --------------------------------------------------------------------------- #
# Helpers / fixtures
# --------------------------------------------------------------------------- #

_HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
skip_no_ffmpeg = pytest.mark.skipif(
    not _HAS_FFMPEG,
    reason="FFmpeg not found on PATH",
)

_FAKE_PROBE_OUTPUT = json.dumps(
    {
        "format": {
            "filename": "test.mp4",
            "duration": "10.0",
            "size": "1024",
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
            }
        ],
    }
)


# --------------------------------------------------------------------------- #
# _require_ffmpeg
# --------------------------------------------------------------------------- #


def test_require_ffmpeg_raises_when_missing() -> None:
    """_require_ffmpeg raises FFmpegNotFoundError when ffmpeg / ffprobe absent."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(media_engine.FFmpegNotFoundError, match="FFmpeg"):
            media_engine._require_ffmpeg()


def test_require_ffmpeg_returns_paths_when_present() -> None:
    """_require_ffmpeg returns tuple of non-empty strings when both tools exist."""
    with patch("shutil.which", side_effect=lambda name: f"/usr/bin/{name}"):
        ffmpeg, ffprobe = media_engine._require_ffmpeg()
    assert ffmpeg == "/usr/bin/ffmpeg"
    assert ffprobe == "/usr/bin/ffprobe"
