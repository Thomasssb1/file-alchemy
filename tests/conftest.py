"""Global pytest fixtures and configurations."""

import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from pytestqt.qtbot import QtBot

from file_alchemy.engines import media_engine
from file_alchemy.engines.registry import ConversionRegistry

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from file_alchemy.ui.components import ResultsPanel, DropZone, FileListPanel
    from file_alchemy.ui.pages.compression_page import CompressionPage

# Use Qt's offscreen platform when no display is available (CI / headless).
# setdefault means this is a no-op when a real display is already configured.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


@pytest.fixture
def dummy_image(tmp_path: Path) -> Path:
    """Create a 100x100 RGB JPEG image."""
    img_path = tmp_path / "test.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(img_path, format="JPEG")
    return img_path


@pytest.fixture
def results_panel(qtbot) -> "ResultsPanel":
    from file_alchemy.ui.components import ResultsPanel

    panel = ResultsPanel()
    qtbot.addWidget(panel)
    panel.show()
    return panel


@pytest.fixture
def drop_zone(qtbot) -> "DropZone":
    from file_alchemy.ui.components import DropZone

    mock_callback = MagicMock()
    dz = DropZone(files_callback=mock_callback)
    dz._mock_cb = mock_callback  # Attach for assertions
    qtbot.addWidget(dz)
    return dz


@pytest.fixture
def file_list_panel(qtbot) -> "FileListPanel":
    from file_alchemy.ui.components import FileListPanel

    panel = FileListPanel()
    qtbot.addWidget(panel)
    panel.show()
    return panel


@pytest.fixture()
def compression_page(qtbot: QtBot) -> "CompressionPage":
    """Create a CompressionPage and register it with qtbot for cleanup."""
    from file_alchemy.ui.pages.compression_page import CompressionPage

    p = CompressionPage()
    qtbot.addWidget(p)
    p.show()
    return p


@pytest.fixture()
def mock_compression_worker():
    """Patch CompressionWorker so _start_compression never spawns a thread."""
    with patch("file_alchemy.ui.pages.compression_page.CompressionWorker") as cls:
        mock_w = MagicMock()
        mock_w.progress = MagicMock()
        mock_w.finished = MagicMock()
        mock_w.error = MagicMock()
        cls.return_value = mock_w
        yield cls
