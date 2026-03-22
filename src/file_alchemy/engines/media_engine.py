"""FFmpeg-backed media engine: probe, convert, and progress reporting."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from file_alchemy.errors.ffmpeg_not_found_error import FFmpegNotFoundError
from file_alchemy.errors.media_conversion_error import MediaConversionError


def _require_ffmpeg() -> tuple[str, str]:
    """Return (ffmpeg, ffprobe) executable paths, raising if not found."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise FFmpegNotFoundError(
            "FFmpeg / ffprobe not found on PATH. "
            "Install FFmpeg and ensure it is accessible."
        )
    return ffmpeg, ffprobe


def probe(path: str | Path) -> dict:
    """Return stream and format metadata for *path* via ffprobe.

    Args:
        path: Path to the media file to inspect.

    Returns:
        Parsed JSON dict from ffprobe (keys: ``format``, ``streams``).

    Raises:
        FFmpegNotFoundError: If ffprobe is not on PATH.
        MediaConversionError: If ffprobe fails to parse the file or exits with an error.
    """
    _, ffprobe_bin = _require_ffmpeg()
    try:
        result = subprocess.run(
            [
                ffprobe_bin,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise MediaConversionError(
            f"Failed to probe file: {path}", stderr=e.stderr
        ) from e

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise MediaConversionError(
            f"Failed to parse ffprobe JSON output for file: {path}",
            stderr=result.stderr,
        ) from e


# --------------------------------------------------------------------------- #
# Progress parsing
# --------------------------------------------------------------------------- #

_TIME_RE = re.compile(r"time=(\d+):(\d+):([\d.]+)")


def _parse_seconds(hours: str, minutes: str, seconds: str) -> float:
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _parse_progress(
    line: str,
    duration_seconds: float,
    progress_callback: Callable[[float], None],
) -> None:
    """Update caller with 0-100 progress if *line* contains a ``time=`` token."""
    match = _TIME_RE.search(line)
    if match and duration_seconds > 0:
        elapsed = _parse_seconds(*match.groups())
        pct = min(elapsed / duration_seconds * 100, 100.0)
        progress_callback(pct)


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #


def convert(
    input_path: str | Path,
    output_path: str | Path,
    extra_args: list[str] | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> Path:
    """Convert *input_path* to *output_path* using FFmpeg.

    FFmpeg infers codecs and containers from the output extension.  Pass
    *extra_args* to override defaults (e.g. ``["-vf", "scale=1280:-1"]``).

    Args:
        input_path:  Source file.
        output_path: Destination file; its extension determines the format.
        extra_args:  Additional FFmpeg CLI arguments inserted before ``-y``.
        progress_callback: Optional callback receiving progress as a float in [0, 100].

    Returns:
        The resolved ``Path`` of the created output file.

    Raises:
        FFmpegNotFoundError: If ffmpeg is not on PATH.
        MediaConversionError: If FFmpeg exits with a non-zero status.
    """
    ffmpeg_bin, _ = _require_ffmpeg()
    input_path = Path(input_path)
    output_path = Path(output_path)

    # Determine total duration upfront so progress can be reported as %.
    duration_seconds = 0.0
    if progress_callback:
        try:
            meta = probe(input_path)
            raw = meta.get("format", {}).get("duration")
            if raw is not None:
                duration_seconds = float(raw)
        except Exception:
            pass  # Fall back to indeterminate progress.

    cmd = [
        ffmpeg_bin,
        "-i",
        str(input_path),
        *(extra_args or []),
        "-y",  # overwrite output without prompting
        str(output_path),
    ]

    process = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stderr_lines: list[str] = []
    assert process.stderr is not None
    for line in process.stderr:
        stderr_lines.append(line)
        if progress_callback:
            _parse_progress(line, duration_seconds, progress_callback)

    process.wait()
    if process.returncode != 0:
        err_out = "".join(stderr_lines)
        raise MediaConversionError(
            f"FFmpeg conversion failed with code {process.returncode}",
            stderr=err_out,
        )

    return output_path.resolve()
