"""Fixtures specifically for integration tests."""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def sample_wav(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a 1-second silent WAV file using FFmpeg and clean up automatically."""
    tmp_dir = tmp_path_factory.mktemp("media")
    wav = tmp_dir / "silent.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "1",
            "-q:a",
            "9",
            str(wav),
        ],
        check=True,
        capture_output=True,
    )
    yield wav
    if wav.exists():
        wav.unlink()


@pytest.fixture
def sample_png(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a simple 100x100 red PNG file using FFmpeg and clean up automatically."""
    tmp_dir = tmp_path_factory.mktemp("media")
    png = tmp_dir / "dummy.png"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=100x100:d=1",
            "-vframes",
            "1",
            str(png),
        ],
        check=True,
        capture_output=True,
    )
    yield png
    if png.exists():
        png.unlink()


@pytest.fixture
def sample_mp4(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a 1-second test MP4 file using FFmpeg."""
    tmp_dir = tmp_path_factory.mktemp("media_mp4")
    mp4 = tmp_dir / "test.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=160x120:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(mp4),
        ],
        check=True,
        capture_output=True,
    )
    yield mp4
    if mp4.exists():
        mp4.unlink()
