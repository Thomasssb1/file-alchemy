"""Component tests for the MediaPage UI.

Uses pytest-qt's ``qtbot`` fixture which manages QApplication lifecycle and
provides helpers for widget interaction and signal recording.

These tests exercise the widget's logic (grouped format combo, button state,
header-guard in _start_conversion) without launching a real window or
running FFmpeg.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent
from pytestqt.qtbot import QtBot

from file_alchemy.ui.pages.media.media_page import MediaPage

# --------------------------------------------------------------------------- #
# Helpers & Fixtures
# --------------------------------------------------------------------------- #


def _add_files(page: MediaPage, *names: str, tmp_path: Path) -> list[Path]:
    """Touch fake files in *tmp_path* and add them to *page*."""
    paths = [tmp_path / name for name in names]
    for p in paths:
        p.touch()
    page._on_files_added(paths)
    return paths


def _make_drop_event(urls: list[QUrl]) -> QDropEvent:
    """Build a synthetic QDropEvent carrying the given URLs.

    The QMimeData is stored as ``event._mime`` so Python's refcount keeps it
    alive for the entire duration of the ``dropEvent`` call - without this,
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


@pytest.fixture()
def page(qtbot: QtBot) -> MediaPage:
    """Create a MediaPage and register it with qtbot for cleanup."""
    p = MediaPage()
    qtbot.addWidget(p)
    return p


@pytest.fixture()
def mock_conversion_worker():
    """Patch ConversionWorker so _start_conversion never spawns a thread."""
    with patch("file_alchemy.ui.pages.media.media_page.ConversionWorker") as cls:
        mock_w = MagicMock()
        mock_w.progress = MagicMock()
        mock_w.finished = MagicMock()
        mock_w.error = MagicMock()
        cls.return_value = mock_w
        yield cls


# --------------------------------------------------------------------------- #
# Initial state
# --------------------------------------------------------------------------- #


def test_convert_button_disabled_initially(page: MediaPage) -> None:
    assert not page._convert_btn.isEnabled()


def test_format_combo_empty_initially(page: MediaPage) -> None:
    assert page._format_combo.count() == 0


def test_file_list_empty_initially(page: MediaPage) -> None:
    assert page._file_panel._list_widget.count() == 0


def test_pending_initialised_to_zero(page: MediaPage) -> None:
    assert page._pending == 0


# --------------------------------------------------------------------------- #
# File loading
# --------------------------------------------------------------------------- #


def test_adding_file_populates_file_list(page: MediaPage, tmp_path: Path) -> None:
    _add_files(page, "clip.mp4", tmp_path=tmp_path)
    assert page._file_panel._list_widget.count() == 1
    assert page._file_panel._list_widget.item(0).text() == "clip.mp4"
    assert page._convert_btn.isEnabled()


def test_adding_duplicate_files_is_ignored(page: MediaPage, tmp_path: Path) -> None:
    paths = _add_files(page, "clip.mp4", tmp_path=tmp_path)
    page._on_files_added(paths)
    assert page._file_panel._list_widget.count() == 1


def test_clear_resets_page(page: MediaPage, tmp_path: Path) -> None:
    _add_files(page, "clip.mp4", tmp_path=tmp_path)
    page._file_panel.clear()
    assert page._file_panel._list_widget.count() == 0
    assert page._format_combo.count() == 0
    assert not page._convert_btn.isEnabled()


def test_multiple_files_all_appear_in_list(page: MediaPage, tmp_path: Path) -> None:
    _add_files(page, "clip1.mp4", "clip2.mkv", "track.mp3", tmp_path=tmp_path)
    assert len(page._file_panel.files) == 3
    assert page._file_panel._list_widget.count() == 3


