"""Component tests for the CompressionPage UI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QMimeData, QPointF, QUrl, Qt
from PyQt6.QtGui import QDropEvent

from file_alchemy.engines.compression_options import CompressionMode
from file_alchemy.ui.pages.compression_page import CompressionPage, _format_size


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _add_files(page: CompressionPage, *names: str, tmp_path: Path) -> list[Path]:
    """Touch fake files in *tmp_path* and feed them through _on_files_added."""
    paths = [tmp_path / name for name in names]
    for p in paths:
        p.touch()
    page._on_files_added(paths)
    return paths


def _make_drop_event(urls: list[QUrl]) -> QDropEvent:
    """Build a synthetic QDropEvent carrying the given URLs.

    The QMimeData is stored as ``event._mime`` so Python's refcount keeps it
    alive for the entire duration of the ``dropEvent`` call — without this,
    the GC can collect it mid-call and cause an access violation on Windows.
    """
    mime = QMimeData()
    mime.setUrls(urls)
    event = QDropEvent(
        QPointF(0, 0),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    event._mime = mime  # prevent GC
    return event


def _get_result_text(page: CompressionPage, index: int = 0) -> str:
    """Return the label text of the results panel item at *index*."""
    item = page._results_panel._list_widget.item(index)
    widget = page._results_panel._list_widget.itemWidget(item)
    return widget.label.text()


# --------------------------------------------------------------------------- #
# _format_size
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "size_bytes, expected",
    [
        (0, "0 B"),
        (500, "500 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1_048_576, "1.0 MB"),
        (1_572_864, "1.5 MB"),
        (1_073_741_824, "1.0 GB"),
        (1_610_612_736, "1.5 GB"),
    ],
)
def test_format_size(size_bytes: int, expected: str) -> None:
    assert _format_size(size_bytes) == expected


# --------------------------------------------------------------------------- #
# Initial state
# --------------------------------------------------------------------------- #


def test_initial_state(compression_page: CompressionPage) -> None:
    assert compression_page._radio_lossless.isChecked()
    assert not compression_page._radio_lossy.isChecked()
    assert not compression_page._radio_target.isChecked()

    assert not compression_page._quality_widget.isVisible()
    assert not compression_page._target_widget.isVisible()
    assert not compression_page._compress_btn.isEnabled()
    assert not compression_page._progress_bar.isVisible()
    assert compression_page._output_dir is None
    assert compression_page._pending == 0
    assert compression_page._batch_total == 0


# --------------------------------------------------------------------------- #
# Controls visibility across all 3 modes
# --------------------------------------------------------------------------- #


def test_controls_visibility_lossy_mode(compression_page: CompressionPage) -> None:
    compression_page._radio_lossy.setChecked(True)
    assert compression_page._quality_widget.isVisible()
    assert not compression_page._target_widget.isVisible()


def test_controls_visibility_target_mode(compression_page: CompressionPage) -> None:
    compression_page._radio_target.setChecked(True)
    assert not compression_page._quality_widget.isVisible()
    assert compression_page._target_widget.isVisible()


def test_controls_visibility_lossless_mode(compression_page: CompressionPage) -> None:
    # Start in lossy so we can verify the revert
    compression_page._radio_lossy.setChecked(True)
    compression_page._radio_lossless.setChecked(True)
    assert not compression_page._quality_widget.isVisible()
    assert not compression_page._target_widget.isVisible()


def test_slider_updates_label(compression_page: CompressionPage) -> None:
    compression_page._quality_slider.setValue(42)
    assert "42" in compression_page._quality_label.text()


# --------------------------------------------------------------------------- #
# _get_current_options — edge cases across all 3 modes
# --------------------------------------------------------------------------- #


def test_get_current_options_lossless(compression_page: CompressionPage) -> None:
    compression_page._radio_lossless.setChecked(True)
    opts = compression_page._get_current_options()
    assert opts.mode == CompressionMode.LOSSLESS
    # quality field exists but is irrelevant for lossless
    assert opts.target_bytes is None


def test_get_current_options_lossy_min_quality(
    compression_page: CompressionPage,
) -> None:
    """Slider minimum (1) must survive the round-trip."""
    compression_page._radio_lossy.setChecked(True)
    compression_page._quality_slider.setValue(1)
    opts = compression_page._get_current_options()
    assert opts.mode == CompressionMode.LOSSY
    assert opts.quality == 1


def test_get_current_options_lossy_max_quality(
    compression_page: CompressionPage,
) -> None:
    """Slider maximum (100) must survive the round-trip."""
    compression_page._radio_lossy.setChecked(True)
    compression_page._quality_slider.setValue(100)
    opts = compression_page._get_current_options()
    assert opts.quality == 100


@pytest.mark.parametrize(
    "value, unit_index, expected_bytes",
    [
        (1, 0, 1 * 1024),  # minimum KB
        (800, 0, 800 * 1024),  # typical KB
        (1, 1, 1 * 1024 * 1024),  # minimum MB
        (10, 1, 10 * 1024 * 1024),  # typical MB
        (999999, 0, 999999 * 1024),  # spinbox maximum in KB
        (999999, 1, 999999 * 1024 * 1024),  # spinbox maximum in MB
    ],
)
def test_get_current_options_target_size_edge_cases(
    compression_page: CompressionPage,
    value: int,
    unit_index: int,
    expected_bytes: int,
) -> None:
    compression_page._radio_target.setChecked(True)
    compression_page._target_spinbox.setValue(value)
    compression_page._target_unit.setCurrentIndex(unit_index)
    opts = compression_page._get_current_options()
    assert opts.mode == CompressionMode.TARGET_SIZE
    assert opts.target_bytes == expected_bytes


# --------------------------------------------------------------------------- #
# File loading — browse (manual) path
# --------------------------------------------------------------------------- #


def test_browse_button_adds_files(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    fake = tmp_path / "track.mp3"
    fake.touch()

    with patch(
        "file_alchemy.ui.components.drop_zone.QFileDialog.getOpenFileNames",
        return_value=([str(fake)], ""),
    ):
        compression_page._drop_zone._open_file_dialog()

    assert compression_page._file_panel._list_widget.count() == 1
    assert compression_page._file_panel.files[0].name == "track.mp3"
    assert compression_page._compress_btn.isEnabled()


def test_browse_cancel_adds_nothing(compression_page: CompressionPage) -> None:
    with patch(
        "file_alchemy.ui.components.drop_zone.QFileDialog.getOpenFileNames",
        return_value=([], ""),
    ):
        compression_page._drop_zone._open_file_dialog()

    assert compression_page._file_panel._list_widget.count() == 0
    assert not compression_page._compress_btn.isEnabled()


def test_browse_filters_unsupported_formats(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """Unsupported files selected via browser must be silently dropped."""
    good = tmp_path / "image.jpg"
    bad = tmp_path / "spreadsheet.xlsx"
    good.touch()
    bad.touch()

    with patch(
        "file_alchemy.ui.components.drop_zone.QFileDialog.getOpenFileNames",
        return_value=([str(bad), str(good)], ""),
    ):
        compression_page._drop_zone._open_file_dialog()

    assert compression_page._file_panel._list_widget.count() == 1
    assert compression_page._file_panel.files[0].name == "image.jpg"


# --------------------------------------------------------------------------- #
# File loading — drag-and-drop path
# --------------------------------------------------------------------------- #


def test_drag_drop_adds_valid_file(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    fake = tmp_path / "video.mp4"
    fake.touch()

    event = _make_drop_event([QUrl.fromLocalFile(str(fake))])
    compression_page._drop_zone.dropEvent(event)

    assert compression_page._file_panel._list_widget.count() == 1
    assert compression_page._file_panel.files[0].name == "video.mp4"
    assert compression_page._compress_btn.isEnabled()


def test_drag_drop_ignores_non_file_urls(compression_page: CompressionPage) -> None:
    event = _make_drop_event([QUrl("https://example.com/video.mp4")])
    compression_page._drop_zone.dropEvent(event)
    assert compression_page._file_panel._list_widget.count() == 0


def test_drag_drop_filters_unsupported_formats(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    good = tmp_path / "audio.flac"
    bad = tmp_path / "archive.zip"
    good.touch()
    bad.touch()

    event = _make_drop_event(
        [QUrl.fromLocalFile(str(bad)), QUrl.fromLocalFile(str(good))]
    )
    compression_page._drop_zone.dropEvent(event)

    assert compression_page._file_panel._list_widget.count() == 1
    assert compression_page._file_panel.files[0].name == "audio.flac"


def test_drag_drop_multiple_files_added(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    files = [tmp_path / name for name in ("a.mp4", "b.mp3", "c.png")]
    for f in files:
        f.touch()

    event = _make_drop_event([QUrl.fromLocalFile(str(f)) for f in files])
    compression_page._drop_zone.dropEvent(event)

    assert compression_page._file_panel._list_widget.count() == 3


def test_drag_drop_deduplicates_files(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """Dropping the same file a second time must not add a duplicate."""
    fake = tmp_path / "photo.jpg"
    fake.touch()

    event = _make_drop_event([QUrl.fromLocalFile(str(fake))])
    compression_page._drop_zone.dropEvent(event)
    compression_page._drop_zone.dropEvent(event)

    assert compression_page._file_panel._list_widget.count() == 1


# --------------------------------------------------------------------------- #
# Clearing the file list
# --------------------------------------------------------------------------- #


def test_clear_list_disables_compress_button(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    _add_files(compression_page, "video.mp4", tmp_path=tmp_path)
    assert compression_page._compress_btn.isEnabled()

    compression_page._file_panel.clear()

    assert not compression_page._compress_btn.isEnabled()
    assert compression_page._file_panel._list_widget.count() == 0


def test_clear_list_resets_estimate_label(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    f = tmp_path / "video.mp4"
    f.write_text("x" * 1000)
    compression_page._on_files_added([f])
    # Estimate is non-placeholder while file is loaded
    assert "--" not in compression_page._estimate_label.text()

    compression_page._file_panel.clear()

    assert "Est. output: ≈ --" in compression_page._estimate_label.text()


def test_clear_and_re_add_re_enables_compress(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    _add_files(compression_page, "audio.mp3", tmp_path=tmp_path)
    compression_page._file_panel.clear()

    _add_files(compression_page, "audio.flac", tmp_path=tmp_path)
    assert compression_page._compress_btn.isEnabled()


# --------------------------------------------------------------------------- #
# Multi-file selection — different configs update estimate per-row
# --------------------------------------------------------------------------- #


def test_three_files_estimate_updates_per_selection(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """Selecting each row of a 3-file list must update the estimate for that file."""
    small = tmp_path / "small.jpg"
    medium = tmp_path / "medium.mp4"
    large = tmp_path / "large.flac"
    small.write_bytes(b"x" * 100)
    medium.write_bytes(b"x" * 10_000)
    large.write_bytes(b"x" * 1_000_000)

    compression_page._on_files_added([small, medium, large])
    compression_page._radio_lossless.setChecked(True)

    # Select small file
    compression_page._file_panel._list_widget.setCurrentRow(0)
    label_small = compression_page._estimate_label.text()

    # Select medium file
    compression_page._file_panel._list_widget.setCurrentRow(1)
    label_medium = compression_page._estimate_label.text()

    # Select large file
    compression_page._file_panel._list_widget.setCurrentRow(2)
    label_large = compression_page._estimate_label.text()

    # Each file has a different size so the estimates must all differ
    assert label_small != label_medium
    assert label_medium != label_large
    assert label_small != label_large


def test_three_files_lossy_estimate_scales_with_quality(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """Changing quality while a file is selected must update the estimate."""
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 100_000)
    compression_page._on_files_added([f])
    compression_page._radio_lossy.setChecked(True)

    compression_page._quality_slider.setValue(10)
    label_low = compression_page._estimate_label.text()

    compression_page._quality_slider.setValue(90)
    label_high = compression_page._estimate_label.text()

    # Higher quality → larger estimated output
    assert label_low != label_high


def test_three_files_target_mode_shows_same_target_regardless_of_selection(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """In target-size mode the display value is always the chosen target, not the file size."""
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    a.write_bytes(b"x" * 1000)
    b.write_bytes(b"x" * 100_000)
    compression_page._on_files_added([a, b])

    compression_page._radio_target.setChecked(True)
    compression_page._target_spinbox.setValue(5)
    compression_page._target_unit.setCurrentIndex(1)  # MB

    compression_page._file_panel._list_widget.setCurrentRow(0)
    label_a = compression_page._estimate_label.text()

    compression_page._file_panel._list_widget.setCurrentRow(1)
    label_b = compression_page._estimate_label.text()

    assert label_a == label_b
    assert "5.0 MB" in label_a
    # Target is exact — no approximation prefix
    assert "≈" not in label_a


# --------------------------------------------------------------------------- #
# _resolve_output_path — collision avoidance
# --------------------------------------------------------------------------- #


def test_resolve_output_path_no_collision(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    src = tmp_path / "image.png"
    src.touch()
    assert (
        compression_page._resolve_output_path(src) == tmp_path / "image_compressed.png"
    )


def test_resolve_output_path_avoids_collision(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    src = tmp_path / "image.png"
    src.touch()
    (tmp_path / "image_compressed.png").touch()
    assert (
        compression_page._resolve_output_path(src)
        == tmp_path / "image_compressed_2.png"
    )


def test_resolve_output_path_avoids_multiple_collisions(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    src = tmp_path / "image.png"
    src.touch()
    (tmp_path / "image_compressed.png").touch()
    (tmp_path / "image_compressed_2.png").touch()
    assert (
        compression_page._resolve_output_path(src)
        == tmp_path / "image_compressed_3.png"
    )


def test_resolve_output_path_uses_output_dir(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    compression_page._output_dir = out_dir
    src = tmp_path / "track.mp3"
    src.touch()
    result = compression_page._resolve_output_path(src)
    assert result.parent == out_dir
    assert result.name == "track_compressed.mp3"


# --------------------------------------------------------------------------- #
# Compression start / worker lifecycle
# --------------------------------------------------------------------------- #


def test_start_compression_starts_worker(
    compression_page: CompressionPage,
    tmp_path: Path,
    mock_compression_worker: MagicMock,
) -> None:
    _add_files(compression_page, "video.mp4", tmp_path=tmp_path)
    compression_page._start_compression()
    mock_compression_worker.assert_called_once()
    assert not compression_page._compress_btn.isEnabled()


def test_start_compression_no_files_is_noop(
    compression_page: CompressionPage,
    mock_compression_worker: MagicMock,
) -> None:
    compression_page._start_compression()
    mock_compression_worker.assert_not_called()


def test_progress_bar_shown_when_compression_starts(
    compression_page: CompressionPage,
    tmp_path: Path,
    mock_compression_worker: MagicMock,
) -> None:
    _add_files(compression_page, "video.mp4", tmp_path=tmp_path)
    compression_page._start_compression()
    assert compression_page._progress_bar.isVisible()


# --------------------------------------------------------------------------- #
# Queuing system — multiple files
# --------------------------------------------------------------------------- #


def test_all_files_queued_on_start(
    compression_page: CompressionPage,
    tmp_path: Path,
    mock_compression_worker: MagicMock,
) -> None:
    """Three loaded files → 1 worker running immediately + 2 in the queue."""
    _add_files(compression_page, "a.mp4", "b.mp3", "c.png", tmp_path=tmp_path)
    compression_page._start_compression()

    assert mock_compression_worker.call_count == 1
    assert len(compression_page._queue) == 2
    assert compression_page._batch_total == 3
    assert compression_page._pending == 3


def test_completing_one_advances_queue(
    compression_page: CompressionPage,
    tmp_path: Path,
    mock_compression_worker: MagicMock,
) -> None:
    """Simulating _complete_one must dequeue the next file and start a new worker."""
    _add_files(compression_page, "a.mp4", "b.mp3", tmp_path=tmp_path)
    out_a = tmp_path / "a_compressed.mp4"
    out_a.touch()

    compression_page._start_compression()
    assert mock_compression_worker.call_count == 1

    # Simulate the first worker finishing
    with patch("file_alchemy.ui.pages.compression_page.InfoBar"):
        compression_page._on_finished(out_a, 1000, 800)

    # A second worker should now have been created for b.mp3
    assert mock_compression_worker.call_count == 2
    assert compression_page._pending == 1


def test_queue_exhausted_resets_ui(
    compression_page: CompressionPage,
    tmp_path: Path,
    mock_compression_worker: MagicMock,
) -> None:
    """After all files finish the progress bar hides and the button re-enables."""
    _add_files(compression_page, "a.mp4", "b.mp3", tmp_path=tmp_path)
    out_a = tmp_path / "a_compressed.mp4"
    out_b = tmp_path / "b_compressed.mp3"
    out_a.touch()
    out_b.touch()

    compression_page._start_compression()

    with patch("file_alchemy.ui.pages.compression_page.InfoBar"):
        compression_page._on_finished(out_a, 500, 400)  # file 1 done
        compression_page._on_finished(out_b, 300, 250)  # file 2 done

    assert not compression_page._progress_bar.isVisible()
    assert compression_page._compress_btn.isEnabled()
    assert compression_page._results_panel.count == 2


def test_error_in_queue_advances_to_next_file(
    compression_page: CompressionPage,
    tmp_path: Path,
    mock_compression_worker: MagicMock,
) -> None:
    """An error on the first file must not block the remaining queue."""
    _add_files(compression_page, "a.mp4", "b.mp3", tmp_path=tmp_path)
    compression_page._start_compression()

    with patch("file_alchemy.ui.pages.base_page.InfoBar"):
        compression_page._on_error("FFmpeg died")

    # Worker 2 is created for b.mp3 despite the first error
    assert mock_compression_worker.call_count == 2
    assert compression_page._results_panel.count == 1  # error entry


def test_three_file_batch_all_errors_resets_ui(
    compression_page: CompressionPage,
    tmp_path: Path,
    mock_compression_worker: MagicMock,
) -> None:
    """Even if every file errors, the UI must reset cleanly after the last one."""
    _add_files(compression_page, "a.mp4", "b.mp3", "c.png", tmp_path=tmp_path)
    compression_page._start_compression()

    with patch("file_alchemy.ui.pages.base_page.InfoBar"):
        compression_page._on_error("error 1")
        compression_page._on_error("error 2")
        compression_page._on_error("error 3")

    assert not compression_page._progress_bar.isVisible()
    assert compression_page._compress_btn.isEnabled()
    assert compression_page._results_panel.count == 3


def test_mixed_success_and_error_batch(
    compression_page: CompressionPage,
    tmp_path: Path,
    mock_compression_worker: MagicMock,
) -> None:
    """A batch with some successes and some errors must populate results for both."""
    _add_files(compression_page, "good.mp4", "bad.mp3", tmp_path=tmp_path)
    out = tmp_path / "good_compressed.mp4"
    out.touch()

    compression_page._start_compression()

    with patch("file_alchemy.ui.pages.compression_page.InfoBar"):
        compression_page._on_finished(out, 1000, 800)

    with patch("file_alchemy.ui.pages.base_page.InfoBar"):
        compression_page._on_error("codec not supported")

    assert compression_page._results_panel.count == 2


# --------------------------------------------------------------------------- #
# _on_finished — results panel and InfoBar
# --------------------------------------------------------------------------- #


def test_on_finished_reduction_in_results_panel(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """A successful compression must write the correct metrics to the results list."""
    _add_files(compression_page, "video.mp4", tmp_path=tmp_path)
    out_path = tmp_path / "video_compressed.mp4"
    out_path.touch()

    with patch("file_alchemy.ui.pages.compression_page.InfoBar") as mock_bar:
        compression_page._pending = 1
        # 10 MB → 5 MB (50% reduction)
        compression_page._on_finished(out_path, 10 * 1024 * 1024, 5 * 1024 * 1024)

    mock_bar.success.assert_called_once()
    assert compression_page._results_panel.count == 1
    text = _get_result_text(compression_page)
    assert "video_compressed.mp4" in text
    assert "10.0 MB" in text
    assert "5.0 MB" in text
    assert "50.0%" in text
    assert "↓" in text


def test_on_finished_size_increase_in_results_panel(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """When output is larger than input, a warning entry must be added."""
    _add_files(compression_page, "audio.flac", tmp_path=tmp_path)
    out_path = tmp_path / "audio_compressed.flac"
    out_path.touch()

    with patch("file_alchemy.ui.pages.compression_page.InfoBar") as mock_bar:
        compression_page._pending = 1
        # 10 MB → 15 MB (50% increase)
        compression_page._on_finished(out_path, 10 * 1024 * 1024, 15 * 1024 * 1024)

    mock_bar.warning.assert_called_once()
    text = _get_result_text(compression_page)
    assert "50.0%" in text
    assert "↑" in text
    assert "larger" in text


def test_on_finished_zero_byte_original_no_crash(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """Zero-byte original must not cause ZeroDivisionError; reports 0% change."""
    out_path = tmp_path / "out.png"
    out_path.touch()

    with patch("file_alchemy.ui.pages.compression_page.InfoBar") as mock_bar:
        compression_page._pending = 1
        compression_page._on_finished(out_path, 0, 0)

    # 0% change → not a size increase → success bar
    mock_bar.success.assert_called_once()


def test_on_finished_exact_same_size(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """When original == final, percentage is 0% and should show as success."""
    out_path = tmp_path / "out.mp3"
    out_path.touch()

    with patch("file_alchemy.ui.pages.compression_page.InfoBar") as mock_bar:
        compression_page._pending = 1
        compression_page._on_finished(out_path, 5000, 5000)

    mock_bar.success.assert_called_once()
    text = _get_result_text(compression_page)
    assert "0.0%" in text
    assert "↓" in text


def test_on_finished_infobar_is_closable(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    """InfoBar notifications must always be closable by the user."""
    out_path = tmp_path / "out.mp4"
    out_path.touch()

    with patch("file_alchemy.ui.pages.compression_page.InfoBar") as mock_bar:
        compression_page._pending = 1
        compression_page._on_finished(out_path, 1000, 800)

    _, kwargs = mock_bar.success.call_args
    assert kwargs.get("isClosable") is True


# --------------------------------------------------------------------------- #
# _on_error — page-specific title
# --------------------------------------------------------------------------- #


def test_on_error_uses_compression_failed_title(
    compression_page: CompressionPage,
) -> None:
    """The InfoBar title must identify 'Compression failed', not the base generic."""
    with patch("file_alchemy.ui.pages.base_page.InfoBar") as mock_bar:
        compression_page._pending = 1
        compression_page._on_error("codec error")

    _, kwargs = mock_bar.error.call_args
    assert kwargs["title"] == "Compression failed"


# --------------------------------------------------------------------------- #
# Reset after batch
# --------------------------------------------------------------------------- #


def test_reset_after_batch_restores_button_and_hides_bar(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    _add_files(compression_page, "video.mp4", tmp_path=tmp_path)
    compression_page._compress_btn.setEnabled(False)
    compression_page._progress_bar.setVisible(True)

    compression_page._reset_after_batch()

    assert compression_page._compress_btn.isEnabled()
    assert not compression_page._progress_bar.isVisible()
    assert compression_page._progress_bar.value() == 0


def test_reset_after_batch_with_empty_list_leaves_button_disabled(
    compression_page: CompressionPage,
) -> None:
    """If the list was cleared mid-run, the button must remain disabled after reset."""
    compression_page._file_panel.clear()  # no files
    compression_page._reset_after_batch()
    assert not compression_page._compress_btn.isEnabled()


# --------------------------------------------------------------------------- #
# Estimated size label
# --------------------------------------------------------------------------- #


def test_estimated_size_lossless(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    f = tmp_path / "video.mp4"
    f.write_text("x" * 1000)
    compression_page._on_files_added([f])

    compression_page._radio_lossless.setChecked(True)
    assert "1000 B" in compression_page._estimate_label.text()


def test_estimated_size_target_shows_exact_value(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    f = tmp_path / "video.mp4"
    f.write_text("x" * 1000)
    compression_page._on_files_added([f])

    compression_page._radio_target.setChecked(True)
    compression_page._target_spinbox.setValue(4)
    compression_page._target_unit.setCurrentIndex(0)  # KB
    label = compression_page._estimate_label.text()
    assert "4.0 KB" in label
    assert "≈" not in label  # Target is exact, not approximate


def test_estimated_size_empty_panel_shows_placeholder(
    compression_page: CompressionPage,
) -> None:
    assert "Est. output: ≈ --" in compression_page._estimate_label.text()


def test_estimated_size_lossy_has_approximation_prefix(
    compression_page: CompressionPage, tmp_path: Path
) -> None:
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"x" * 5000)
    compression_page._on_files_added([f])

    compression_page._radio_lossy.setChecked(True)
    assert "≈" in compression_page._estimate_label.text()
