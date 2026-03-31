"""Shared base class for batch-processing pages (compression, media)."""

from __future__ import annotations

from abc import abstractmethod
from collections import deque
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, ProgressBar

from file_alchemy.ui.components import FileListPanel, ResultsPanel


class BaseBatchPage(QWidget):
    """Base for pages that run a worker queue with a shared progress bar.

    Subclasses must:
    - Set ``_error_title`` as a class attribute (shown in the error InfoBar).
    - Call ``super().__init__`` then build their own UI, assigning
      ``self._progress_bar``, ``self._file_panel``, ``self._results_panel``,
      and ``self._output_dir_label`` before anything tries to use them.
    - Implement ``_run_next_in_queue`` to pop from ``self._queue`` and
      start a worker connected to ``_on_progress``, ``_on_finished``,
      and ``_on_error``.
    - Implement ``_restore_action_button`` to re-enable the primary action
      button in a page-appropriate way after a batch completes.
    """

    _error_title: str  # must be defined by each concrete subclass

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_worker: Any = None
        self._queue: deque = deque()
        self._output_dir: Path | None = None
        self._pending: int = 0
        self._batch_total: int = 0

        # Subclasses must create these during their _setup_ui call.
        self._progress_bar: ProgressBar
        self._file_panel: FileListPanel
        self._results_panel: ResultsPanel

    # ------------------------------------------------------------------ #
    # Output directory
    # ------------------------------------------------------------------ #

    def _pick_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if directory:
            self._output_dir = Path(directory)
            self._output_dir_label.setText(f"Output: {self._output_dir}")

    # ------------------------------------------------------------------ #
    # Batch progress
    # ------------------------------------------------------------------ #

    def _on_progress(self, pct: float) -> None:
        if self._batch_total > 0:
            completed = self._batch_total - self._pending
            overall_pct = ((completed * 100) + pct) / self._batch_total
            self._progress_bar.setValue(int(min(100, overall_pct)))

    # ------------------------------------------------------------------ #
    # Error handling
    # ------------------------------------------------------------------ #

    def _on_error(self, message: str) -> None:
        self._results_panel.add_error(message)
        InfoBar.error(
            title=self._error_title,
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=6000,
            parent=self,
        )
        self._complete_one()

    # ------------------------------------------------------------------ #
    # Worker lifecycle
    # ------------------------------------------------------------------ #

    def _complete_one(self) -> None:
        """Decrement the pending counter and run next or reset UI."""
        if self._current_worker:
            self._current_worker.deleteLater()
            self._current_worker = None

        self._pending -= 1
        if self._pending <= 0:
            self._reset_after_batch()
        else:
            self._run_next_in_queue()

    def _reset_after_batch(self) -> None:
        """Hide the progress bar and delegate button restore to the subclass."""
        self._progress_bar.setVisible(False)
        self._progress_bar.setValue(0)
        self._restore_action_button()

    # ------------------------------------------------------------------ #
    # Abstract interface for subclasses
    # ------------------------------------------------------------------ #

    @abstractmethod
    def _run_next_in_queue(self) -> None:
        """Pop the next task from ``self._queue`` and start a worker."""

    @abstractmethod
    def _restore_action_button(self) -> None:
        """Re-enable the primary action button after a batch completes."""
