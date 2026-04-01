"""Pillow-backed image compression engine."""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

from PIL import Image

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
}


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
            # Ensure RGB for JPEG (which cannot handle alpha in compression)
            if fmt == "JPEG" and opened_img.mode in {"RGBA", "P", "LA"}:
                img = opened_img.convert("RGB")
            else:
                # Ensure we hold an in-memory copy after the file is closed
                img = opened_img.copy()
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
