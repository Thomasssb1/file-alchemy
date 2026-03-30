"""Unit tests for file_alchemy.engines.image_engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from file_alchemy.engines.compression_options import CompressionMode, CompressionOptions
from file_alchemy.engines.image_engine import (
    _binary_search_quality,
    _resolve_format,
    compress_image,
)
from file_alchemy.errors.media_conversion_error import MediaConversionError


@pytest.mark.parametrize(
    "ext, expected",
    [
        ("jpg", "JPEG"),
        ("jpeg", "JPEG"),
        ("png", "PNG"),
        ("webp", "WEBP"),
        ("avif", "AVIF"),
        ("tiff", "TIFF"),
        ("tif", "TIFF"),
    ],
)
def test_resolve_format_supported(ext: str, expected: str) -> None:
    """Test resolution of standard format variations, including jpeg vs jpg."""
    assert _resolve_format(ext) == expected


def test_resolve_format_unsupported() -> None:
    """Test resolution failures raise expected error."""
    with pytest.raises(MediaConversionError):
        _resolve_format("unknown")


def test_compress_image_unsupported_format(dummy_image: Path, tmp_path: Path) -> None:
    """Test giving an unsupported output format extension fails cleanly."""
    out_path = tmp_path / "out.unsupported"
    opts = CompressionOptions(CompressionMode.LOSSY)
    with pytest.raises(MediaConversionError, match="Unsupported image format"):
        compress_image(dummy_image, out_path, opts)


def test_binary_search_quality(dummy_image: Path) -> None:
    """Test binary search logic algorithm correctly converges on an appropriate quality."""
    img = Image.open(dummy_image)
    kwargs = {"optimize": True}
    target_bytes = 800

    best_q = _binary_search_quality(img, "JPEG", target_bytes, kwargs, lo=1, hi=95)

    import io

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=best_q, optimize=True)
    assert len(buf.getvalue()) <= target_bytes

    if best_q < 95:
        buf2 = io.BytesIO()
        img.save(buf2, format="JPEG", quality=best_q + 1, optimize=True)
        assert len(buf2.getvalue()) > target_bytes


@pytest.mark.parametrize("target_bytes", [0, 800, 99999999])
def test_target_size_various_values(
    dummy_image: Path, tmp_path: Path, target_bytes: int
) -> None:
    """Test target size with completely out-of-scale bounds (0 bytes, highly oversized) and valid bytes."""
    out_path = tmp_path / f"out_{target_bytes}.jpg"
    opts = CompressionOptions(CompressionMode.TARGET_SIZE, target_bytes=target_bytes)

    res = compress_image(dummy_image, out_path, opts)
    assert res.exists()


def test_target_size_unsupported_format(dummy_image: Path, tmp_path: Path) -> None:
    """Test TARGET_SIZE mode with an engine-unsupported format (PNG)."""
    out_path = tmp_path / "out.png"
    opts = CompressionOptions(CompressionMode.TARGET_SIZE, target_bytes=1000)
    with pytest.raises(
        MediaConversionError, match="does not support target-size compression"
    ):
        compress_image(dummy_image, out_path, opts)


@pytest.mark.parametrize("quality", [-10, 0, 50, 100, 150])
def test_compression_quality_ranges(
    dummy_image: Path, tmp_path: Path, quality: int
) -> None:
    """Test lossy compression automatically clamps/handles edge-case positive and negative qualities."""
    out_path = tmp_path / f"out_q{quality}.jpg"
    opts = CompressionOptions(CompressionMode.LOSSY, quality=quality)

    res = compress_image(dummy_image, out_path, opts)
    assert res.exists()


def test_compress_image_lossless(dummy_image: Path, tmp_path: Path) -> None:
    """Test lossless correctly resolves path and fires progress callback incrementally."""
    out_path = tmp_path / "out.png"
    opts = CompressionOptions(CompressionMode.LOSSLESS)
    cb = MagicMock()

    res = compress_image(dummy_image, out_path, opts, progress_callback=cb)

    assert res == out_path.resolve()
    assert out_path.exists()
    cb.assert_called_once_with(100.0)


def test_compress_image_target_size(dummy_image: Path, tmp_path: Path) -> None:
    """Test standard target size mode creates realistically sized image."""
    out_path = tmp_path / "out.jpg"
    opts = CompressionOptions(CompressionMode.TARGET_SIZE, target_bytes=800)

    res = compress_image(dummy_image, out_path, opts)

    assert res == out_path.resolve()
    assert out_path.exists()
    assert out_path.stat().st_size <= 800


def test_compress_image_fails_open(tmp_path: Path) -> None:
    """Test reading invalid media correctly fails with open error."""
    bad_path = tmp_path / "bad.jpg"
    bad_path.write_text("not an image")
    out_path = tmp_path / "out.jpg"
    opts = CompressionOptions(CompressionMode.LOSSY)

    with pytest.raises(MediaConversionError, match="Failed to open image"):
        compress_image(bad_path, out_path, opts)


def test_compress_image_fails_save(dummy_image: Path, tmp_path: Path) -> None:
    """Test exceptions thrown natively during Pillow.save() are safely caught."""
    out_path = tmp_path / "out.jpg"
    opts = CompressionOptions(CompressionMode.LOSSY)

    with patch("PIL.Image.Image.save", side_effect=OSError("Disk full test")):
        with pytest.raises(MediaConversionError, match="Failed to save image"):
            compress_image(dummy_image, out_path, opts)


def test_compress_image_rgba_to_jpeg_conversion(tmp_path: Path) -> None:
    """Test saving an image with an Alpha channel to JPEG properly strips the alpha first."""
    img_path = tmp_path / "alpha.png"
    img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    img.save(img_path, format="PNG")

    out_path = tmp_path / "out.jpg"
    opts = CompressionOptions(CompressionMode.LOSSY, quality=80)

    res = compress_image(img_path, out_path, opts)

    assert res.exists()
    opened = Image.open(res)
    assert opened.mode == "RGB"
