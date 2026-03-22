"""Conversion registry: maps (input_ext, output_ext) pairs to engines.

The UI queries this module to build format-picker dropdowns and to guard
against unsupported conversions before handing off to an engine.

Extension strings are stored **without** leading dots, in lower-case
(e.g. ``"mp4"``, ``"png"``).
"""

from __future__ import annotations

from .conversion_registry import ConversionRegistry
from .conversion_route import ConversionRoute
from .default_registry import DEFAULT_REGISTRY, _category_of

__all__ = [
    "ConversionRegistry",
    "ConversionRoute",
    "DEFAULT_REGISTRY",
    "_category_of",
]
