"""Tests for background worker threads (ConversionWorker, CompressionWorker)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from file_alchemy.engines.registry import ConversionRoute
from file_alchemy.errors.media_conversion_error import MediaConversionError
from file_alchemy.ui.workers import CompressionWorker, ConversionWorker


def test_conversion_worker_success(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    inp.touch()

    # Create a mock engine function that just returns the output path
    mock_engine = MagicMock(return_value=out)
    route = ConversionRoute(
        input_ext="mp4",
        output_ext="mp4",
        category="video",
        engine_fn=mock_engine,
    )

    worker = ConversionWorker(inp, out, route, extra_args=["-v"])

    finished_args = []
    error_args = []
    worker.finished.connect(lambda res: finished_args.append(res))
    worker.error.connect(lambda err: error_args.append(err))

    worker.run()

    mock_engine.assert_called_once()
    assert finished_args == [out]
    assert error_args == []


def test_conversion_worker_error(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    inp.touch()

    mock_engine = MagicMock(side_effect=ValueError("Test exception"))
    route = ConversionRoute(
        input_ext="mp4",
        output_ext="mp4",
        category="video",
        engine_fn=mock_engine,
    )

    worker = ConversionWorker(inp, out, route)

    finished_args = []
    error_args = []
    worker.finished.connect(lambda res: finished_args.append(res))
    worker.error.connect(lambda err: error_args.append(err))

    worker.run()

    mock_engine.assert_called_once()
    assert finished_args == []
    assert len(error_args) == 1
    assert "Unexpected error: Test exception" in error_args[0]


def test_compression_worker_image_success(tmp_path: Path) -> None:
    inp = tmp_path / "in.png"
    out = tmp_path / "out.jpg"
    inp.write_bytes(b"dummy_data_12345")  # 16 bytes

    mock_options = MagicMock()
    mock_options.category = "image"

    worker = CompressionWorker(inp, out, mock_options, "image")

    finished_args = []
    error_args = []
    # signature: finished(object, int, int)
    worker.finished.connect(lambda res, orig, new: finished_args.append((res, orig, new)))
    worker.error.connect(lambda err: error_args.append(err))

    # Mock compress_image to simulate a compressed output file
    def fake_compress(*args, **kwargs):
        out.write_bytes(b"compressed")  # 10 bytes
        return out

    with patch("file_alchemy.ui.workers.compress_image", side_effect=fake_compress) as mock_img:
        worker.run()

    mock_img.assert_called_once()
    assert len(finished_args) == 1
    res, orig_size, new_size = finished_args[0]
    assert res == out
    assert orig_size == 16
    assert new_size == 10
    assert error_args == []


def test_compression_worker_media_success(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    inp.write_bytes(b"large_video_data_123")  # 20 bytes

    mock_options = MagicMock()
    mock_options.category = "video"

    worker = CompressionWorker(inp, out, mock_options, "video")

    finished_args = []
    error_args = []
    worker.finished.connect(lambda res, orig, new: finished_args.append((res, orig, new)))
    worker.error.connect(lambda err: error_args.append(err))

    def fake_compress(*args, **kwargs):
        out.write_bytes(b"smaller")  # 7 bytes
        return out

    with patch("file_alchemy.ui.workers.compress_media", side_effect=fake_compress) as mock_media:
        worker.run()

    mock_media.assert_called_once()
    assert len(finished_args) == 1
    res, orig_size, new_size = finished_args[0]
    assert res == out
    assert orig_size == 20
    assert new_size == 7
    assert error_args == []


def test_compression_worker_media_conversion_error(tmp_path: Path) -> None:
    inp = tmp_path / "in.mp4"
    out = tmp_path / "out.mp4"
    inp.touch()

    worker = CompressionWorker(inp, out, MagicMock(), "video")

    finished_args = []
    error_args = []
    worker.finished.connect(lambda res, orig, new: finished_args.append((res, orig, new)))
    worker.error.connect(lambda err: error_args.append(err))

    with patch("file_alchemy.ui.workers.compress_media", side_effect=MediaConversionError("FFmpeg failed")):
        worker.run()

    assert finished_args == []
    assert len(error_args) == 1
    assert error_args[0] == "FFmpeg failed"


def test_compression_worker_generic_error(tmp_path: Path) -> None:
    inp = tmp_path / "in.png"
    out = tmp_path / "out.png"
    inp.touch()

    worker = CompressionWorker(inp, out, MagicMock(), "image")

    finished_args = []
    error_args = []
    worker.finished.connect(lambda res, orig, new: finished_args.append((res, orig, new)))
    worker.error.connect(lambda err: error_args.append(err))

    with patch("file_alchemy.ui.workers.compress_image", side_effect=RuntimeError("Out of memory")):
        worker.run()

    assert finished_args == []
    assert len(error_args) == 1
    assert error_args[0] == "Unexpected error: Out of memory"
