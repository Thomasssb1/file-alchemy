"""Tests for BaseBatchPage shared behaviour using a minimal concrete stub."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QLabel, QVBoxLayout
from pytestqt.qtbot import QtBot
from qfluentwidgets import ProgressBar

from file_alchemy.ui.components import FileListPanel, ResultsPanel
from file_alchemy.ui.pages.base_page import BaseBatchPage

# --------------------------------------------------------------------------- #
# Stub concrete implementation
# --------------------------------------------------------------------------- #


class _StubBatchPage(BaseBatchPage):
    """Minimal concrete subclass that satisfies the abstract contract.

    ``_run_next_in_queue`` tracks how many times it has been called so
    tests can assert queue-advancement behaviour without real workers.
    ``_restore_action_button`` sets a flag so tests can verify it is
    called by ``_reset_after_batch``.
    """

    _error_title = "Stub error"

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        self._output_dir_label = QLabel("Output: same folder as input")
        layout.addWidget(self._output_dir_label)

        self._progress_bar = ProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._file_panel = FileListPanel()
        layout.addWidget(self._file_panel)

        self._results_panel = ResultsPanel()
        layout.addWidget(self._results_panel)

        self.run_next_count: int = 0
        self.restore_count: int = 0

    def _run_next_in_queue(self) -> None:
        self.run_next_count += 1
        if self._queue:
            self._queue.popleft()

    def _restore_action_button(self) -> None:
        self.restore_count += 1


# --------------------------------------------------------------------------- #
# Fixture
# --------------------------------------------------------------------------- #


@pytest.fixture()
def stub(qtbot: QtBot) -> _StubBatchPage:
    """Create a _StubBatchPage registered with qtbot for cleanup."""
    p = _StubBatchPage()
    qtbot.addWidget(p)
    p.show()
    return p


# --------------------------------------------------------------------------- #
# _pick_output_dir
# --------------------------------------------------------------------------- #


def test_pick_output_dir_accepts_directory(
    stub: _StubBatchPage, tmp_path: Path
) -> None:
    with patch(
        "file_alchemy.ui.pages.base_page.QFileDialog.getExistingDirectory",
        return_value=str(tmp_path),
    ):
        stub._pick_output_dir()

    assert stub._output_dir == tmp_path
    assert str(tmp_path) in stub._output_dir_label.text()


def test_pick_output_dir_cancel_leaves_none(stub: _StubBatchPage) -> None:
    with patch(
        "file_alchemy.ui.pages.base_page.QFileDialog.getExistingDirectory",
        return_value="",
    ):
        stub._pick_output_dir()

    assert stub._output_dir is None


def test_pick_output_dir_successive_calls_update_state(
    stub: _StubBatchPage, tmp_path: Path
) -> None:
    """Each accepted directory replaces the previous one."""
    first = tmp_path / "first"
    first.mkdir()
    second = tmp_path / "second"
    second.mkdir()

    with patch(
        "file_alchemy.ui.pages.base_page.QFileDialog.getExistingDirectory",
        return_value=str(first),
    ):
        stub._pick_output_dir()
    assert stub._output_dir == first

    with patch(
        "file_alchemy.ui.pages.base_page.QFileDialog.getExistingDirectory",
        return_value=str(second),
    ):
        stub._pick_output_dir()
    assert stub._output_dir == second
    assert str(second) in stub._output_dir_label.text()


# --------------------------------------------------------------------------- #
# _on_progress
# --------------------------------------------------------------------------- #


def test_on_progress_aggregates_total_batch(stub: _StubBatchPage) -> None:
    """Progress across a 2-file batch is correctly weighted."""
    stub._batch_total = 2

    stub._pending = 2  # 0 completed, file 1 at 50%
    stub._on_progress(50.0)
    assert stub._progress_bar.value() == 25  # (0*100 + 50) / 2

    stub._pending = 1  # 1 completed, file 2 at 50%
    stub._on_progress(50.0)
    assert stub._progress_bar.value() == 75  # (1*100 + 50) / 2

    stub._on_progress(100.0)
    assert stub._progress_bar.value() == 100  # (1*100 + 100) / 2


def test_on_progress_clamps_to_100(stub: _StubBatchPage) -> None:
    """Values above 100 from an engine must be clamped."""
    stub._batch_total = 1
    stub._pending = 1
    stub._on_progress(150.0)
    assert stub._progress_bar.value() == 100


def test_on_progress_noop_when_batch_total_zero(stub: _StubBatchPage) -> None:
    """_on_progress must not divide by zero when no batch is running."""
    stub._batch_total = 0
    stub._on_progress(50.0)
    assert stub._progress_bar.value() == 0


# --------------------------------------------------------------------------- #
# _on_error
# --------------------------------------------------------------------------- #


def test_on_error_adds_entry_to_results_panel(stub: _StubBatchPage) -> None:
    with patch("file_alchemy.ui.pages.base_page.InfoBar"):
        stub._pending = 1
        stub._on_error("something went wrong")

    assert stub._results_panel.count == 1


def test_on_error_shows_infobar_with_error_level(stub: _StubBatchPage) -> None:
    with patch("file_alchemy.ui.pages.base_page.InfoBar") as mock_bar:
        stub._pending = 1
        stub._on_error("something went wrong")

    mock_bar.error.assert_called_once()


def test_on_error_infobar_uses_subclass_title(stub: _StubBatchPage) -> None:
    with patch("file_alchemy.ui.pages.base_page.InfoBar") as mock_bar:
        stub._pending = 1
        stub._on_error("failure message")

    _, kwargs = mock_bar.error.call_args
    assert kwargs["title"] == "Stub error"


def test_on_error_infobar_is_closable(stub: _StubBatchPage) -> None:
    with patch("file_alchemy.ui.pages.base_page.InfoBar") as mock_bar:
        stub._pending = 1
        stub._on_error("failure")

    _, kwargs = mock_bar.error.call_args
    assert kwargs.get("isClosable") is True


def test_on_error_calls_complete_one(stub: _StubBatchPage) -> None:
    """After an error on the last item, _reset_after_batch should run."""
    stub._batch_total = 1
    stub._pending = 1

    with patch("file_alchemy.ui.pages.base_page.InfoBar"):
        stub._on_error("failure")

    assert stub.restore_count == 1  # _reset_after_batch → _restore_action_button


# --------------------------------------------------------------------------- #
# _complete_one
# --------------------------------------------------------------------------- #


def test_complete_one_decrements_pending(stub: _StubBatchPage) -> None:
    stub._queue.append(object())
    stub._batch_total = 2
    stub._pending = 2

    stub._complete_one()

    assert stub._pending == 1


def test_complete_one_advances_queue_when_items_remain(stub: _StubBatchPage) -> None:
    stub._queue.extend([object(), object()])
    stub._batch_total = 2
    stub._pending = 2

    stub._complete_one()

    assert stub.run_next_count == 1


def test_complete_one_resets_when_last_item(stub: _StubBatchPage) -> None:
    """On the last item, _reset_after_batch (and therefore _restore_action_button) runs."""
    stub._batch_total = 1
    stub._pending = 1

    stub._complete_one()

    assert stub._pending == 0
    assert stub.restore_count == 1
    assert not stub._progress_bar.isVisible()


def test_complete_one_clears_current_worker(stub: _StubBatchPage) -> None:
    mock_worker = MagicMock()
    stub._current_worker = mock_worker
    stub._batch_total = 1
    stub._pending = 1

    stub._complete_one()

    mock_worker.deleteLater.assert_called_once()
    assert stub._current_worker is None


# --------------------------------------------------------------------------- #
# _reset_after_batch
# --------------------------------------------------------------------------- #


def test_reset_after_batch_hides_progress_bar(stub: _StubBatchPage) -> None:
    stub._progress_bar.setVisible(True)
    stub._progress_bar.setValue(60)

    stub._reset_after_batch()

    assert not stub._progress_bar.isVisible()
    assert stub._progress_bar.value() == 0


def test_reset_after_batch_calls_restore_action_button(stub: _StubBatchPage) -> None:
    stub._reset_after_batch()
    assert stub.restore_count == 1
