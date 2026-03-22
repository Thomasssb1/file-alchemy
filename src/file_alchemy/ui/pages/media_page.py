"""Media Converter page — drag-drop, format picker, batch conversion."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
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

from file_alchemy.engines.registry import DEFAULT_REGISTRY, _category_of
from file_alchemy.ui.workers import ConversionWorker


class _DropZone(QFrame):
    """Drag-and-drop target that also shows a file-open button."""

    def __init__(
        self,
        files_callback: Callable[[list[Path]], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._files_callback = files_callback

        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.setObjectName("dropZone")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#dropZone {"
            "  border: 2px dotted #6366f1;"
            "  border-radius: 8px;"
            "  background: rgba(99, 102, 241, 0.09);"
            "}"
            "#dropZone:hover {"
            "  border-color: #818cf8;"
            "  background: rgba(99, 102, 241, 0.16);"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        icon_label = QLabel("📂")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 32px;")
        layout.addWidget(icon_label)

        hint = QLabel("Drop files here  or")
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
            self._files_callback(paths)


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
        self._queue: list[tuple[Path, Path, object]] = []
        self._input_files: list[Path] = []
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

        self._drop_zone = _DropZone(files_callback=self._on_files_added)
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

        root.addStretch()

    def _build_file_list_column(self, parent_layout: QHBoxLayout) -> None:
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(StrongBodyLabel("Selected files"))

        self._file_list = QListWidget()
        self._file_list.setMinimumHeight(150)
        self._file_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._file_list.currentRowChanged.connect(self._on_selection_changed)
        col.addWidget(self._file_list)

        clear_btn = PushButton(FluentIcon.DELETE, "Clear list")
        clear_btn.clicked.connect(self._clear_files)
        col.addWidget(clear_btn)
        parent_layout.addLayout(col, stretch=3)

    def _build_controls_column(self, parent_layout: QHBoxLayout) -> None:
        col = QVBoxLayout()
        col.setSpacing(12)
        col.setAlignment(Qt.AlignmentFlag.AlignTop)

        col.addWidget(StrongBodyLabel("Output format"))
        self._format_combo = QComboBox()
        self._format_combo.setMinimumWidth(180)
        self._format_combo.setStyleSheet(
            "QComboBox {"
            "  background: #2d2d2d;"
            "  color: #ffffff;"
            "  border: 1px solid #3d3d3d;"
            "  border-radius: 5px;"
            "  padding: 4px 8px;"
            "  font-size: 13px;"
            "}"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView {"
            "  background: #2d2d2d;"
            "  color: #ffffff;"
            "  selection-background-color: #404040;"
            "  border: 1px solid #3d3d3d;"
            "}"
        )
        col.addWidget(self._format_combo)

        col.addSpacing(8)

        self._output_dir_label = QLabel("Output: same folder as input")
        self._output_dir_label.setStyleSheet("color: #888; font-size: 12px;")
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
        for path in paths:
            if path not in self._input_files:
                self._input_files.append(path)
                self._file_list.addItem(QListWidgetItem(path.name))

        if self._input_files and self._file_list.currentRow() < 0:
            self._file_list.setCurrentRow(0)

    def _clear_files(self) -> None:
        self._input_files.clear()
        self._file_list.clear()
        self._format_combo.clear()
        self._convert_btn.setEnabled(False)

    def _on_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._input_files):
            return
        self._repopulate_format_combo(self._input_files[row])

    # ------------------------------------------------------------------ #
    # Format ComboBox — grouped by category
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
        if not out_ext or out_ext.startswith("──") or not self._input_files:
            return

        self._convert_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        self._queue.clear()

        for input_path in self._input_files:
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

        input_path, output_path, route = self._queue.pop(0)
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
        self._convert_btn.setEnabled(True)
