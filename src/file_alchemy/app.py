"""Application entry point - creates QApplication, sets theme, launches MainWindow."""

import os
import sys

# Suppress the QFluentWidgets Pro print statement by briefly redirecting stdout
_original_stdout = sys.stdout
sys.stdout = open(os.devnull, "w")
try:
    from qfluentwidgets import Theme, setTheme
finally:
    sys.stdout.close()
    sys.stdout = _original_stdout

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from file_alchemy.ui.main_window import MainWindow


def main() -> None:
    """Launch the File Alchemy application."""
    # Tell Windows this is a separate app from Python
    if os.name == "nt":
        import ctypes

        app_id = "filealchemy.desktopapp.1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    # Suppress Qt font warnings and missing font performance costs
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts.warning=false"

    app = QApplication(sys.argv)
    app.setApplicationName("File Alchemy")
    app.setOrganizationName("FileAlchemy")

    # Prevent "Segoe UI" search overhead on macOS by setting a native font early
    if sys.platform == "darwin":
        app.setFont(QFont("SF Pro", 13))

    setTheme(Theme.DARK)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
