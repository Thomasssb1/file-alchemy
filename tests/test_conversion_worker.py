"""Tests for ConversionWorker thread."""

from pathlib import Path
from unittest.mock import MagicMock

from file_alchemy.engines.registry import ConversionRoute
from file_alchemy.ui.pages.media.conversion_worker import ConversionWorker


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
