"""Main application window - FluentWindow with sidebar navigation."""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    NavigationItemPosition,
)

from file_alchemy.ui.pages.compression.compression_page import CompressionPage
from file_alchemy.ui.pages.media.media_page import MediaPage
from file_alchemy.ui.pages.placeholder_page import PlaceholderPage


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
            self._reorder_title_bar()

        # Centre on screen
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                (geo.width() - self.width()) // 2,
                (geo.height() - self.height()) // 2,
            )

    def _reorder_title_bar(self) -> None:
        """Reposition title bar buttons to the left for macOS/Linux style."""
        if sys.platform == "darwin":
            self.setSystemTitleBarButtonVisible(True)
            self.titleBar.minBtn.hide()
            self.titleBar.maxBtn.hide()
            self.titleBar.closeBtn.hide()

            if hasattr(self.titleBar, "iconLabel"):
                self.titleBar.iconLabel.hide()

            self.titleBar.hBoxLayout.insertSpacing(0, 80)
            return

        layout = self.titleBar.hBoxLayout
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Remove from current layout (buttonLayout) to ensure they can be moved to hBoxLayout
        self.titleBar.buttonLayout.removeWidget(self.titleBar.minBtn)
        self.titleBar.buttonLayout.removeWidget(self.titleBar.maxBtn)
        self.titleBar.buttonLayout.removeWidget(self.titleBar.closeBtn)

        layout.insertWidget(0, self.titleBar.closeBtn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.insertWidget(1, self.titleBar.minBtn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.insertWidget(2, self.titleBar.maxBtn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.insertSpacing(3, 10)

    def resizeEvent(self, e) -> None:
        """Override resizeEvent to ensure title bar starts at (0,0) on macOS/Linux."""
        super().resizeEvent(e)
        if sys.platform in ("darwin", "linux"):
            self.titleBar.move(0, 0)
            self.titleBar.resize(self.width(), self.titleBar.height())

    def _setup_navigation(self) -> None:
        self.navigationInterface.setReturnButtonVisible(False)

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
