"""Application entry point - creates QApplication, sets theme, launches MainWindow."""

import os
import sys

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from file_alchemy.ui.main_window import MainWindow


def main() -> None:
    """Launch the File Alchemy application."""
    # Tell Windows this is a separate app from Python
    if os.name == "nt":
        import ctypes

        app_id = "filealchemy.desktopapp.1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    app = QApplication(sys.argv)
    app.setApplicationName("File Alchemy")
    app.setOrganizationName("FileAlchemy")

    setTheme(Theme.DARK)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
