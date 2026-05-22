"""Unit tests for file_alchemy.engines.compression_options."""

from __future__ import annotations

from file_alchemy.engines.compression.compression_mode import CompressionMode
from file_alchemy.engines.compression.compression_options import (
    CompressionOptions,
    _quality_to_audio_bitrate,
    _quality_to_crf,
    ext_category,
)


def test_ext_category() -> None:
    assert ext_category("mp4") == "video"
    assert ext_category("mp3") == "audio"
    assert ext_category("png") == "image"
    assert ext_category("gif") == "image"
    assert ext_category("txt") is None


def test_quality_to_crf() -> None:
    """CRF scales from 51 (quality=1) down to 0 (quality=100)"""
    assert _quality_to_crf(1) == 51
    assert _quality_to_crf(50) == 26
    assert _quality_to_crf(100) == 0
    # Boundary clamping
    assert _quality_to_crf(0) == 51
    assert _quality_to_crf(150) == 0


def test_quality_to_audio_bitrate() -> None:
    """Bitrate scales from 64 (quality=1) to 320 (quality=100)"""
    assert _quality_to_audio_bitrate(1) == 64
    assert _quality_to_audio_bitrate(100) == 320
    assert 128 <= _quality_to_audio_bitrate(50) <= 256


class TestToFfmpegArgs:
    def test_lossless_video(self) -> None:
        opts = CompressionOptions(CompressionMode.LOSSLESS)
        assert opts.to_ffmpeg_args("mp4") == ["-c:v", "libx264", "-crf", "0"]
        assert opts.to_ffmpeg_args("webm") == ["-c:v", "libvpx-vp9", "-lossless", "1"]

    def test_lossless_audio(self) -> None:
        opts = CompressionOptions(CompressionMode.LOSSLESS)
        assert opts.to_ffmpeg_args("flac") == ["-c:a", "flac"]
        assert opts.to_ffmpeg_args("wav") == ["-c:a", "pcm_s16le"]
        assert opts.to_ffmpeg_args("mp3") == ["-b:a", "320k"]

    def test_lossy_video(self) -> None:
        opts = CompressionOptions(CompressionMode.LOSSY, quality=75)
        crf_val = str(_quality_to_crf(75))
        assert opts.to_ffmpeg_args("mp4") == ["-c:v", "libx264", "-crf", crf_val]
        assert opts.to_ffmpeg_args("webm") == [
            "-c:v",
            "libvpx-vp9",
            "-crf",
            crf_val,
            "-b:v",
            "0",
        ]

    def test_lossy_audio(self) -> None:
        opts = CompressionOptions(CompressionMode.LOSSY, quality=50)
        br_val = str(_quality_to_audio_bitrate(50))
        assert opts.to_ffmpeg_args("mp3") == ["-b:a", f"{br_val}k"]

    def test_target_size_video(self) -> None:
        opts = CompressionOptions(
            CompressionMode.TARGET_SIZE, target_bytes=10 * 1024 * 1024
        )
        args = opts.to_ffmpeg_args("mp4", duration_seconds=10.0)
        assert "-c:v" in args
        assert "-b:v" in args
        assert "-b:a" in args
        assert "128k" in args  # default audio

    def test_target_size_audio(self) -> None:
        opts = CompressionOptions(
            CompressionMode.TARGET_SIZE, target_bytes=1024 * 1024
        )  # 1MB
        args = opts.to_ffmpeg_args("mp3", duration_seconds=60.0)
        assert "-b:a" in args
        # 1MB * 8 = 8,388,608 bits, / 60,000s ~ 139 kbps
        idx = args.index("-b:a")
        assert "139k" == args[idx + 1]

    def test_target_size_missing_params(self) -> None:
        opts = CompressionOptions(CompressionMode.TARGET_SIZE, target_bytes=None)
        assert opts.to_ffmpeg_args("mp4", 10.0) == []
        opts2 = CompressionOptions(CompressionMode.TARGET_SIZE, target_bytes=1000)
        assert opts2.to_ffmpeg_args("mp4", 0.0) == []


