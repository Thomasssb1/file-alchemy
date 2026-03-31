"""Main application window - FluentWindow with sidebar navigation."""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QWidget
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    NavigationItemPosition,
)

from file_alchemy.ui.pages.compression_page import CompressionPage
from file_alchemy.ui.pages.media_page import MediaPage


class PlaceholderPage(QWidget):
    """Temporary placeholder page shown inside navigation tabs."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(title.replace(" ", "_"))

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            """
            font-size: 24px;
            color: #888;
            """
        )
        layout.addWidget(label)


class MainWindow(FluentWindow):
    """Top-level window with Fluent sidebar navigation."""

    def __init__(self) -> None:
        super().__init__()
        self._setup_navigation()
        self._setup_window()

    def _set_icon(self) -> None:
        try:
            base_path = Path(sys._MEIPASS)
        except AttributeError:
            base_path = Path(__file__).resolve().parent.parent.parent.parent

        icon_path = base_path / "assets" / "logo.ico"
        self.setWindowIcon(QIcon(str(icon_path)))

    def _setup_window(self) -> None:
        self.setWindowTitle("File Alchemy")
        self._set_icon()
        self.resize(1000, 650)

        # Move window control buttons to the top-left on macOS and Linux.
        # macOS style: [Close] [Min] [Max] ... [Title]
        if sys.platform in ("darwin", "linux"):
            layout = self.titleBar.hBoxLayout
            layout.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

            # More robust removal
            layout.removeWidget(self.titleBar.minBtn)
            layout.removeWidget(self.titleBar.maxBtn)
            layout.removeWidget(self.titleBar.closeBtn)

            # Insert buttons at the beginning (Close, Min, Max)
            layout.insertWidget(
                0, self.titleBar.closeBtn, 0, Qt.AlignmentFlag.AlignLeft
            )
            layout.insertWidget(1, self.titleBar.minBtn, 0, Qt.AlignmentFlag.AlignLeft)
            layout.insertWidget(2, self.titleBar.maxBtn, 0, Qt.AlignmentFlag.AlignLeft)
            layout.insertSpacing(3, 10)

            # macOS doesn't typically show an icon in the title bar
            if sys.platform == "darwin" and hasattr(self.titleBar, "iconLabel"):
                self.titleBar.iconLabel.hide()

        # Centre on screen
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                (geo.width() - self.width()) // 2,
                (geo.height() - self.height()) // 2,
            )

    def _setup_navigation(self) -> None:
        # --- Media Converter page ---
        self._media_page = MediaPage()
        self.addSubInterface(
            self._media_page,
            FluentIcon.MEDIA,
            "Convert",
        )

        # --- Compression page ---
        self._compression_page = CompressionPage()
        self.addSubInterface(
            self._compression_page,
            FluentIcon.ZIP_FOLDER,
            "Compress",
        )

        # --- Bottom-pinned settings page ---
        self._settings_page = PlaceholderPage("Settings")
        self.addSubInterface(
            self._settings_page,
            FluentIcon.SETTING,
            "Settings",
            position=NavigationItemPosition.BOTTOM,
        )