def test_adding_files_keeps_existing_selection(page: MediaPage, tmp_path: Path) -> None:
    """Adding a second batch must not reset the row selection to 0."""
    _add_files(page, "clip.mp4", "track.mp3", tmp_path=tmp_path)
    page._file_panel._list_widget.setCurrentRow(1)

    extra = tmp_path / "extra.wav"
    extra.touch()
    page._on_files_added([extra])

    assert page._file_panel._list_widget.currentRow() == 1


# --------------------------------------------------------------------------- #
# Grouped format ComboBox
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "filename, expected_category",
    [
        ("clip.mp4", "Video"),
        ("track.mp3", "Audio"),
        ("photo.png", "Image"),
    ],
)
def test_first_header_matches_input_category(
    page: MediaPage, tmp_path: Path, filename: str, expected_category: str
) -> None:
    """The first combo item must be a disabled header matching the file's category."""
    _add_files(page, filename, tmp_path=tmp_path)

    first = page._format_combo.model().item(0)
    assert first is not None
    assert not first.isEnabled()
    assert expected_category in first.text()


def test_video_file_shows_cross_format_section(page: MediaPage, tmp_path: Path) -> None:
    _add_files(page, "clip.mp4", tmp_path=tmp_path)

    model = page._format_combo.model()
    cross_headers = [
        model.item(i).text()
        for i in range(page._format_combo.count())
        if not model.item(i).isEnabled() and "cross" in model.item(i).text().lower()
    ]
    assert cross_headers, (
        "Expected at least one '(cross-format)' header for video input"
    )


def test_all_header_items_are_disabled(page: MediaPage, tmp_path: Path) -> None:
    """Every disabled item must be a category header (contain '──')."""
    _add_files(page, "clip.mp4", tmp_path=tmp_path)

    model = page._format_combo.model()
    for i in range(page._format_combo.count()):
        item = model.item(i)
        if not item.isEnabled():
            assert "──" in item.text(), (
                f"Disabled item at index {i} looks wrong: {item.text()!r}"
            )


def test_initial_selection_is_enabled_item(page: MediaPage, tmp_path: Path) -> None:
    _add_files(page, "clip.mp4", tmp_path=tmp_path)

    idx = page._format_combo.currentIndex()
    item = page._format_combo.model().item(idx)
    assert item.isEnabled(), (
        f"Initial selection landed on a disabled header at index {idx}: {item.text()!r}"
    )


def test_convert_button_disabled_for_unknown_extension(
    page: MediaPage, tmp_path: Path
) -> None:
    _add_files(page, "data.xyz123", tmp_path=tmp_path)
    assert not page._convert_btn.isEnabled()


def test_selecting_each_row_updates_format_combo(
    page: MediaPage, tmp_path: Path
) -> None:
    """Switching row between a video and audio file must repopulate the combo."""
    _add_files(page, "clip.mp4", "track.mp3", tmp_path=tmp_path)

    page._file_panel._list_widget.setCurrentRow(0)
    mp4_headers = [
        page._format_combo.model().item(i).text()
        for i in range(page._format_combo.count())
        if not page._format_combo.model().item(i).isEnabled()
    ]

    page._file_panel._list_widget.setCurrentRow(1)
    mp3_headers = [
        page._format_combo.model().item(i).text()
        for i in range(page._format_combo.count())
        if not page._format_combo.model().item(i).isEnabled()
    ]

    assert any("Video" in h for h in mp4_headers)
    assert any("Audio" in h for h in mp3_headers)
    assert mp4_headers != mp3_headers


# --------------------------------------------------------------------------- #
# Format selection - same category vs cross-category
# --------------------------------------------------------------------------- #


def test_same_category_format_selectable(page: MediaPage, tmp_path: Path) -> None:
    """A same-category video output (mkv) must be selectable."""
    _add_files(page, "clip.mp4", tmp_path=tmp_path)
    for i in range(page._format_combo.count()):
        if page._format_combo.itemText(i) == "mkv":
            page._format_combo.setCurrentIndex(i)
            break
    assert page._format_combo.currentText() == "mkv"


