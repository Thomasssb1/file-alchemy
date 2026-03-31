"""Component tests for the CompressionPage UI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytestqt.qtbot import QtBot

from file_alchemy.engines.compression_options import CompressionMode
from file_alchemy.ui.pages.compression_page import CompressionPage, _format_size


def _add_files(page: CompressionPage, *names: str, tmp_path: Path) -> list[Path]:
    paths = [tmp_path / name for name in names]
    for p in paths:
        p.touch()
    page._on_files_added(paths)
    return paths


@pytest.fixture
def page(qtbot: QtBot) -> CompressionPage:
    p = CompressionPage()
    qtbot.addWidget(p)
    p.show()
    return p


@pytest.fixture
def mock_compression_worker():
    with patch("file_alchemy.ui.pages.compression_page.CompressionWorker") as cls:
        mock_w = MagicMock()
        mock_w.progress = MagicMock()
        mock_w.finished = MagicMock()
        mock_w.error = MagicMock()
        cls.return_value = mock_w
        yield cls


def test_format_size() -> None:
    assert _format_size(500) == "500 B"
    assert _format_size(1500) == "1.5 KB"
    assert _format_size(1048576) == "1.0 MB"
    assert _format_size(1572864) == "1.5 MB"


def test_initial_state(page: CompressionPage) -> None:
    assert page._radio_lossless.isChecked()
    assert not page._radio_lossy.isChecked()
    assert not page._radio_target.isChecked()

    assert not page._quality_widget.isVisible()
    assert not page._target_widget.isVisible()
    assert not page._compress_btn.isEnabled()


def test_controls_visibility_toggles(page: CompressionPage) -> None:
    page._radio_lossy.setChecked(True)
    assert page._quality_widget.isVisible()
    assert not page._target_widget.isVisible()

    page._radio_target.setChecked(True)
    assert not page._quality_widget.isVisible()
    assert page._target_widget.isVisible()


def test_slider_updates_label(page: CompressionPage) -> None:
    page._quality_slider.setValue(42)
    assert "42" in page._quality_label.text()


def test_get_current_options(page: CompressionPage) -> None:
    # Lossless
    page._radio_lossless.setChecked(True)
    opts1 = page._get_current_options()
    assert opts1.mode == CompressionMode.LOSSLESS

    # Lossy
    page._radio_lossy.setChecked(True)
    page._quality_slider.setValue(88)
    opts2 = page._get_current_options()
    assert opts2.mode == CompressionMode.LOSSY
    assert opts2.quality == 88

    # Target
    page._radio_target.setChecked(True)
    page._target_spinbox.setValue(10)
    page._target_unit.setCurrentIndex(1)  # MB
    opts3 = page._get_current_options()
    assert opts3.mode == CompressionMode.TARGET_SIZE
    assert opts3.target_bytes == 10 * 1024 * 1024


def test_add_files_enables_compress(page: CompressionPage, tmp_path: Path) -> None:
    _add_files(page, "video.mp4", tmp_path=tmp_path)
    assert page._compress_btn.isEnabled()
    assert page._file_panel._list_widget.count() == 1


def test_start_compression_starts_worker(
    page: CompressionPage, tmp_path: Path, mock_compression_worker: MagicMock
) -> None:
    _add_files(page, "video.mp4", tmp_path=tmp_path)
    page._start_compression()
    mock_compression_worker.assert_called_once()
    assert not page._compress_btn.isEnabled()


def test_on_finished_updates_results_list(
    page: CompressionPage, tmp_path: Path
) -> None:
    _add_files(page, "video.mp4", tmp_path=tmp_path)
    out_path = tmp_path / "video_compressed.mp4"
    out_path.touch()

    with patch("file_alchemy.ui.pages.compression_page.InfoBar"):
        # Original 10MB -> Final 5MB (50% reduction)
        page._pending = 1
        page._on_finished(out_path, 10 * 1024 * 1024, 5 * 1024 * 1024)

    assert page._results_panel.count == 1
    item = page._results_panel._list_widget.item(0)
    widget = page._results_panel._list_widget.itemWidget(item)
    item_text = widget.label.text()
    assert "video_compressed.mp4" in item_text
    assert "10.0 MB" in item_text
    assert "5.0 MB" in item_text
    assert "50.0%" in item_text
    assert "↓" in item_text


def test_on_finished_size_increase(page: CompressionPage, tmp_path: Path) -> None:
    _add_files(page, "video.mp4", tmp_path=tmp_path)
    out_path = tmp_path / "video_compressed.mp4"
    out_path.touch()

    with patch("file_alchemy.ui.pages.compression_page.InfoBar"):
        # Original 10MB -> Final 15MB
        page._pending = 1
        page._on_finished(out_path, 10 * 1024 * 1024, 15 * 1024 * 1024)

    assert page._results_panel.count == 1
    item = page._results_panel._list_widget.item(0)
    widget = page._results_panel._list_widget.itemWidget(item)
    item_text = widget.label.text()
    assert "10.0 MB" in item_text
    assert "15.0 MB" in item_text
    assert "50.0%" in item_text
    assert "↑" in item_text


def test_estimated_size_updates(page: CompressionPage, tmp_path: Path) -> None:
    f = tmp_path / "video.mp4"
    f.write_text("x" * 1000)  # 1000 bytes
    page._on_files_added([f])

    # Lossless mode should show ~1000 B
    page._radio_lossless.setChecked(True)
    assert "1000 B" in page._estimate_label.text()

    # Target mode should precisely show target
    page._radio_target.setChecked(True)
    page._target_spinbox.setValue(4)
    page._target_unit.setCurrentIndex(0)  # KB
    assert "4.0 KB" in page._estimate_label.text()
    assert "≈" not in page._estimate_label.text()  # Exact target
