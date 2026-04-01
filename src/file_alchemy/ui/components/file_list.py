"""Reusable panel for managing drag-and-dropped selected files."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, PushButton, StrongBodyLabel


class FileListPanel(QWidget):
    """Encapsulates the selected file list UI and underlying Path state."""

    selectionChanged = pyqtSignal(int)
    listCleared = pyqtSignal()
    filesAdded = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[Path] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(StrongBodyLabel("Selected files"))

        self._list_widget = QListWidget()
        self._list_widget.setMinimumHeight(150)
        self._list_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._list_widget.currentRowChanged.connect(self.selectionChanged)
        layout.addWidget(self._list_widget)

        self._clear_btn = PushButton(FluentIcon.DELETE, "Clear list")
        self._clear_btn.clicked.connect(self.clear)
        layout.addWidget(self._clear_btn)

    def add_files(self, paths: list[Path]) -> None:
        """Add unique paths to the list. Emits filesAdded if any were new."""
        added = False
        for p in paths:
            if p not in self._items:
                self._items.append(p)
                self._list_widget.addItem(QListWidgetItem(p.name))
                added = True

        if self._items and self._list_widget.currentRow() < 0:
            self._list_widget.setCurrentRow(0)

        if added:
            self.filesAdded.emit()

    def clear(self) -> None:
        """Clear all files from the queue securely."""
        self._items.clear()
        self._list_widget.clear()
        self.listCleared.emit()

    @property
    def files(self) -> list[Path]:
        """Return a copy of the current file paths."""
        return self._items.copy()

    @property
    def count(self) -> int:
        """Number of items currently queued."""
        return len(self._items)

    @property
    def current_row(self) -> int:
        """Index of currently selected list item."""
        return self._list_widget.currentRow()