class TestToPillowKwargs:
    def test_lossless_png(self) -> None:
        opts = CompressionOptions(CompressionMode.LOSSLESS)
        kwargs = opts.to_pillow_kwargs("png")
        assert kwargs["compress_level"] == 9
        assert kwargs["optimize"] is True

    def test_lossy_jpeg(self) -> None:
        opts = CompressionOptions(CompressionMode.LOSSY, quality=60)
        kwargs = opts.to_pillow_kwargs("jpg")
        assert kwargs["quality"] == 60
        assert kwargs["optimize"] is True

    def test_target_size_image(self) -> None:
        # returns lossy kwargs to be used with binary search step
        opts = CompressionOptions(CompressionMode.TARGET_SIZE, target_bytes=100)
        kwargs = opts.to_pillow_kwargs("webp")
        assert "quality" in kwargs

    def test_lossy_gif(self) -> None:
        opts = CompressionOptions(CompressionMode.LOSSY, quality=60)
        kwargs = opts.to_pillow_kwargs("gif")
        assert kwargs["optimize"] is True


class TestRequiresTwoPass:
    def test_no_two_pass_for_lossless_or_lossy(self) -> None:
        opts1 = CompressionOptions(CompressionMode.LOSSLESS)
        opts2 = CompressionOptions(CompressionMode.LOSSY)
        assert opts1.requires_two_pass("mp4") is False
        assert opts2.requires_two_pass("mp4") is False

    def test_two_pass_only_for_target_size_video(self) -> None:
        opts = CompressionOptions(CompressionMode.TARGET_SIZE, target_bytes=1000)
        assert opts.requires_two_pass("mp4") is True
        assert opts.requires_two_pass("mp3") is False
        assert opts.requires_two_pass("png") is False


class TestEstimateSize:
    def test_returns_target_for_target_size(self, tmp_path) -> None:
        f = tmp_path / "in.mp4"
        f.write_text("x")
        opts = CompressionOptions(CompressionMode.TARGET_SIZE, target_bytes=42)
        assert opts.estimate_size(f) == 42

    def test_returns_original_size_for_lossless(self, tmp_path) -> None:
        f = tmp_path / "in.mp4"
        f.write_text("1234")
        opts = CompressionOptions(CompressionMode.LOSSLESS)
        assert opts.estimate_size(f) == 4

    def test_returns_quality_ratio_for_lossy(self, tmp_path) -> None:
        f = tmp_path / "in.mp4"
        f.write_bytes(b"x" * 100)
        # Quadratic formula: (64/100)^2 = 0.4096 → 40 bytes for 100-byte input
        opts = CompressionOptions(CompressionMode.LOSSY, quality=64)
        assert opts.estimate_size(f) == 40

    def test_lossy_quality_100_returns_full_size(self, tmp_path) -> None:
        f = tmp_path / "in.mp4"
        f.write_bytes(b"x" * 1000)
        opts = CompressionOptions(CompressionMode.LOSSY, quality=100)
        assert opts.estimate_size(f) == 1000

    def test_lossy_quality_50_is_quarter_of_input(self, tmp_path) -> None:
        f = tmp_path / "in.mp4"
        f.write_bytes(b"x" * 1000)
        # (50/100)^2 = 0.25
        opts = CompressionOptions(CompressionMode.LOSSY, quality=50)
        assert opts.estimate_size(f) == 250

    def test_lossy_quality_1_returns_at_least_1_byte(self, tmp_path) -> None:
        """Floor guard: extremely low quality must never produce a 0-byte estimate."""
        f = tmp_path / "in.mp4"
        f.write_bytes(b"x")  # 1-byte file
        opts = CompressionOptions(CompressionMode.LOSSY, quality=1)
        assert opts.estimate_size(f) >= 1

    def test_missing_file_returns_none(self) -> None:
        opts = CompressionOptions(CompressionMode.LOSSLESS)
        assert opts.estimate_size("missing.mp4") is None
