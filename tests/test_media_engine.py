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


# --------------------------------------------------------------------------- #
# probe (mocked)
# --------------------------------------------------------------------------- #


def test_probe_returns_parsed_dict(tmp_path: Path) -> None:
    """probe() parses ffprobe JSON output and returns a dict."""
    fake_file = tmp_path / "input.mp4"
    fake_file.touch()

    completed = MagicMock()
    completed.stdout = _FAKE_PROBE_OUTPUT

    with (
        patch.object(
            media_engine, "_require_ffmpeg", return_value=("/ffmpeg", "/ffprobe")
        ),
        patch("subprocess.run", return_value=completed) as mock_run,
    ):
        result = media_engine.probe(fake_file)

    assert result["format"]["duration"] == "10.0"
    assert result["streams"][0]["codec_name"] == "h264"
    # Ensure -print_format json and -show_streams were passed
    call_args = mock_run.call_args[0][0]
    assert "-print_format" in call_args
    assert "json" in call_args
    assert "-show_streams" in call_args


def test_probe_raises_on_failure(tmp_path: Path) -> None:
    """probe() raises MediaConversionError when ffprobe exits with non-zero status."""
    fake_file = tmp_path / "non_existent.mp4"

    error = subprocess.CalledProcessError(1, ["ffprobe"], stderr="No such file")

    with (
        patch.object(
            media_engine, "_require_ffmpeg", return_value=("/ffmpeg", "/ffprobe")
        ),
        patch("subprocess.run", side_effect=error),
    ):
        with pytest.raises(
            media_engine.MediaConversionError, match="Failed to probe file:"
        ):
            media_engine.probe(fake_file)


# --------------------------------------------------------------------------- #
# _parse_progress
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "line, duration, expected_pct",
    [
        ("frame=  100 fps= 25 time=00:00:05.00 bitrate=  128", 10.0, 50.0),
        ("frame=  200 fps= 25 time=00:00:10.00 bitrate=  128", 10.0, 100.0),
        ("frame=    0 fps=  0 time=00:00:00.00 bitrate= N/A", 10.0, 0.0),
        # time= beyond duration → clamped to 100
        ("frame=  999 fps= 25 time=00:00:20.00 bitrate=  128", 10.0, 100.0),
    ],
)
def test_parse_progress_calls_callback(
    line: str, duration: float, expected_pct: float
) -> None:
    captured: list[float] = []
    media_engine._parse_progress(line, duration, captured.append)
    assert len(captured) == 1
    assert captured[0] == pytest.approx(expected_pct, abs=0.01)


def test_parse_progress_no_time_token() -> None:
    """Lines without time= should not invoke the callback."""
    captured: list[float] = []
    media_engine._parse_progress(
        "Duration: 00:00:10.00, start: 0.0", 10.0, captured.append
    )
    assert captured == []


def test_parse_progress_zero_duration_no_division() -> None:
    """Zero duration must not cause a ZeroDivisionError."""
    captured: list[float] = []
    media_engine._parse_progress("time=00:00:05.00 bitrate=  128", 0.0, captured.append)
    assert captured == []
