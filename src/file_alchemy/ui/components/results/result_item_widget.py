"""Custom widget for list items allowing border styling and Fluent icons."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget
from qfluentwidgets import FluentIcon, IconWidget


class ResultItemWidget(QWidget):
    """Custom widget for list items allowing border styling and Fluent icons."""

    def __init__(
        self, icon: FluentIcon, text: str, border_color: str = "transparent"
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.icon_widget = IconWidget(icon)
        self.icon_widget.setFixedSize(16, 16)
        layout.addWidget(self.icon_widget)

        self.label = QLabel(text)
        self.label.setStyleSheet(
            """
            background: transparent;
            border: none;
            """
        )
        layout.addWidget(self.label)
        layout.addStretch()

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"""
            ResultItemWidget {{
              border: 1px solid {border_color};
              border-radius: 4px;
              background: transparent;
            }}
            """
        )
