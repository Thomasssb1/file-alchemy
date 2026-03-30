"""Drag-and-drop file zone — shared between Media and Compression pages."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import PushButton


class DropZone(QFrame):
    """Drag-and-drop target that also shows a file-open button."""

    def __init__(
        self,
        files_callback: Callable[[list[Path]], None],
        parent: QWidget | None = None,
        text: str = "Drop files here",
        icon: str = "📂",
    ) -> None:
        super().__init__(parent)
        self._files_callback = files_callback

        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.setObjectName("dropZone")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            """
            #dropZone {
              border: 2px dotted #6366f1;
              border-radius: 8px;
              background: rgba(99, 102, 241, 0.09);
            }
            #dropZone:hover {
              border-color: #818cf8;
              background: rgba(99, 102, 241, 0.16);
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 32px;")
        layout.addWidget(icon_label)

        hint = QLabel(text)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #999; font-size: 13px;")
        layout.addWidget(hint)

        self._browse_btn = PushButton("Browse…")
        self._browse_btn.setFixedWidth(110)
        layout.addWidget(self._browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._browse_btn.clicked.connect(self._open_file_dialog)

    def _open_file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files")
        if paths:
            self._files_callback([Path(p) for p in paths])

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        paths = [Path(u.toLocalFile()) for u in urls if u.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self._files_callback(paths)
        else:
            event.ignore()
