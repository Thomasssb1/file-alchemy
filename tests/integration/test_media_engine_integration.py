"""Integration tests for file_alchemy.engines.media_engine using real FFmpeg."""

from __future__ import annotations

from pathlib import Path

import pytest

from file_alchemy.engines import media_engine
from tests.conftest import skip_no_ffmpeg


@skip_no_ffmpeg
def test_probe_real_file(sample_wav: Path) -> None:
    """probe() returns expected keys for a minimal real file."""
    info = media_engine.probe(sample_wav)
    assert "format" in info
    assert "streams" in info
    assert float(info["format"]["duration"]) == pytest.approx(1.0, abs=0.1)


@skip_no_ffmpeg
def test_convert_wav_to_mp3(tmp_path: Path, sample_wav: Path) -> None:
    """convert() produces an mp3 file from a source WAV."""
    mp3 = tmp_path / "silent.mp3"
    progress_values: list[float] = []

    result = media_engine.convert(
        sample_wav, mp3, progress_callback=progress_values.append
    )

    assert result.exists()
    assert result.suffix == ".mp3"
    for pct in progress_values:
        assert 0.0 <= pct <= 100.0


@skip_no_ffmpeg
def test_convert_png_to_jpeg(tmp_path: Path, sample_png: Path) -> None:
    """convert() produces a jpeg image from a source PNG."""
    jpeg = tmp_path / "dummy.jpg"
    progress_values: list[float] = []

    result = media_engine.convert(
        sample_png, jpeg, progress_callback=progress_values.append
    )

    assert result.exists()
    assert result.suffix == ".jpg"
