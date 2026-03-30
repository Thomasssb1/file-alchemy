"""Tests for reusable UI components."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QMimeData, QUrl, Qt
from pytestqt.qtbot import QtBot

from file_alchemy.ui.components import DropZone, FileListPanel, ResultsPanel


def test_results_panel_add_success(results_panel: ResultsPanel) -> None:
    results_panel.add_success("Converted A", folder_path="/fake/dir")
    assert results_panel.count == 1

    item = results_panel._list_widget.item(0)
    widget = results_panel._list_widget.itemWidget(item)

    assert "Converted A" in widget.label.text()

    # Check folder path mapping
    assert item.data(Qt.ItemDataRole.UserRole) == "/fake/dir"

    # Success borders should be transparent
    assert "transparent" in widget.styleSheet()


def test_results_panel_add_warning(results_panel: ResultsPanel) -> None:
    results_panel.add_warning("Inflation on B", folder_path="/fake/dir2")
    assert results_panel.count == 1

    item = results_panel._list_widget.item(0)
    widget = results_panel._list_widget.itemWidget(item)

    assert "Inflation on B" in widget.label.text()

    # Warn borders should be orange
    assert "#f59e0b" in widget.styleSheet()


def test_results_panel_add_error(results_panel: ResultsPanel) -> None:
    results_panel.add_error("File corrupted")
    assert results_panel.count == 1

    item = results_panel._list_widget.item(0)
    widget = results_panel._list_widget.itemWidget(item)

    assert "File corrupted" in widget.label.text()

    # Error borders should be red
    assert "#ef4444" in widget.styleSheet()


def test_results_panel_clear(results_panel: ResultsPanel) -> None:
    results_panel.add_success("1")
    results_panel.add_error("2")
    assert results_panel.count == 2

    results_panel.clear()
    assert results_panel.count == 0


@patch("platform.system", return_value="Windows")
@patch("subprocess.Popen")
def test_results_panel_double_click_windows(
    mock_popen: MagicMock, _: MagicMock, results_panel: ResultsPanel
) -> None:
    results_panel.add_success("1", folder_path="C:/foo")
    item = results_panel._list_widget.item(0)

    results_panel._on_item_double_clicked(item)

    mock_popen.assert_called_once_with(["explorer", "C:/foo"])


@patch("file_alchemy.ui.components.drop_zone.QFileDialog.getOpenFileNames")
def test_drop_zone_browse_files_button(
    mock_get_names: MagicMock, drop_zone: DropZone, tmp_path: Path
) -> None:
    fake_file = tmp_path / "valid.mp4"
    mock_get_names.return_value = ([str(fake_file)], "")
    
    # Simulate clicking the manual browse button
    drop_zone._browse_btn.clicked.emit()
    
    # Must correctly process and invoke callback via picker dialog
    drop_zone._mock_cb.assert_called_once()
    assert drop_zone._mock_cb.call_args[0][0][0].name == "valid.mp4"


def test_drop_zone_drag_enter(drop_zone: DropZone) -> None:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("/some/file.mp4")])

    mock_event = MagicMock()
    mock_event.mimeData.return_value = mime

    drop_zone.dragEnterEvent(mock_event)
    mock_event.acceptProposedAction.assert_called_once()


def test_drop_zone_drop_event(drop_zone: DropZone, tmp_path: Path) -> None:
    fake_file = tmp_path / "video.mp4"
    fake_file.touch()

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(fake_file))])

    mock_event = MagicMock()
    mock_event.mimeData.return_value = mime

    drop_zone.dropEvent(mock_event)

    # Callback should be executed with the dropped valid path
    drop_zone._mock_cb.assert_called_once_with([fake_file])


def test_results_panel_selection_highlights_correctly(results_panel: ResultsPanel) -> None:
    results_panel.add_success("Item 1")
    results_panel.add_warning("Item 2")
    results_panel.add_error("Item 3")
    assert results_panel.count == 3
    
    list_widget = results_panel._list_widget
    
    # Select the second item specifically (warning item)
    list_widget.setCurrentRow(1)
    
    # Assert selection evaluates effectively in memory
    assert list_widget.currentRow() == 1
    selected_items = list_widget.selectedItems()
    assert len(selected_items) == 1
    
    # Fetch nested itemWidget value to ensure proper evaluation of highlight
    widget = list_widget.itemWidget(selected_items[0])
    assert "Item 2" in widget.label.text()


def test_file_list_panel_selection_changed(file_list_panel: FileListPanel, qtbot: QtBot) -> None:
    # Adding items manually
    file1 = Path("/fake/file1.mp4")
    file2 = Path("/fake/file2.mp3")
    
    with qtbot.waitSignal(file_list_panel.filesAdded):
        file_list_panel.add_files([file1, file2])
    
    assert file_list_panel.count == 2
    
    # Initially the first item should be selected
    assert file_list_panel.current_row == 0
    assert file_list_panel.files[file_list_panel.current_row] == file1
    
    # Alter the selection explicitly to verify component event bridging
    with qtbot.waitSignal(file_list_panel.selectionChanged) as blocker:
        file_list_panel._list_widget.setCurrentRow(1)
        
    assert blocker.args[0] == 1
    assert file_list_panel.current_row == 1
    assert file_list_panel.files[file_list_panel.current_row] == file2
