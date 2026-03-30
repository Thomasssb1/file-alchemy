"""Reusable results panel showing completion items."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, IconWidget, StrongBodyLabel


class ResultItemWidget(QWidget):
    """Custom widget for list items allowing border styling and Fluent icons."""

    def __init__(
        self, icon: FluentIcon, text: str, border_color: str = "transparent"
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.icon_widget = IconWidget(icon)
        self.icon_widget.setFixedSize(16, 16)
        layout.addWidget(self.icon_widget)

        self.label = QLabel(text)
        self.label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.label)
        layout.addStretch()

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"ResultItemWidget {{ border: 1px solid {border_color}; border-radius: 4px; background: transparent; }}"
        )


class ResultsPanel(QWidget):
    """Displays a list of completed operations (success or failure).

    Items can be double-clicked to open their containing folder.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._label = StrongBodyLabel("Results")
        layout.addWidget(self._label)

        self._list_widget = QListWidget()
        self._list_widget.setMaximumHeight(150)
        # Ensure our custom widgets layout nicely inside list items
        self._list_widget.setSpacing(2)
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list_widget)

    def _add_item(
        self, widget: ResultItemWidget, folder_path: str | Path | None = None
    ) -> None:
        item = QListWidgetItem()
        # Set size hint slightly taller to accommodate the widget borders/margins safely
        item.setSizeHint(widget.sizeHint())
        if folder_path:
            item.setData(Qt.ItemDataRole.UserRole, str(folder_path))
        self._list_widget.addItem(item)
        self._list_widget.setItemWidget(item, widget)

    def add_success(self, message: str, folder_path: str | Path | None = None) -> None:
        """Add a success record, optionally with a clickable folder path."""
        widget = ResultItemWidget(FluentIcon.COMPLETED, message)
        self._add_item(widget, folder_path)

    def add_warning(self, message: str, folder_path: str | Path | None = None) -> None:
        """Add a warning record, optionally with a clickable folder path."""
        # Use an orange border on warning
        widget = ResultItemWidget(FluentIcon.INFO, message, border_color="#f59e0b")
        self._add_item(widget, folder_path)

    def add_error(self, message: str) -> None:
        """Add an error record."""
        # Use a red border on error
        widget = ResultItemWidget(
            FluentIcon.CLOSE, f"Failed: {message}", border_color="#ef4444"
        )
        self._add_item(widget)

    def clear(self) -> None:
        """Clear all results."""
        self._list_widget.clear()

    @property
    def count(self) -> int:
        """Return the number of items in the results list."""
        return self._list_widget.count()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        folder_path = item.data(Qt.ItemDataRole.UserRole)
        if not folder_path:
            return

        if platform.system() == "Windows":
            subprocess.Popen(["explorer", folder_path])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
