"""Pillow-backed image compression engine."""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageSequence

from file_alchemy.engines.compression.compression_mode import CompressionMode
from file_alchemy.engines.compression.compression_options import CompressionOptions
from file_alchemy.errors.media_conversion_error import MediaConversionError

# Pillow format names keyed by file extension
_EXT_TO_FORMAT: dict[str, str] = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
    "tif": "TIFF",
    "ico": "ICO",
    "avif": "AVIF",
    "gif": "GIF",
}

_GIF_MIN_COLORS = 2
_GIF_MAX_COLORS = 256


def _resolve_format(output_ext: str) -> str:
    """Return the Pillow format string for a given extension.

    Args:
        output_ext: The file extension stripped of its dot (e.g. "jpg")

    Returns:
        The matched Pillow format string (e.g. "JPEG")

    Raises:
        MediaConversionError: If the format is unknown to our mapping.

    """
    fmt = _EXT_TO_FORMAT.get(output_ext.lower().lstrip("."))
    if not fmt:
        raise MediaConversionError(
            f"Unsupported image format for compression: .{output_ext}"
        )
    return fmt


def _save_to_bytes(img: Image.Image, fmt: str, **kwargs: object) -> bytes:
    """Save *img* into an in-memory buffer and return raw bytes."""
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def _binary_search_quality(
    img: Image.Image,
    fmt: str,
    target_bytes: int,
    base_kwargs: dict,
    lo: int = 1,
    hi: int = 95,
) -> int:
    """Find the highest quality whose output is ≤ *target_bytes*.

    Uses a binary search on the quality parameter. If even quality=1
    exceeds the target, returns 1 (the smallest file we can produce).
    """
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        kwargs = {**base_kwargs, "quality": mid}
        data = _save_to_bytes(img, fmt, **kwargs)
        if len(data) <= target_bytes:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _quality_to_gif_colors(quality: int) -> int:
    """Map user-facing quality 1-100 to a GIF palette size of 2-256 colors."""
    clamped = max(1, min(quality, 100))
    return round(
        _GIF_MIN_COLORS + (_GIF_MAX_COLORS - _GIF_MIN_COLORS) * (clamped - 1) / 99
    )


def _prepare_gif_frames(
    img: Image.Image,
    colors: int | None,
    frame_step: int = 1,
) -> tuple[list[Image.Image], dict[str, object]]:
    """Return GIF frames and save options while preserving animation metadata."""
    frames: list[Image.Image] = []
    durations: list[int] = []
    disposals: list[int] = []
    frame_step = max(1, frame_step)

    for frame_index, frame in enumerate(ImageSequence.Iterator(img)):
        frame_duration = int(frame.info.get("duration", img.info.get("duration", 100)))

        if frame_index % frame_step != 0:
            if durations:
                durations[-1] += frame_duration
            continue

        copied_frame = frame.copy()
        if colors is not None:
            copied_frame = copied_frame.convert("RGBA").quantize(
                colors=colors,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.NONE,
            )

        frames.append(copied_frame)
        durations.append(frame_duration)

        disposal = getattr(frame, "disposal_method", frame.info.get("disposal"))
        if disposal is not None:
            disposals.append(int(disposal))

    if not frames:
        raise MediaConversionError("GIF contains no frames.")

    save_kwargs: dict[str, object] = {"optimize": True}
    if len(frames) > 1:
        save_kwargs["save_all"] = True
        save_kwargs["append_images"] = frames[1:]
        save_kwargs["duration"] = durations
    else:
        save_kwargs["duration"] = durations[0]

    loop = img.info.get("loop")
    if loop is not None:
        save_kwargs["loop"] = int(loop)

    if len(disposals) == len(frames):
        save_kwargs["disposal"] = disposals if len(disposals) > 1 else disposals[0]

    return frames, save_kwargs


def _save_gif_to_bytes(
    frames: list[Image.Image], save_kwargs: dict[str, object]
) -> bytes:
    """Save GIF frames into an in-memory buffer and return raw bytes."""
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", **save_kwargs)
    return buf.getvalue()


