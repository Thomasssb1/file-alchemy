from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ConversionRoute:
    """A registered conversion between two formats."""

    input_ext: str
    output_ext: str
    # Human-readable category shown in the UI
    category: str
    # Callable that accepts (input_path, output_path, **kwargs)
    engine_fn: Callable
