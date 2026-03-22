"""Unit tests for file_alchemy.engines.media_engine."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from file_alchemy.engines import media_engine

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


def test_probe_returns_parsed_dict(tmp_path: Path, mock_ffmpeg_paths: None) -> None:
    """probe() parses ffprobe JSON output and returns a dict."""
    fake_file = tmp_path / "input.mp4"
    fake_file.touch()

    completed = MagicMock()
    completed.stdout = _FAKE_PROBE_OUTPUT

    with patch("subprocess.run", return_value=completed) as mock_run:
        result = media_engine.probe(fake_file)

    assert result["format"]["duration"] == "10.0"
    assert result["streams"][0]["codec_name"] == "h264"
    call_args = mock_run.call_args[0][0]
    assert "-print_format" in call_args
    assert "json" in call_args
    assert "-show_streams" in call_args


def test_probe_raises_on_failure(tmp_path: Path, mock_ffmpeg_paths: None) -> None:
    """probe() raises MediaConversionError when ffprobe exits with non-zero status."""
    fake_file = tmp_path / "non_existent.mp4"

    error = subprocess.CalledProcessError(1, ["ffprobe"], stderr="No such file")

    with patch("subprocess.run", side_effect=error):
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


# --------------------------------------------------------------------------- #
# convert (mocked)
# --------------------------------------------------------------------------- #


def test_convert_returns_resolved_output_path(tmp_path: Path, mock_ffmpeg_paths: None) -> None:
    """convert() returns the resolved output path on success."""
    inp = tmp_path / "input.wav"
    inp.touch()
    out = tmp_path / "output.mp3"

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stderr = iter(["frame=1 time=00:00:01.00\n"])

    with (
        patch.object(
            media_engine, "probe", return_value={"format": {"duration": "5.0"}}
        ),
        patch("subprocess.Popen", return_value=mock_process),
    ):
        result = media_engine.convert(inp, out, progress_callback=lambda _: None)

    assert result == out.resolve()


def test_convert_raises_on_nonzero_returncode(tmp_path: Path, mock_ffmpeg_paths: None) -> None:
    """convert() raises CalledProcessError when FFmpeg exits non-zero."""
    inp = tmp_path / "bad.mp4"
    inp.touch()
    out = tmp_path / "out.avi"

    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stderr = iter(["Error while opening encoder\n"])

    with (
        patch.object(media_engine, "probe", return_value={"format": {}}),
        patch("subprocess.Popen", return_value=mock_process),
    ):
        with pytest.raises(media_engine.MediaConversionError):
            media_engine.convert(inp, out)


def test_convert_extra_args_forwarded(tmp_path: Path, mock_ffmpeg_paths: None) -> None:
    """Extra CLI args are included in the command passed to Popen."""
    inp = tmp_path / "in.mp4"
    inp.touch()
    out = tmp_path / "out.mp4"

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stderr = iter([])

    with (
        patch.object(media_engine, "probe", return_value={"format": {}}),
        patch("subprocess.Popen", return_value=mock_process) as mock_popen,
    ):
        media_engine.convert(inp, out, extra_args=["-vf", "scale=1280:-1"])

    cmd = mock_popen.call_args[0][0]
    assert "-vf" in cmd
    assert "scale=1280:-1" in cmd


def test_convert_without_progress_callback(tmp_path: Path, mock_ffmpeg_paths: None) -> None:
    """convert() works correctly when no progress callback is given."""
    inp = tmp_path / "in.ogg"
    inp.touch()
    out = tmp_path / "out.flac"

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stderr = iter(["time=00:00:03.00\n"])

    with patch("subprocess.Popen", return_value=mock_process):
        with patch.object(media_engine, "probe") as mock_probe:
            media_engine.convert(inp, out)
            mock_probe.assert_not_called()


def test_convert_indeterminate_progress(tmp_path: Path, mock_ffmpeg_paths: None) -> None:
    """convert() gracefully falls back to duration=0 if probe() raises an exception."""
    inp = tmp_path / "in.mp4"
    inp.touch()
    out = tmp_path / "out.mp4"

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stderr = iter(["time=00:00:03.00\n"])

    with (
        patch.object(media_engine, "probe", side_effect=Exception("Probe failed")),
        patch("subprocess.Popen", return_value=mock_process),
    ):
        progress_values: list[float] = []
        media_engine.convert(inp, out, progress_callback=progress_values.append)

    assert progress_values == []
