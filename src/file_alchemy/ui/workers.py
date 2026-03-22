"""QThread-based conversion worker for non-blocking FFmpeg calls."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from file_alchemy.engines import media_engine
from file_alchemy.engines.registry import ConversionRoute
from file_alchemy.errors.media_conversion_error import MediaConversionError


class ConversionWorker(QThread):
    """Run a single file conversion on a background thread.

    Signals:
        progress(float):  Emitted with values in [0, 100] during conversion.
        finished(Path):   Emitted with the resolved output path on success.
        error(str):       Emitted with a human-readable message on failure.
    """

    progress: pyqtSignal = pyqtSignal(float)
    finished: pyqtSignal = pyqtSignal(Path)
    error: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        route: ConversionRoute,
        extra_args: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._input_path = input_path
        self._output_path = output_path
        self._route = route
        self._extra_args = extra_args or []

    def run(self) -> None:
        """Execute the conversion. Called automatically by QThread.start()."""
        try:
            result = media_engine.convert(
                self._input_path,
                self._output_path,
                extra_args=self._extra_args,
                progress_callback=self.progress.emit,
            )
            self.finished.emit(result)
        except MediaConversionError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Unexpected error: {exc}")
