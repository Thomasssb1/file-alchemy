"""QThread-based conversion worker for non-blocking FFmpeg calls."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from file_alchemy.engines.registry import ConversionRoute
from file_alchemy.errors.media_conversion_error import MediaConversionError

from file_alchemy.engines.compression_options import CompressionOptions
from file_alchemy.engines.media_engine import compress_media
from file_alchemy.engines.image_engine import compress_image


class ConversionWorker(QThread):
    """Run a single file conversion on a background thread.

    Signals:
        progress(float):  Emitted with values in [0, 100] during conversion.
        finished(Path):   Emitted with the resolved output path on success.
        error(str):       Emitted with a human-readable message on failure.
    """

    progress: pyqtSignal = pyqtSignal(float)
    finished: pyqtSignal = pyqtSignal(object)
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
            result = self._route.engine_fn(
                self._input_path,
                self._output_path,
                extra_args=self._extra_args,
                progress_callback=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(f"Unexpected error: {exc}")


class CompressionWorker(QThread):
    """Run a single file compression on a background thread.

    Signals:
        progress(float):  Emitted with values in [0, 100] during compression.
        finished(Path, int, int): Emitted with (output_path, original_bytes, output_bytes) on success.
        error(str):       Emitted with a human-readable message on failure.
    """

    progress: pyqtSignal = pyqtSignal(float)
    finished: pyqtSignal = pyqtSignal(object, int, int)
    error: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        options: CompressionOptions,
        category: str,
    ) -> None:
        super().__init__()
        self._input_path = input_path
        self._output_path = output_path
        self._options = options
        self._category = category

    def run(self) -> None:
        try:
            original_bytes = self._input_path.stat().st_size
            result: Path

            if self._category == "image":
                result = compress_image(
                    self._input_path,
                    self._output_path,
                    self._options,
                    progress_callback=self.progress.emit,
                )
            else:
                result = compress_media(
                    self._input_path,
                    self._output_path,
                    self._options,
                    progress_callback=self.progress.emit,
                )

            output_bytes = result.stat().st_size
            self.finished.emit(result, original_bytes, output_bytes)
        except MediaConversionError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Unexpected error: {exc}")
