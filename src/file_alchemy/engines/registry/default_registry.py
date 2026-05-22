"""Default application-wide conversion registry and format definitions."""

from __future__ import annotations

from .conversion_registry import ConversionRegistry
from .conversion_route import ConversionRoute

# --------------------------------------------------------------------------- #
# Format definitions
# --------------------------------------------------------------------------- #

_VIDEO_EXTS: frozenset[str] = frozenset(
    {"mp4", "mkv", "avi", "webm", "mov", "flv", "wmv", "ts", "m4v", "gif"}
)
_AUDIO_EXTS: frozenset[str] = frozenset(
    {"mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "opus", "aiff"}
)
_IMAGE_EXTS: frozenset[str] = frozenset(
    {"png", "jpg", "jpeg", "bmp", "tiff", "tif", "webp", "ico", "icns", "avif"}
)

# Map a category name to the set of extensions that belong to it.
CATEGORY_EXTS: dict[str, frozenset[str]] = {
    "Video": _VIDEO_EXTS,
    "Audio": _AUDIO_EXTS,
    "Image": _IMAGE_EXTS,
}

# Cross-format conversions supported by FFmpeg (e.g. video → gif, video → mp3).
_CROSS_CONVERSIONS: dict[str, set[str]] = {
    "Video": {
        "gif",
        "mp3",
        "aac",
        "wav",
        "ico",
        "icns",
    },  # strip audio or make gif/icon
    "Audio": set(),  # audio → video not supported here
    "Image": set(),  # image → video out of scope
}


def _category_of(ext: str) -> str | None:
    """Return the category name for *ext*, or ``None`` if unknown."""
    for cat, exts in CATEGORY_EXTS.items():
        if ext in exts:
            return cat
    return None


# --------------------------------------------------------------------------- #
# Default registry construction
# --------------------------------------------------------------------------- #


def _build_default_registry() -> ConversionRegistry:
    """Build and return the application-wide default registry."""
    from file_alchemy.engines.media_engine import convert as _ffmpeg_convert
    from file_alchemy.engines.media_engine import convert_to_icon as _icon_convert

    registry = ConversionRegistry()

    for category, exts in CATEGORY_EXTS.items():
        extra_outputs = _CROSS_CONVERSIONS.get(category, set())

        for in_ext in exts:
            # Same-category conversions
            for out_ext in exts:
                if in_ext == out_ext:
                    continue

                engine_fn = (
                    _icon_convert if out_ext in {"ico", "icns"} else _ffmpeg_convert
                )

                registry.register(
                    ConversionRoute(
                        input_ext=in_ext,
                        output_ext=out_ext,
                        category=category,
                        engine_fn=engine_fn,
                    )
                )
            # Cross-category conversions (e.g. video → gif, video → mp3)
            for out_ext in extra_outputs:
                if out_ext == in_ext:
                    continue
                out_category = _category_of(out_ext) or category

                engine_fn = (
                    _icon_convert if out_ext in {"ico", "icns"} else _ffmpeg_convert
                )

                registry.register(
                    ConversionRoute(
                        input_ext=in_ext,
                        output_ext=out_ext,
                        category=out_category,
                        engine_fn=engine_fn,
                    )
                )

    return registry


# Singleton instance used by the rest of the application.
DEFAULT_REGISTRY: ConversionRegistry = _build_default_registry()
