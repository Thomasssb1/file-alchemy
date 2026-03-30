"""Media Converter page - drag-drop, format picker, batch conversion."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    ProgressBar,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    TitleLabel,
)

from file_alchemy.engines.registry import (
    DEFAULT_REGISTRY,
    ConversionRoute,
    _category_of,
)
from file_alchemy.ui.components import DropZone, FileListPanel, ResultsPanel
from file_alchemy.ui.workers import ConversionWorker


class MediaPage(QWidget):
    """Media conversion page with batch file selection and format picker.

    Features:
    - Drag-and-drop or browse file selection (batch)
    - Auto-detect format and populate output ComboBox from registry
    - Shared progress bar across conversions
    - Success/error InfoBar notifications
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MediaPage")
        self._current_worker: ConversionWorker | None = None
        self._queue: deque[tuple[Path, Path, ConversionRoute]] = deque()
        self._output_dir: Path | None = None
        self._pending: int = 0
        self._batch_total: int = 0
        self._setup_ui()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(20)

        title = TitleLabel("Media Converter")
        root.addWidget(title)

        self._drop_zone = DropZone(files_callback=self._on_files_added)
        root.addWidget(self._drop_zone)

        list_and_controls = QHBoxLayout()
        list_and_controls.setSpacing(16)
        self._build_file_list_column(list_and_controls)
        self._build_controls_column(list_and_controls)
        root.addLayout(list_and_controls)

        self._progress_bar = ProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        root.addWidget(self._progress_bar)

        self._results_panel = ResultsPanel()
        root.addWidget(self._results_panel)

        root.addStretch()

    def _build_file_list_column(self, parent_layout: QHBoxLayout) -> None:
        self._file_panel = FileListPanel()
        self._file_panel.selectionChanged.connect(self._on_selection_changed)
        self._file_panel.listCleared.connect(self._on_list_cleared)
        parent_layout.addWidget(self._file_panel, stretch=3)

    def _on_list_cleared(self) -> None:
        if hasattr(self, "_format_combo"):
            self._format_combo.clear()
        if hasattr(self, "_convert_btn"):
            self._convert_btn.setEnabled(False)

    def _build_controls_column(self, parent_layout: QHBoxLayout) -> None:
        col = QVBoxLayout()
        col.setSpacing(12)
        col.setAlignment(Qt.AlignmentFlag.AlignTop)

        col.addWidget(StrongBodyLabel("Output format"))
        self._format_combo = QComboBox()
        self._format_combo.setMinimumWidth(180)
        self._format_combo.setStyleSheet(
            """
            QComboBox {
              background: #2d2d2d;
              color: #ffffff;
              border: 1px solid #3d3d3d;
              border-radius: 5px;
              padding: 4px 8px;
              font-size: 13px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
              background: #2d2d2d;
              color: #ffffff;
              selection-background-color: #404040;
              border: 1px solid #3d3d3d;
            }
            """
        )
        col.addWidget(self._format_combo)

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

        self._convert_btn = PrimaryPushButton(FluentIcon.PLAY, "Convert")
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._start_conversion)
        col.addWidget(self._convert_btn)

        parent_layout.addLayout(col, stretch=1)

    # ------------------------------------------------------------------ #
    # File management
    # ------------------------------------------------------------------ #

    def _on_files_added(self, paths: list[Path]) -> None:
        self._file_panel.add_files(paths)
        if self._file_panel.count == 1:
            # Force a re-evaluation on the first file since currentRowChanged might not fire inherently if pre-selected
            self._repopulate_format_combo(self._file_panel.files[0])

    def _on_selection_changed(self, row: int) -> None:
        files = self._file_panel.files
        if row < 0 or row >= len(files):
            return
        self._repopulate_format_combo(files[row])

    # ------------------------------------------------------------------ #
    # Format ComboBox - grouped by category
    # ------------------------------------------------------------------ #

    def _add_combo_header(self, text: str) -> None:
        """Append a non-selectable category header to the format combo."""
        self._format_combo.addItem(text)
        index = self._format_combo.count() - 1
        item = self._format_combo.model().item(index)
        item.setEnabled(False)
        item.setForeground(QColor("#888888"))

    def _repopulate_format_combo(self, path: Path) -> None:
        """Rebuild the format combo grouped by category for the given file.

        Same-category formats appear first under the input's own category
        header.  Cross-category outputs follow, each in their own group.
        """
        ext = path.suffix.lstrip(".").lower()
        in_category = _category_of(ext)
        outputs = DEFAULT_REGISTRY.outputs_for(ext)

        same: list[str] = []
        cross: dict[str, list[str]] = {}
        for out_ext in outputs:
            out_cat = _category_of(out_ext)
            if out_cat == in_category:
                same.append(out_ext)
            else:
                cross.setdefault(out_cat or "Other", []).append(out_ext)

        self._format_combo.clear()

        if same and in_category:
            self._add_combo_header(f"── {in_category} ──")
            for fmt in sorted(same):
                self._format_combo.addItem(fmt)

        for cat, exts in sorted(cross.items()):
            self._add_combo_header(f"── {cat}  (cross-format) ──")
            for fmt in sorted(exts):
                self._format_combo.addItem(fmt)

        self._select_first_enabled()
        self._convert_btn.setEnabled(self._format_combo.count() > 0)

    def _select_first_enabled(self) -> None:
        """Advance the combo selection past any disabled header items."""
        model = self._format_combo.model()
        for i in range(self._format_combo.count()):
            if model.item(i).isEnabled():
                self._format_combo.setCurrentIndex(i)
                return

    # ------------------------------------------------------------------ #
    # Output directory
    # ------------------------------------------------------------------ #

    def _pick_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if directory:
            self._output_dir = Path(directory)
            self._output_dir_label.setText(f"Output: {self._output_dir}")

    def _resolve_output_path(self, input_path: Path, out_ext: str) -> Path:
        base = self._output_dir or input_path.parent
        return base / f"{input_path.stem}.{out_ext}"

    # ------------------------------------------------------------------ #
    # Conversion
    # ------------------------------------------------------------------ #

    def _start_conversion(self) -> None:
        out_ext = self._format_combo.currentText()
        files = self._file_panel.files
        if not out_ext or out_ext.startswith("──") or not files:
            return

        self._convert_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        self._queue.clear()

        for input_path in files:
            in_ext = input_path.suffix.lstrip(".").lower()
            route = DEFAULT_REGISTRY.get_route(in_ext, out_ext)
            if route is None:
                self._show_error(
                    f"No conversion route for {in_ext} → {out_ext}. Skipped."
                )
                continue

            output_path = self._resolve_output_path(input_path, out_ext)
            self._queue.append((input_path, output_path, route))

        self._batch_total = len(self._queue)
        self._pending = self._batch_total

        if self._pending == 0:
            self._reset_after_batch()
        else:
            self._run_next_in_queue()

    def _run_next_in_queue(self) -> None:
        """Pop the next conversion task and start the worker."""
        if not self._queue:
            return

        input_path, output_path, route = self._queue.popleft()
        self._current_worker = ConversionWorker(input_path, output_path, route)
        self._current_worker.progress.connect(self._on_progress)
        self._current_worker.finished.connect(self._on_finished)
        self._current_worker.error.connect(self._on_error)
        self._current_worker.start()

    def _on_progress(self, pct: float) -> None:
        if self._batch_total > 0:
            completed = self._batch_total - self._pending
            overall_pct = ((completed * 100) + pct) / self._batch_total
            self._progress_bar.setValue(int(overall_pct))

    def _on_finished(self, output_path: Path) -> None:
        self._results_panel.add_success(
            output_path.name, folder_path=output_path.parent
        )

        InfoBar.success(
            title="Done",
            content=f"Saved: {output_path.name}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=4000,
            parent=self,
        )
        self._complete_one()

    def _on_error(self, message: str) -> None:
        self._results_panel.add_error(message)
        self._show_error(message)
        self._complete_one()

    def _complete_one(self) -> None:
        """Decrement the pending counter and run next or reset UI."""
        if self._current_worker:
            self._current_worker.deleteLater()
            self._current_worker = None

        self._pending -= 1
        if self._pending <= 0:
            self._reset_after_batch()
        else:
            self._run_next_in_queue()

    def _show_error(self, message: str) -> None:
        InfoBar.error(
            title="Conversion failed",
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=6000,
            parent=self,
        )

    def _reset_after_batch(self) -> None:
        self._progress_bar.setVisible(False)
        self._progress_bar.setValue(0)
        out_ext = self._format_combo.currentText()
        has_valid_ext = bool(out_ext and not out_ext.startswith("──"))
        self._convert_btn.setEnabled(self._file_panel.count > 0 and has_valid_ext)
