"""FFmpeg-backed media engine: probe, convert, and progress reporting."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import platform
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
    offset: float = 0.0,
    scale: float = 100.0,
) -> None:
    """Update caller with scaled progress if *line* contains a ``time=`` token.

    Progress is calculated as ``offset + (elapsed / duration * scale)``,
    capped at ``offset + scale``.
    """
    match = _TIME_RE.search(line)
    if match and duration_seconds > 0:
        elapsed = _parse_seconds(*match.groups())
        pct = min(elapsed / duration_seconds * scale, scale)
        progress_callback(offset + pct)


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #


def _execute_ffmpeg(
    cmd: list[str],
    duration_seconds: float,
    progress_callback: Callable[[float], None] | None,
    error_prefix: str = "FFmpeg conversion failed",
    offset: float = 0.0,
    scale: float = 100.0,
) -> None:
    """Execute FFmpeg command, parse progress, and handle errors."""
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
            _parse_progress(
                line, duration_seconds, progress_callback, offset, scale
            )

    process.wait()
    if process.returncode != 0:
        err_out = "".join(stderr_lines)
        raise MediaConversionError(
            f"{error_prefix} with code {process.returncode}",
            stderr=err_out,
        )


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

    _execute_ffmpeg(cmd, duration_seconds, progress_callback)
    return output_path.resolve()


def convert_to_icon(
    input_path: str | Path,
    output_path: str | Path,
    extra_args: list[str] | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> Path:
    """Convert an image or video to an ICO or ICNS file using Pillow.

    Rationale:
    FFmpeg's native ICO/ICNS support is inconsistent; it often lacks high-resolution
    packaging or cannot write ICNS files at all, so to handle this we:
    1. Use FFmpeg to extract a single high-quality frame (or decode the image).
    2. Use Pillow to handle square-cropping, transparency (RGBA), and packaging
       the multiple resolution layers required by the .ico and .icns container formats.
    """
    import tempfile
    from PIL import Image

    input_path = Path(input_path)
    output_path = Path(output_path)

    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        args = ["-vframes", "1"]
        if extra_args:
            args.extend(extra_args)

        convert(input_path, tmp.name, args, progress_callback)

        try:
            img = Image.open(tmp.name)
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Ensure it is square to prevent icon aspect ratio distortion on some OS
            size = min(img.size)
            if img.size[0] != img.size[1]:
                # Crop to center square
                left = (img.size[0] - size) // 2
                top = (img.size[1] - size) // 2
                img = img.crop((left, top, left + size, top + size))

            fmt = "ICO" if output_path.suffix.lower() == ".ico" else "ICNS"
            img.save(output_path, format=fmt)
        except Exception as e:
            raise MediaConversionError(
                f"Failed to generate {output_path.suffix.upper()} using Pillow",
                stderr=str(e),
            ) from e

    return output_path.resolve()


# --------------------------------------------------------------------------- #
# Two-pass target-size encoding
# --------------------------------------------------------------------------- #


def convert_two_pass(
    input_path: str | Path,
    output_path: str | Path,
    extra_args: list[str] | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> Path:
    """Encode *input_path* using two-pass mode for target-size accuracy.

    Pass 1 analyses the input (progress 0–50%).  Pass 2 encodes to the
    final output (progress 50–100%).  Temporary ``ffmpeg2pass-*.log*``
    files are cleaned up automatically.

    Args:
        input_path:  Source file.
        output_path: Destination file.
        extra_args:  FFmpeg CLI arguments including bitrate settings.
        progress_callback: Optional callback receiving 0–100 progress.

    Returns:
        The resolved ``Path`` of the created output file.

    Raises:
        FFmpegNotFoundError: If ffmpeg is not on PATH.
        MediaConversionError: If either pass fails.
    """
    ffmpeg_bin, _ = _require_ffmpeg()
    input_path = Path(input_path)
    output_path = Path(output_path)
    args = extra_args or []

    duration_seconds = 0.0
    if progress_callback:
        try:
            meta = probe(input_path)
            raw = meta.get("format", {}).get("duration")
            if raw is not None:
                duration_seconds = float(raw)
        except Exception:
            pass

    null_target = "NUL" if platform.system() == "Windows" else "/dev/null"

    # --- Pass 1: analyse -------------------------------------------------- #
    pass1_cmd = [
        ffmpeg_bin,
        "-i",
        str(input_path),
        *args,
        "-pass",
        "1",
        "-an",
        "-f",
        "null",
        "-y",
        null_target,
    ]

    _execute_ffmpeg(
        pass1_cmd,
        duration_seconds,
        progress_callback,
        error_prefix="FFmpeg pass 1 failed",
        offset=0.0,
        scale=50.0,
    )

    # --- Pass 2: encode --------------------------------------------------- #
    pass2_cmd = [
        ffmpeg_bin,
        "-i",
        str(input_path),
        *args,
        "-pass",
        "2",
        "-y",
        str(output_path),
    ]

    _execute_ffmpeg(
        pass2_cmd,
        duration_seconds,
        progress_callback,
        error_prefix="FFmpeg pass 2 failed",
        offset=50.0,
        scale=50.0,
    )

    # Clean up two-pass log files
    for log_file in Path.cwd().glob("ffmpeg2pass-*"):
        log_file.unlink(missing_ok=True)

    return output_path.resolve()
