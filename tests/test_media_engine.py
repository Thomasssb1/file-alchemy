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


def test_probe_returns_parsed_dict(tmp_path: Path, _: None) -> None:
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


def test_probe_raises_on_failure(tmp_path: Path, _: None) -> None:
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


@pytest.mark.parametrize(
    "line, duration, offset, scale, expected_pct",
    [
        ("time=00:00:05.00", 10.0, 0.0, 50.0, 25.0),
        ("time=00:00:05.00", 10.0, 50.0, 50.0, 75.0),
        ("time=00:00:10.00", 10.0, 50.0, 50.0, 100.0),
    ],
)
def test_parse_progress_scaled(
    line: str, duration: float, offset: float, scale: float, expected_pct: float
) -> None:
    """_parse_progress handles offset and scale for multi-pass encoding."""
    captured: list[float] = []
    media_engine._parse_progress(
        line, duration, captured.append, offset=offset, scale=scale
    )
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
    media_engine._parse_progress(
        "time=00:00:05.00 bitrate=  128",
        0.0,
        captured.append,
    )
    assert captured == []


# --------------------------------------------------------------------------- #
# convert (mocked)
# --------------------------------------------------------------------------- #


def test_convert_returns_resolved_output_path(
    tmp_path: Path, _: None
) -> None:
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


def test_convert_raises_on_nonzero_returncode(
    tmp_path: Path, _: None
) -> None:
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


def test_convert_extra_args_forwarded(tmp_path: Path, _: None) -> None:
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


def test_convert_without_progress_callback(
    tmp_path: Path, _: None
) -> None:
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


def test_convert_indeterminate_progress(
    tmp_path: Path, _: None
) -> None:
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


# --------------------------------------------------------------------------- #
# convert_to_icon (mocked)
# --------------------------------------------------------------------------- #


def test_convert_to_ico_success(tmp_path: Path, _: None) -> None:
    """convert_to_icon() successfully produces an .ico using Pillow."""
    inp = tmp_path / "input.png"
    inp.touch()
    out = tmp_path / "output.ico"

    mock_image = MagicMock()
    mock_image.size = (256, 256)
    mock_image.mode = "RGBA"

    with (
        patch("PIL.Image.open", return_value=mock_image) as mock_open,
        patch.object(media_engine, "convert") as mock_convert,
    ):
        result = media_engine.convert_to_icon(inp, out)

    assert result == out.resolve()
    # Verify that it first calls convert to extract a frame
    mock_convert.assert_called_once()
    assert "-vframes" in mock_convert.call_args[0][2]

    # Verify Pillow interaction
    mock_open.assert_called_once()
    mock_image.save.assert_called_once_with(out, format="ICO")


def test_convert_to_icns_success(tmp_path: Path, _: None) -> None:
    """convert_to_icon() successfully produces an .icns and handles mode conversion."""
    inp = tmp_path / "input.png"
    inp.touch()
    out = tmp_path / "output.icns"

    mock_image = MagicMock()
    mock_image.size = (512, 512)
    mock_image.mode = "RGB"  # Trigger convert("RGBA")
    mock_image.convert.return_value = mock_image

    with (
        patch("PIL.Image.open", return_value=mock_image),
        patch.object(media_engine, "convert"),
    ):
        result = media_engine.convert_to_icon(inp, out)

    assert result == out.resolve()
    mock_image.convert.assert_called_with("RGBA")
    mock_image.save.assert_called_once_with(out, format="ICNS")


def test_convert_to_icon_crops_non_square(
    tmp_path: Path, _: None
) -> None:
    """convert_to_icon() crops non-square inputs to center squares."""
    inp = tmp_path / "input.png"
    inp.touch()
    out = tmp_path / "output.ico"

    mock_image = MagicMock()
    mock_image.size = (500, 250)  # Width > Height
    mock_image.mode = "RGBA"
    mock_image.crop.return_value = mock_image

    with (
        patch("PIL.Image.open", return_value=mock_image),
        patch.object(media_engine, "convert"),
    ):
        media_engine.convert_to_icon(inp, out)

    # Size is 250, so left = (500-250)//2 = 125, top = (250-250)//2 = 0
    # crop((125, 0, 375, 250))
    mock_image.crop.assert_called_once_with((125, 0, 375, 250))


def test_convert_to_icon_raises_on_error(
    tmp_path: Path, _: None
) -> None:
    """convert_to_icon() raises MediaConversionError if Pillow fails."""
    inp = tmp_path / "input.png"
    inp.touch()
    out = tmp_path / "output.ico"

    with (
        patch("PIL.Image.open", side_effect=Exception("Pillow crash")),
        patch.object(media_engine, "convert"),
    ):
        with pytest.raises(media_engine.MediaConversionError, match="Failed to generate"):
            media_engine.convert_to_icon(inp, out)


# --------------------------------------------------------------------------- #
# ico/icns to img (using standard convert)
# --------------------------------------------------------------------------- #


def test_convert_ico_to_png(tmp_path: Path, _: None) -> None:
    """Standard convert() handles .ico as input (delegating to FFmpeg)."""
    inp = tmp_path / "input.ico"
    inp.touch()
    out = tmp_path / "output.png"

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stderr = iter([])

    with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
        media_engine.convert(inp, out)

    cmd = mock_popen.call_args[0][0]
    # Check that input and output are in the command
    assert str(inp) in cmd
    assert str(out) in cmd


# --------------------------------------------------------------------------- #
# convert_two_pass (mocked)
# --------------------------------------------------------------------------- #