def test_cross_category_format_selectable(page: MediaPage, tmp_path: Path) -> None:
    """A cross-category audio output (mp3) must be selectable."""
    _add_files(page, "clip.mp4", tmp_path=tmp_path)
    for i in range(page._format_combo.count()):
        if page._format_combo.itemText(i) == "mp3":
            page._format_combo.setCurrentIndex(i)
            break
    assert page._format_combo.currentText() == "mp3"


def test_same_category_format_not_in_cross_section(
    page: MediaPage, tmp_path: Path
) -> None:
    """'mkv' (same Video category as mp4) must not appear under a cross-format header."""
    _add_files(page, "clip.mp4", tmp_path=tmp_path)

    model = page._format_combo.model()
    in_cross_section = False
    for i in range(page._format_combo.count()):
        item = model.item(i)
        text = item.text()
        if not item.isEnabled():
            in_cross_section = "cross" in text.lower()
            continue
        if text == "mkv" and in_cross_section:
            pytest.fail("'mkv' should not appear under a cross-format header")


# --------------------------------------------------------------------------- #
# _start_conversion guards
# --------------------------------------------------------------------------- #


def test_start_conversion_skips_header_text(page: MediaPage, tmp_path: Path) -> None:
    """_start_conversion must bail out when the combo shows a header."""
    _add_files(page, "clip.mp4", tmp_path=tmp_path)
    page._format_combo.setCurrentIndex(0)
    assert not page._format_combo.model().item(0).isEnabled()

    page._start_conversion()
    assert getattr(page, "_current_worker", None) is None
    assert not page._queue


def test_start_conversion_skips_when_no_files(page: MediaPage) -> None:
    page._start_conversion()
    assert getattr(page, "_current_worker", None) is None
    assert not page._queue


# --------------------------------------------------------------------------- #
# Batch conversion
# --------------------------------------------------------------------------- #


def test_all_files_queued_when_converting(
    page: MediaPage, tmp_path: Path, mock_conversion_worker: MagicMock
) -> None:
    """All loaded files produce a worker, regardless of which row is selected."""
    _add_files(page, "a.mp4", "b.mp4", "c.mp4", tmp_path=tmp_path)
    page._file_panel._list_widget.setCurrentRow(1)
    page._select_first_enabled()

    page._start_conversion()
    assert mock_conversion_worker.call_count == 1
    assert len(page._queue) == 2


def test_progress_bar_shown_when_conversion_starts(
    qtbot: QtBot, tmp_path: Path, mock_conversion_worker: MagicMock
) -> None:
    page = MediaPage()
    qtbot.addWidget(page)
    page.show()
    _add_files(page, "clip.mp4", tmp_path=tmp_path)
    page._select_first_enabled()

    page._start_conversion()
    assert page._progress_bar.isVisible()


# --------------------------------------------------------------------------- #
# Upload methods
# --------------------------------------------------------------------------- #


def test_browse_button_adds_files(page: MediaPage, tmp_path: Path) -> None:
    fake = tmp_path / "song.mp3"
    fake.touch()

    with patch(
        "file_alchemy.ui.components.drop_zone.QFileDialog.getOpenFileNames",
        return_value=([str(fake)], ""),
    ):
        page._drop_zone._open_file_dialog()

    assert page._file_panel._list_widget.count() == 1
    assert page._file_panel.files[0].name == "song.mp3"


def test_browse_button_cancel_adds_nothing(page: MediaPage) -> None:
    with patch(
        "file_alchemy.ui.components.drop_zone.QFileDialog.getOpenFileNames",
        return_value=([], ""),
    ):
        page._drop_zone._open_file_dialog()

    assert page._file_panel._list_widget.count() == 0


def test_drop_zone_callback_wiring(page: MediaPage, tmp_path: Path) -> None:
    """The drop zone's _files_callback must be wired to _on_files_added."""
    fake = tmp_path / "video.mp4"
    fake.touch()
    page._drop_zone._files_callback([fake])
    assert page._file_panel._list_widget.count() == 1


