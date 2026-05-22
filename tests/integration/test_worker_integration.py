"""Integration tests for Workers using real engines (no mocks)."""

from __future__ import annotations

from pathlib import Path

from file_alchemy.engines.compression.compression_mode import CompressionMode
from file_alchemy.engines.compression.compression_options import CompressionOptions
from file_alchemy.engines.registry import DEFAULT_REGISTRY
from file_alchemy.ui.pages.compression.compression_worker import CompressionWorker
from file_alchemy.ui.pages.media.conversion_worker import ConversionWorker
from tests.conftest import skip_no_ffmpeg


@skip_no_ffmpeg
def test_conversion_worker_wav_to_mp3(sample_wav: Path, tmp_path: Path) -> None:
    """ConversionWorker produces a real MP3 file using the real FFmpeg engine."""
    out = tmp_path / "out.mp3"
    route = DEFAULT_REGISTRY.get_route("wav", "mp3")
    assert route is not None

    worker = ConversionWorker(sample_wav, out, route)
    worker.run()

    assert out.exists()
    assert out.suffix == ".mp3"
    assert out.stat().st_size > 0


@skip_no_ffmpeg
def test_conversion_worker_mp4_to_gif(sample_mp4: Path, tmp_path: Path) -> None:
    """ConversionWorker converts MP4 to GIF (cross-format)."""
    out = tmp_path / "out.gif"
    route = DEFAULT_REGISTRY.get_route("mp4", "gif")
    assert route is not None

    worker = ConversionWorker(sample_mp4, out, route)
    worker.run()

    assert out.exists()
    assert out.suffix == ".gif"
    assert out.stat().st_size > 0


@skip_no_ffmpeg
def test_conversion_worker_png_to_ico(sample_png: Path, tmp_path: Path) -> None:
    """ConversionWorker converts PNG to ICO using convert_to_icon engine."""
    out = tmp_path / "out.ico"
    route = DEFAULT_REGISTRY.get_route("png", "ico")
    assert route is not None

    worker = ConversionWorker(sample_png, out, route)
    worker.run()

    assert out.exists()
    assert out.suffix == ".ico"
    assert out.stat().st_size > 0


@skip_no_ffmpeg
def test_conversion_worker_png_to_jpg(sample_png: Path, tmp_path: Path) -> None:
    """ConversionWorker converts PNG to JPG using real FFmpeg."""
    out = tmp_path / "out.jpg"
    route = DEFAULT_REGISTRY.get_route("png", "jpg")
    assert route is not None

    worker = ConversionWorker(sample_png, out, route)
    worker.run()

    assert out.exists()
    assert out.suffix == ".jpg"
    assert out.stat().st_size > 0


def test_compression_worker_real_pillow(sample_png: Path, tmp_path: Path) -> None:
    """CompressionWorker produces a real compressed PNG using the real Pillow engine."""
    out = tmp_path / "out_compressed.png"
    options = CompressionOptions(mode=CompressionMode.LOSSLESS)

    worker = CompressionWorker(sample_png, out, options, "image")
    worker.run()

    assert out.exists()
    assert out.stat().st_size > 0
    assert out.stat().st_size <= sample_png.stat().st_size


@skip_no_ffmpeg
def test_compression_worker_real_ffmpeg_media(sample_wav: Path, tmp_path: Path) -> None:
    """CompressionWorker compresses a WAV (media) using real FFmpeg."""
    out = tmp_path / "out_compressed.wav"
    options = CompressionOptions(mode=CompressionMode.LOSSY, quality=50)

    worker = CompressionWorker(sample_wav, out, options, "audio")
    worker.run()

    assert out.exists()
    assert out.stat().st_size > 0
    assert out.stat().st_size <= sample_wav.stat().st_size