def test_convert_two_pass_success(tmp_path: Path, _: None) -> None:
    """convert_two_pass() runs two FFmpeg passes and cleans up logs."""
    inp = tmp_path / "input.mp4"
    inp.touch()
    out = tmp_path / "output.mp4"

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stderr = iter(["frame=1 time=00:00:05.00\n"])

    # Create dummy log files to verify cleanup
    log1 = Path.cwd() / "ffmpeg2pass-0.log"
    log1.touch()

    def make_mock_process():
        proc = MagicMock()
        proc.returncode = 0
        proc.stderr = iter(["frame=1 time=00:00:05.00\n"])
        return proc

    try:
        with (
            patch.object(
                media_engine, "probe", return_value={"format": {"duration": "10.0"}}
            ),
            patch("subprocess.Popen", side_effect=[make_mock_process(), make_mock_process()]) as mock_popen,
        ):
            progress: list[float] = []
            result = media_engine.convert_two_pass(
                inp, out, progress_callback=progress.append
            )

        assert result == out.resolve()
        assert mock_popen.call_count == 2

        # Check pass 1 args: should have -pass 1 and output to null (NUL or /dev/null)
        pass1_args = mock_popen.call_args_list[0][0][0]
        assert "-pass" in pass1_args
        assert "1" in pass1_args
        assert "-f" in pass1_args
        assert "null" in pass1_args

        # Check pass 2 args: should have -pass 2 and real output path
        pass2_args = mock_popen.call_args_list[1][0][0]
        assert "-pass" in pass2_args
        assert "2" in pass2_args
        assert str(out) in pass2_args

        # Check progress: 50% from pass 1 (5s/10s * 50% = 25%) and 75% from pass 2 (50% + 25%)
        # Note: each pass will report progress.
        assert 25.0 in progress
        assert 75.0 in progress

        # Verify log cleanup
        assert not log1.exists()
    finally:
        log1.unlink(missing_ok=True)


def test_convert_two_pass_failure_on_first_pass(
    tmp_path: Path, _: None
) -> None:
    """convert_two_pass() raises MediaConversionError if the first pass fails."""
    inp = tmp_path / "input.mp4"
    inp.touch()
    out = tmp_path / "output.mp4"

    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stderr = iter(["First pass error\n"])

    with (
        patch.object(
            media_engine, "probe", return_value={"format": {"duration": "10.0"}}
        ),
        patch("subprocess.Popen", return_value=mock_process),
    ):
        with pytest.raises(
            media_engine.MediaConversionError, match="FFmpeg pass 1 failed"
        ):
            media_engine.convert_two_pass(inp, out)


# --------------------------------------------------------------------------- #
# compress_media (mocked)
# --------------------------------------------------------------------------- #


def test_compress_media_gets_duration_and_uses_convert(
    tmp_path: Path, _: None
) -> None:
    """compress_media gets duration from probe and routes to convert (one-pass)."""
    inp = tmp_path / "input.mp4"
    inp.touch()
    out = tmp_path / "output.mp4"

    mock_options = MagicMock()
    mock_options.to_ffmpeg_args.return_value = ["-b:v", "1M"]
    mock_options.requires_two_pass.return_value = False

    with (
        patch.object(media_engine, "probe", return_value={"format": {"duration": "12.5"}}) as mock_probe,
        patch.object(media_engine, "convert", return_value=out) as mock_convert,
    ):
        result = media_engine.compress_media(inp, out, options=mock_options)

        assert result == out.resolve()
        mock_probe.assert_called_once_with(inp)
        mock_options.to_ffmpeg_args.assert_called_once_with("mp4", 12.5)
        mock_convert.assert_called_once_with(
            inp, out, extra_args=["-b:v", "1M"], progress_callback=None
        )


def test_compress_media_probe_fails_falls_back_to_zero_duration(
    tmp_path: Path, _: None
) -> None:
    """compress_media falls back to duration=0 if probe raises an exception."""
    inp = tmp_path / "input.mp4"
    inp.touch()
    out = tmp_path / "output.mp4"

    mock_options = MagicMock()
    mock_options.to_ffmpeg_args.return_value = ["-b:v", "1M"]
    mock_options.requires_two_pass.return_value = False

    with (
        patch.object(media_engine, "probe", side_effect=Exception("Probe crash")) as mock_probe,
        patch.object(media_engine, "convert", return_value=out) as mock_convert,
    ):
        result = media_engine.compress_media(inp, out, options=mock_options)

        assert result == out.resolve()
        mock_probe.assert_called_once_with(inp)
        mock_options.to_ffmpeg_args.assert_called_once_with("mp4", 0.0)
        mock_convert.assert_called_once()


def test_compress_media_requires_two_pass(
    tmp_path: Path, _: None
) -> None:
    """compress_media calls convert_two_pass if options require it."""
    inp = tmp_path / "input.mp4"
    inp.touch()
    out = tmp_path / "output.mp4"

    mock_options = MagicMock()
    mock_options.to_ffmpeg_args.return_value = ["-b:v", "1M"]
    mock_options.requires_two_pass.return_value = True

    with (
        patch.object(media_engine, "probe", return_value={"format": {"duration": "10.0"}}),
        patch.object(media_engine, "convert_two_pass", return_value=out) as mock_two_pass,
    ):
        result = media_engine.compress_media(inp, out, options=mock_options)

        assert result == out.resolve()
        mock_options.requires_two_pass.assert_called_once_with("mp4")
        mock_two_pass.assert_called_once_with(
            inp, out, extra_args=["-b:v", "1M"], progress_callback=None
        )
