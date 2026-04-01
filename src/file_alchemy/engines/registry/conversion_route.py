"""Data models for conversion routes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ConversionRoute:
    """A registered conversion between two formats."""

    input_ext: str
    output_ext: str
    # Human-readable category shown in the UI
    category: str
    # Callable that accepts (input_path, output_path, **kwargs)
    engine_fn: Callable

    def __post_init__(self) -> None:
        """Force format extensions to be lowercase without a leading dot."""
        object.__setattr__(self, "input_ext", self.input_ext.lower().lstrip("."))
        object.__setattr__(self, "output_ext", self.output_ext.lower().lstrip("."))
