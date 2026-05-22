"""Available compression strategies."""

from enum import Enum, auto


class CompressionMode(Enum):
    """Available compression strategies."""

    LOSSLESS = auto()
    LOSSY = auto()
    TARGET_SIZE = auto()
