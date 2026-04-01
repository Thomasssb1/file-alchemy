"""End-to-end integration tests for the full UI-to-engine flow."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from pytestqt.qtbot import QtBot

from file_alchemy.ui.pages.compression.compression_page import CompressionPage
from file_alchemy.ui.pages.media.media_page import MediaPage
from tests.conftest import skip_no_ffmpeg


@skip_no_ffmpeg
def test_media_conversion_e2e(qtbot: QtBot, sample_wav: Path, tmp_path: Path) -> None:
    """Full flow: add WAV -> select MP3 -> convert -> verify file on disk."""
    page = MediaPage()
    qtbot.addWidget(page)
    page.show()

    # Set a specific output directory to avoid cluttering the source folder
    page._output_dir = tmp_path
    page._output_dir_label.setText(str(tmp_path))

    # Simulate adding the sample WAV file
    page._on_files_added([sample_wav])

    # Ensure the format combo is populated and select 'mp3'
    index = page._format_combo.findText("mp3")
    assert index >= 0, f"MP3 format not found in combo box. Items: {[page._format_combo.itemText(i) for i in range(page._format_combo.count())]}"
    page._format_combo.setCurrentIndex(index)

    # The convert button should now be enabled
    assert page._convert_btn.isEnabled()

    # Click 'Convert' and wait for the batch to finish
    qtbot.mouseClick(page._convert_btn, Qt.MouseButton.LeftButton)

    # BaseBatchPage re-enables the button when _pending reaches 0
    qtbot.waitUntil(lambda: page._convert_btn.isEnabled(), timeout=10000)

    # Verify the output file exists in the temp directory
    expected_output = tmp_path / f"{sample_wav.stem}.mp3"
    assert expected_output.exists(), f"Expected output {expected_output} was not created."
    assert expected_output.stat().st_size > 0


def test_image_compression_e2e(qtbot: QtBot, sample_png: Path, tmp_path: Path) -> None:
    """Full flow: add PNG -> select Lossy -> compress -> verify file on disk."""
    page = CompressionPage()
    qtbot.addWidget(page)
    page.show()

    # Set output directory
    page._output_dir = tmp_path

    # Simulate adding the sample PNG file
    page._on_files_added([sample_png])

    # Select 'Lossy' mode
    page._radio_lossy.setChecked(True)
    assert page._quality_widget.isVisible()

    # The compress button should be enabled
    assert page._compress_btn.isEnabled()

    # Click 'Compress' and wait for completion
    qtbot.mouseClick(page._compress_btn, Qt.MouseButton.LeftButton)

    # Wait for the worker to finish and the UI to reset
    qtbot.waitUntil(lambda: page._compress_btn.isEnabled(), timeout=10000)

    # Verify the output file (CompressionPage uses {stem}_compressed{suffix})
    expected_output = tmp_path / f"{sample_png.stem}_compressed{sample_png.suffix}"
    assert expected_output.exists(), f"Expected output {expected_output} was not created."
    # Lossy compression should ideally result in a non-zero file
    assert expected_output.stat().st_size > 0
