"""Unit tests for file_alchemy.engines.registry."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from file_alchemy.engines.registry import (
    ConversionRegistry,
    ConversionRoute,
    DEFAULT_REGISTRY,
    _category_of,
)


# --------------------------------------------------------------------------- #
# _category_of
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "ext, expected",
    [
        ("mp4", "Video"),
        ("mkv", "Video"),
        ("avi", "Video"),
        ("webm", "Video"),
        ("mov", "Video"),
        ("flv", "Video"),
        ("wmv", "Video"),
        ("ts", "Video"),
        ("m4v", "Video"),
        ("gif", "Video"),
        ("mp3", "Audio"),
        ("wav", "Audio"),
        ("flac", "Audio"),
        ("aac", "Audio"),
        ("ogg", "Audio"),
        ("m4a", "Audio"),
        ("wma", "Audio"),
        ("opus", "Audio"),
        ("aiff", "Audio"),
        ("png", "Image"),
        ("jpg", "Image"),
        ("jpeg", "Image"),
        ("bmp", "Image"),
        ("tiff", "Image"),
        ("tif", "Image"),
        ("webp", "Image"),
        ("ico", "Image"),
        ("avif", "Image"),
    ],
)
def test_category_of_known_extensions(ext: str, expected: str) -> None:
    assert _category_of(ext) == expected


def test_category_of_unknown_extension_returns_none() -> None:
    assert _category_of("xyz") is None
    assert _category_of("") is None


# --------------------------------------------------------------------------- #
# ConversionRegistry.register / get_route
# --------------------------------------------------------------------------- #


def test_register_and_get_route(
    empty_registry: ConversionRegistry, mock_engine_fn: MagicMock
) -> None:
    route = ConversionRoute(
        input_ext="mp4", output_ext="avi", category="Video", engine_fn=mock_engine_fn
    )
    empty_registry.register(route)
    assert empty_registry.get_route("mp4", "avi") is route


def test_get_route_normalises_dots_and_case(
    empty_registry: ConversionRegistry, mock_engine_fn: MagicMock
) -> None:
    empty_registry.register(
        ConversionRoute(
            input_ext="mp4", output_ext="avi", category="Video", engine_fn=mock_engine_fn
        )
    )
    assert empty_registry.get_route(".MP4", ".AVI") is not None
    assert empty_registry.get_route("MP4", "AVI") is not None


def test_get_route_missing_returns_none(empty_registry: ConversionRegistry) -> None:
    assert empty_registry.get_route("xyz", "abc") is None


def test_register_overwrites_existing(empty_registry: ConversionRegistry) -> None:
    fn1, fn2 = MagicMock(), MagicMock()
    route1 = ConversionRoute("mp4", "avi", "Video", fn1)
    route2 = ConversionRoute("mp4", "avi", "Video", fn2)
    empty_registry.register(route1)
    empty_registry.register(route2)
    assert empty_registry.get_route("mp4", "avi") is route2


# --------------------------------------------------------------------------- #
# outputs_for
# --------------------------------------------------------------------------- #


def test_outputs_for_returns_all_registered_targets(
    empty_registry: ConversionRegistry, mock_engine_fn: MagicMock
) -> None:
    empty_registry.register(ConversionRoute("png", "jpg", "Image", mock_engine_fn))
    empty_registry.register(ConversionRoute("png", "webp", "Image", mock_engine_fn))
    empty_registry.register(ConversionRoute("mp3", "wav", "Audio", mock_engine_fn))

    outputs = empty_registry.outputs_for("png")
    assert set(outputs) == {"jpg", "webp"}


def test_outputs_for_unknown_ext_returns_empty(empty_registry: ConversionRegistry) -> None:
    assert empty_registry.outputs_for("xyz") == []


def test_outputs_for_normalises_dots(
    empty_registry: ConversionRegistry, mock_engine_fn: MagicMock
) -> None:
    empty_registry.register(ConversionRoute("png", "jpg", "Image", mock_engine_fn))
    assert "jpg" in empty_registry.outputs_for(".PNG")


# --------------------------------------------------------------------------- #
# is_supported
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "in_ext, out_ext, supported",
    [
        ("png", "jpg", True),
        ("png", "xyz", False),
        ("xyz", "abc", False),
    ],
)
def test_is_supported(
    in_ext: str,
    out_ext: str,
    supported: bool,
    empty_registry: ConversionRegistry,
    mock_engine_fn: MagicMock,
) -> None:
    empty_registry.register(ConversionRoute("png", "jpg", "Image", mock_engine_fn))
    assert empty_registry.is_supported(in_ext, out_ext) is supported


# --------------------------------------------------------------------------- #
# all_routes property
# --------------------------------------------------------------------------- #


def test_all_routes_returns_list(
    empty_registry: ConversionRegistry, mock_engine_fn: MagicMock
) -> None:
    assert empty_registry.all_routes == []
    empty_registry.register(ConversionRoute("mp4", "mkv", "Video", mock_engine_fn))
    assert len(empty_registry.all_routes) == 1


# --------------------------------------------------------------------------- #
# DEFAULT_REGISTRY (integration)
# --------------------------------------------------------------------------- #


def test_default_registry_has_common_video_conversions() -> None:
    assert DEFAULT_REGISTRY.is_supported("mp4", "mkv")
    assert DEFAULT_REGISTRY.is_supported("mp4", "avi")
    assert DEFAULT_REGISTRY.is_supported("mkv", "mp4")


def test_default_registry_has_common_audio_conversions() -> None:
    assert DEFAULT_REGISTRY.is_supported("mp3", "wav")
    assert DEFAULT_REGISTRY.is_supported("wav", "flac")
    assert DEFAULT_REGISTRY.is_supported("flac", "mp3")


def test_default_registry_has_common_image_conversions() -> None:
    assert DEFAULT_REGISTRY.is_supported("png", "jpg")
    assert DEFAULT_REGISTRY.is_supported("jpg", "webp")
    assert DEFAULT_REGISTRY.is_supported("webp", "tiff")


def test_default_registry_has_cross_category_video_to_gif() -> None:
    assert DEFAULT_REGISTRY.is_supported("mp4", "gif")
    assert DEFAULT_REGISTRY.is_supported("mkv", "gif")


def test_default_registry_has_cross_category_video_to_audio() -> None:
    assert DEFAULT_REGISTRY.is_supported("mp4", "mp3")
    assert DEFAULT_REGISTRY.is_supported("mkv", "aac")


def test_default_registry_no_same_ext_routes() -> None:
    """No route should map an extension to itself."""
    for route in DEFAULT_REGISTRY.all_routes:
        assert route.input_ext != route.output_ext, (
            f"Self-loop route found: {route.input_ext} → {route.output_ext}"
        )


def test_default_registry_outputs_for_mp4_is_non_empty() -> None:
    outputs = DEFAULT_REGISTRY.outputs_for("mp4")
    assert len(outputs) > 0
    assert "mkv" in outputs
    assert "gif" in outputs