def _binary_search_gif_colors(
    img: Image.Image,
    target_bytes: int,
    frame_step: int,
    lo: int = _GIF_MIN_COLORS,
    hi: int = _GIF_MAX_COLORS,
) -> int:
    """Find the largest palette size whose GIF output is <= *target_bytes*.

    Uses a binary search on GIF palette size. If even the smallest palette
    size exceeds the target, returns ``lo`` (the smallest file we can
    produce).
    """
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        frames, save_kwargs = _prepare_gif_frames(img, mid, frame_step)
        data = _save_gif_to_bytes(frames, save_kwargs)
        if len(data) <= target_bytes:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _compress_gif_to_bytes(img: Image.Image, options: CompressionOptions) -> bytes:
    """Compress a GIF while preserving animation metadata and optionally sampling frames."""
    colors: int | None = None
    frame_step = max(1, options.gif_frame_step)
    if options.mode is CompressionMode.LOSSY:
        colors = _quality_to_gif_colors(options.quality)
    elif options.mode is CompressionMode.TARGET_SIZE and options.target_bytes:
        colors = _binary_search_gif_colors(img, options.target_bytes, frame_step)

    frames, save_kwargs = _prepare_gif_frames(img, colors, frame_step)
    return _save_gif_to_bytes(frames, save_kwargs)


def compress_image(
    input_path: str | Path,
    output_path: str | Path,
    options: CompressionOptions,
    progress_callback: Callable[[float], None] | None = None,
) -> Path:
    """Compress an image file according to *options*.

    Args:
        input_path:  Source image file.
        output_path: Destination; its extension determines the format.
        options:     Compression settings (mode, quality, target_bytes).
        progress_callback: Optional callback receiving 0–100 progress.

    Returns:
        The resolved ``Path`` of the created output file.

    Raises:
        MediaConversionError: If the format is unsupported or Pillow fails.

    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_ext = output_path.suffix.lstrip(".").lower()
    fmt = _resolve_format(output_ext)

    try:
        with Image.open(input_path) as opened_img:
            if fmt == "GIF":
                try:
                    gif_data = _compress_gif_to_bytes(opened_img, options)
                except MediaConversionError:
                    raise
                except Exception as exc:
                    raise MediaConversionError(
                        f"Failed to save image: {output_path}", stderr=str(exc)
                    ) from exc

                try:
                    output_path.write_bytes(gif_data)
                except Exception as exc:
                    raise MediaConversionError(
                        f"Failed to save image: {output_path}", stderr=str(exc)
                    ) from exc

                if progress_callback:
                    progress_callback(100.0)
                return output_path.resolve()

            # Ensure RGB for JPEG (which cannot handle alpha in compression)
            if fmt == "JPEG" and opened_img.mode in {"RGBA", "P", "LA"}:
                img = opened_img.convert("RGB")
            else:
                # Ensure we hold an in-memory copy after the file is closed
                img = opened_img.copy()
    except MediaConversionError:
        raise
    except Exception as exc:
        raise MediaConversionError(
            f"Failed to open image: {input_path}", stderr=str(exc)
        ) from exc

    kwargs = options.to_pillow_kwargs(output_ext)

    if options.mode is CompressionMode.TARGET_SIZE and options.target_bytes:
        if fmt in {"JPEG", "WEBP", "AVIF"}:
            best_quality = _binary_search_quality(
                img, fmt, options.target_bytes, kwargs
            )
            kwargs["quality"] = best_quality
        else:
            raise MediaConversionError(
                f"Format {output_ext.upper()} does not support target-size compression."
            )
    try:
        img.save(output_path, format=fmt, **kwargs)
    except Exception as exc:
        raise MediaConversionError(
            f"Failed to save image: {output_path}", stderr=str(exc)
        ) from exc

    if progress_callback:
        progress_callback(100.0)

    return output_path.resolve()