def test_drag_drop_adds_files(qtbot: QtBot, tmp_path: Path) -> None:
    page = MediaPage()
    qtbot.addWidget(page)
    page.show()

    fake = tmp_path / "dropped.mp4"
    fake.touch()
    event = _make_drop_event([QUrl.fromLocalFile(str(fake))])
    page._drop_zone.dropEvent(event)

    assert page._file_panel._list_widget.count() == 1
    assert page._file_panel.files[0].name == "dropped.mp4"


def test_drag_drop_ignores_non_file_urls(qtbot: QtBot) -> None:
    page = MediaPage()
    qtbot.addWidget(page)
    page.show()

    event = _make_drop_event([QUrl("https://example.com/video.mp4")])
    page._drop_zone.dropEvent(event)
    assert page._file_panel._list_widget.count() == 0


# --------------------------------------------------------------------------- #
# Output directory
# --------------------------------------------------------------------------- #


def test_default_output_dir_is_none(page: MediaPage) -> None:
    assert page._output_dir is None


def test_resolve_output_path_uses_output_dir(page: MediaPage, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    page._output_dir = out_dir

    result = page._resolve_output_path(Path("/some/input/video.mp4"), "mkv")
    assert result == out_dir / "video.mkv"


def test_resolve_output_path_falls_back_to_input_dir(
    page: MediaPage, tmp_path: Path
) -> None:
    input_file = tmp_path / "track.mp3"
    input_file.touch()

    result = page._resolve_output_path(input_file, "flac")
    assert result.parent == tmp_path
    assert result.name == "track.flac"


# --------------------------------------------------------------------------- #
# Progress bar lifecycle
# --------------------------------------------------------------------------- #


def test_progress_bar_hidden_initially(page: MediaPage) -> None:
    assert not page._progress_bar.isVisible()


def test_progress_bar_hidden_after_successful_conversion(
    page: MediaPage, tmp_path: Path
) -> None:
    _add_files(page, "clip.mp4", tmp_path=tmp_path)
    page._pending = 1
    with patch("file_alchemy.ui.pages.media.media_page.InfoBar"):
        page._on_finished(tmp_path / "out.mp3")

    assert not page._progress_bar.isVisible()
    assert page._convert_btn.isEnabled()


def test_infobar_success_shown_after_conversion(
    page: MediaPage, tmp_path: Path
) -> None:
    page._pending = 1
    with patch("file_alchemy.ui.pages.media.media_page.InfoBar") as mock:
        page._on_finished(tmp_path / "out.mp3")
    mock.success.assert_called_once()


def test_progress_bar_hidden_after_error(page: MediaPage, tmp_path: Path) -> None:
    _add_files(page, "clip.mp4", tmp_path=tmp_path)
    page._pending = 1
    with patch("file_alchemy.ui.pages.media.media_page.InfoBar"):
        page._on_error("FFmpeg conversion failed with code 1")

    assert not page._progress_bar.isVisible()
    assert page._convert_btn.isEnabled()


def test_on_error_uses_conversion_failed_title(page: MediaPage) -> None:
    """The InfoBar title must identify 'Conversion failed', not the base generic."""
    with patch("file_alchemy.ui.pages.base_page.InfoBar") as mock:
        page._pending = 1
        page._on_error("FFmpeg not found on PATH")
    _, kwargs = mock.error.call_args
    assert kwargs["title"] == "Conversion failed"


def test_reset_after_batch_restores_button_and_hides_bar(
    page: MediaPage, tmp_path: Path
) -> None:
    _add_files(page, "clip.mp4", tmp_path=tmp_path)
    page._convert_btn.setEnabled(False)
    page._progress_bar.setVisible(True)

    page._reset_after_batch()

    assert page._convert_btn.isEnabled()
    assert not page._progress_bar.isVisible()
    assert page._progress_bar.value() == 0
