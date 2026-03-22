"""Global pytest fixtures and configurations."""

import shutil
from unittest.mock import MagicMock, patch

import pytest

from file_alchemy.engines import media_engine
from file_alchemy.engines.registry import ConversionRegistry

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


@pytest.fixture
def empty_registry() -> ConversionRegistry:
    """Return a fresh, empty registry for isolation."""
    return ConversionRegistry()


@pytest.fixture
def mock_engine_fn() -> MagicMock:
    """Return a generic mocked engine function."""
    return MagicMock()
