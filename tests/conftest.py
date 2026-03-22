"""Global pytest fixtures and configurations."""

import shutil
from unittest.mock import patch

import pytest

from file_alchemy.engines import media_engine

_HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
skip_no_ffmpeg = pytest.mark.skipif(
    not _HAS_FFMPEG,
    reason="FFmpeg not found on PATH",
)


@pytest.fixture
def mock_ffmpeg_paths() -> None:
    """Mock _require_ffmpeg to return fake paths for unit tests."""
    with patch.object(
        media_engine, "_require_ffmpeg", return_value=("/ffmpeg", "/ffprobe")
    ):
        yield
