"""Compression page - dedicated UI for lossless/lossy compression."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    RadioButton,
    Slider,
    StrongBodyLabel,
    TitleLabel,
)

from file_alchemy.engines.compression_options import (
    CompressionMode,
    CompressionOptions,
    ext_category,
)
from file_alchemy.ui.components import DropZone, FileListPanel, ResultsPanel
from file_alchemy.ui.workers import CompressionWorker


def _format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class CompressionPage(QWidget):
    """File Compression page for lossless, lossy, and target-size reduction."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CompressionPage")
        self._current_worker: CompressionWorker | None = None
        self._queue: deque[Path] = deque()
        self._output_dir: Path | None = None
        self._pending: int = 0
        self._batch_total: int = 0

        self._setup_ui()
        self._update_controls_visibility()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(20)

        title = TitleLabel("File Compression")
        root.addWidget(title)

        self._drop_zone = DropZone(files_callback=self._on_files_added)
        root.addWidget(self._drop_zone)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        self._build_file_list_column(content_layout)
        self._build_controls_column(content_layout)

        root.addLayout(content_layout)

        self._progress_bar = ProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        root.addWidget(self._progress_bar)

        root.addStretch()

        self._results_panel = ResultsPanel()
        root.addWidget(self._results_panel)

    def _build_file_list_column(self, parent_layout: QHBoxLayout) -> None:
        self._file_panel = FileListPanel()
        self._file_panel.selectionChanged.connect(self._update_estimated_size)
        self._file_panel.listCleared.connect(
            lambda: self._compress_btn.setEnabled(False)
        )
        self._file_panel.listCleared.connect(self._update_estimated_size)
        parent_layout.addWidget(self._file_panel, stretch=2)

    def _build_controls_column(self, parent_layout: QHBoxLayout) -> None:
        col = QVBoxLayout()
        col.setSpacing(12)
        col.setAlignment(Qt.AlignmentFlag.AlignTop)

        col.addWidget(StrongBodyLabel("Compression mode"))

        self._radio_lossless = RadioButton("Lossless")
        self._radio_lossless.setChecked(True)
        self._radio_lossless.toggled.connect(self._update_controls_visibility)
        col.addWidget(self._radio_lossless)

        self._radio_lossy = RadioButton("Lossy")
        self._radio_lossy.toggled.connect(self._update_controls_visibility)
        col.addWidget(self._radio_lossy)

        self._radio_target = RadioButton("Target size")
        self._radio_target.toggled.connect(self._update_controls_visibility)
        col.addWidget(self._radio_target)

        # Quality slider widget
        self._quality_widget = QWidget()
        q_layout = QVBoxLayout(self._quality_widget)
        q_layout.setContentsMargins(0, 0, 0, 0)

        self._quality_label = QLabel("Quality: 75")
        q_layout.addWidget(self._quality_label)

        self._quality_slider = Slider(Qt.Orientation.Horizontal)
        self._quality_slider.setRange(1, 100)
        self._quality_slider.setValue(75)
        self._quality_slider.valueChanged.connect(self._on_quality_changed)
        q_layout.addWidget(self._quality_slider)
        col.addWidget(self._quality_widget)

        # Target size widget
        self._target_widget = QWidget()
        t_layout = QHBoxLayout(self._target_widget)
        t_layout.setContentsMargins(0, 0, 0, 0)

        self._target_spinbox = QSpinBox()
        self._target_spinbox.setRange(1, 999999)
        self._target_spinbox.setValue(800)
        self._target_spinbox.valueChanged.connect(self._update_estimated_size)
        t_layout.addWidget(self._target_spinbox, stretch=1)

        self._target_unit = QComboBox()
        self._target_unit.addItems(["KB", "MB"])
        self._target_unit.currentIndexChanged.connect(self._update_estimated_size)
        t_layout.addWidget(self._target_unit)
        col.addWidget(self._target_widget)

        col.addSpacing(8)

        self._estimate_label = QLabel("Est. output: ≈ --")
        self._estimate_label.setStyleSheet(
            """
            color: #6366f1;
            font-weight: bold;
            """
        )
        col.addWidget(self._estimate_label)

        col.addSpacing(8)

        self._output_dir_label = QLabel("Output: same folder as input")
        self._output_dir_label.setStyleSheet(
            """
            color: #888;
            font-size: 12px;
            """
        )
        col.addWidget(self._output_dir_label)

        pick_output_btn = PushButton(FluentIcon.FOLDER, "Choose output folder…")
        pick_output_btn.clicked.connect(self._pick_output_dir)
        col.addWidget(pick_output_btn)

        col.addSpacing(16)

        self._compress_btn = PrimaryPushButton(FluentIcon.ZIP_FOLDER, "Compress")
        self._compress_btn.setEnabled(False)
        self._compress_btn.clicked.connect(self._start_compression)
        col.addWidget(self._compress_btn)

        parent_layout.addLayout(col, stretch=1)

    def _update_controls_visibility(self) -> None:
        self._quality_widget.setVisible(self._radio_lossy.isChecked())
        self._target_widget.setVisible(self._radio_target.isChecked())
        self._update_estimated_size()

    def _on_quality_changed(self, value: int) -> None:
        self._quality_label.setText(f"Quality: {value}")
        self._update_estimated_size()

    def _on_files_added(self, paths: list[Path]) -> None:
        valid_paths = [p for p in paths if ext_category(p.suffix.lstrip(".").lower())]
        if not valid_paths:
            return

        self._file_panel.add_files(valid_paths)
        self._compress_btn.setEnabled(self._file_panel.count > 0)
        self._update_estimated_size()

    def _pick_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if directory:
            self._output_dir = Path(directory)
            self._output_dir_label.setText(f"Output: {self._output_dir}")

    def _get_current_options(self) -> CompressionOptions:
        if self._radio_target.isChecked():
            mode = CompressionMode.TARGET_SIZE
        elif self._radio_lossy.isChecked():
            mode = CompressionMode.LOSSY
        else:
            mode = CompressionMode.LOSSLESS

        target_bytes = None
        if mode == CompressionMode.TARGET_SIZE:
            val = self._target_spinbox.value()
            mult = 1024 if self._target_unit.currentText() == "KB" else 1024 * 1024
            target_bytes = val * mult

        return CompressionOptions(
            mode=mode,
            quality=self._quality_slider.value(),
            target_bytes=target_bytes,
        )

    def _update_estimated_size(self) -> None:
        files = self._file_panel.files
        if not files:
            self._estimate_label.setText("Est. output: ≈ --")
            return

        row = self._file_panel.current_row
        if row < 0 or row >= len(files):
            row = 0

        path = files[row]
        options = self._get_current_options()

        est = options.estimate_size(path)
        if est is None:
            self._estimate_label.setText("Est. output: ≈ ?")
        else:
            prefix = "≈ " if options.mode != CompressionMode.TARGET_SIZE else ""
            self._estimate_label.setText(f"Est. output: {prefix}{_format_size(est)}")

    def _start_compression(self) -> None:
        files = self._file_panel.files
        if not files:
            return

        self._compress_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        self._queue.clear()
        self._queue.extend(files)
        self._batch_total = len(self._queue)
        self._pending = self._batch_total

        self._run_next_in_queue()

    def _resolve_output_path(self, input_path: Path) -> Path:
        base = self._output_dir or input_path.parent
        out = base / f"{input_path.stem}_compressed{input_path.suffix}"
        count = 2
        while out.exists():
            out = base / f"{input_path.stem}_compressed_{count}{input_path.suffix}"
            count += 1
        return out

    def _run_next_in_queue(self) -> None:
        if not self._queue:
            return

        input_path = self._queue.popleft()
        output_path = self._resolve_output_path(input_path)
        ext = output_path.suffix.lstrip(".").lower()
        category = ext_category(ext) or "unknown"
        options = self._get_current_options()

        self._current_worker = CompressionWorker(
            input_path, output_path, options, category
        )
        self._current_worker.progress.connect(self._on_progress)
        self._current_worker.finished.connect(self._on_finished)
        self._current_worker.error.connect(self._on_error)
        self._current_worker.start()

    def _on_progress(self, pct: float) -> None:
        if self._batch_total > 0:
            completed = self._batch_total - self._pending
            overall_pct = ((completed * 100) + pct) / self._batch_total
            self._progress_bar.setValue(int(min(100, overall_pct)))

    def _on_finished(self, output_path: Path, original: int, final: int) -> None:
        name = output_path.name
        o_str = _format_size(original)
        f_str = _format_size(final)
        pct_change = ((original - final) / original) * 100 if original > 0 else 0.0

        grew = pct_change < 0
        arrow = "↑" if grew else "↓"
        display_pct = abs(pct_change)
        suffix = " larger" if grew else ""

        msg = f"Saved: {name} — {o_str} → {f_str} ({display_pct:.1f}% {arrow})"
        list_msg = f"{name}:  {o_str} → {f_str}  ({display_pct:.1f}% {arrow}{suffix})"

        if grew:
            self._results_panel.add_warning(list_msg, folder_path=output_path.parent)
            show_bar = InfoBar.warning
            title = "Size Increased"
        else:
            self._results_panel.add_success(list_msg, folder_path=output_path.parent)
            show_bar = InfoBar.success
            title = "Success"

        show_bar(
            title=title,
            content=msg,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=4000,
            parent=self,
        )
        self._complete_one()

    def _on_error(self, message: str) -> None:
        InfoBar.error(
            title="Compression failed",
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=6000,
            parent=self,
        )
        self._results_panel.add_error(message)
        self._complete_one()

    def _complete_one(self) -> None:
        if self._current_worker:
            self._current_worker.deleteLater()
            self._current_worker = None

        self._pending -= 1
        if self._pending <= 0:
            self._reset_after_batch()
        else:
            self._run_next_in_queue()

    def _reset_after_batch(self) -> None:
        self._progress_bar.setVisible(False)
        self._progress_bar.setValue(0)
        self._compress_btn.setEnabled(self._file_panel.count > 0)
