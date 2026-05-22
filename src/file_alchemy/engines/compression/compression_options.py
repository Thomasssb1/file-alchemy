"""Compression settings: mode, quality, and target-size data model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from file_alchemy.engines.compression.compression_mode import CompressionMode

# Format groupings for codec selection
_VIDEO_EXTS: frozenset[str] = frozenset(
    {"mp4", "mkv", "avi", "webm", "mov", "flv", "wmv", "ts", "m4v"}
)
_AUDIO_EXTS: frozenset[str] = frozenset(
    {"mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "opus", "aiff"}
)
_IMAGE_EXTS: frozenset[str] = frozenset(
    {"png", "jpg", "jpeg", "bmp", "tiff", "tif", "webp", "ico", "avif"}
)

# Audio bitrate range for quality mapping (kbps)
_AUDIO_BITRATE_MIN = 64
_AUDIO_BITRATE_MAX = 320

# Default audio bitrate overhead for video target-size calculations (kbps)
_DEFAULT_AUDIO_BITRATE_KBPS = 128


def ext_category(ext: str) -> str | None:
    """Return 'video', 'audio', or 'image' for the given extension."""
    ext = ext.lower().lstrip(".")
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _IMAGE_EXTS:
        return "image"
    return None


def _quality_to_crf(quality: int) -> int:
    """Map user-facing quality 1–100 to H.264 CRF 51–0 (inverted)."""
    clamped = max(1, min(quality, 100))
    return round(51 * (1 - (clamped - 1) / 99))


def _quality_to_audio_bitrate(quality: int) -> int:
    """Map user-facing quality 1–100 to audio bitrate 64–320 kbps."""
    clamped = max(1, min(quality, 100))
    return round(
        _AUDIO_BITRATE_MIN
        + (_AUDIO_BITRATE_MAX - _AUDIO_BITRATE_MIN) * (clamped - 1) / 99
    )


@dataclass(frozen=True)
class CompressionOptions:
    """Encapsulates compression settings chosen by the user.

    Attributes:
        mode:         The compression strategy.
        quality:      User-facing quality level (1–100). Only used for LOSSY.
        target_bytes: Desired output file size in bytes. Only used for TARGET_SIZE.

    """

    mode: CompressionMode
    quality: int = 75
    target_bytes: int | None = None

    # ------------------------------------------------------------------ #
    # FFmpeg argument builders
    # ------------------------------------------------------------------ #

    def to_ffmpeg_args(
        self, output_ext: str, duration_seconds: float = 0.0
    ) -> list[str]:
        """Convert these options to FFmpeg CLI arguments.

        Args:
            output_ext: Target format extension (without dot).
            duration_seconds: Duration of the input media, needed for
                target-size bitrate calculation.

        Returns:
            A list of FFmpeg CLI flags (e.g. ``["-crf", "0"]``).

        """
        category = ext_category(output_ext)

        if self.mode is CompressionMode.LOSSLESS:
            return self._lossless_args(output_ext, category)

        if self.mode is CompressionMode.LOSSY:
            return self._lossy_args(output_ext, category)

        if self.mode is CompressionMode.TARGET_SIZE:
            return self._target_size_args(output_ext, category, duration_seconds)

        return []

    def _lossless_args(self, output_ext: str, category: str | None) -> list[str]:
        if category == "video":
            if output_ext in {"webm"}:
                return ["-c:v", "libvpx-vp9", "-lossless", "1"]
            return ["-c:v", "libx264", "-crf", "0"]

        if category == "audio":
            if output_ext in {"flac"}:
                return ["-c:a", "flac"]
            if output_ext in {"wav", "aiff"}:
                return ["-c:a", "pcm_s16le"]
            if output_ext in {"m4a"}:
                return ["-c:a", "alac"]
            # Best-effort lossless for other audio formats
            return ["-b:a", f"{_AUDIO_BITRATE_MAX}k"]

        return []

    def _lossy_args(self, output_ext: str, category: str | None) -> list[str]:
        if category == "video":
            crf = _quality_to_crf(self.quality)
            if output_ext in {"webm"}:
                return ["-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0"]
            return ["-c:v", "libx264", "-crf", str(crf)]

        if category == "audio":
            bitrate = _quality_to_audio_bitrate(self.quality)
            return ["-b:a", f"{bitrate}k"]

        return []

    def _target_size_args(
        self, _: str, category: str | None, duration_seconds: float
    ) -> list[str]:
        if not self.target_bytes or duration_seconds <= 0:
            return []

        if category == "video":
            total_bitrate_kbps = (self.target_bytes * 8) / (duration_seconds * 1000)
            video_bitrate = max(
                1, int(total_bitrate_kbps - _DEFAULT_AUDIO_BITRATE_KBPS)
            )
            return [
                "-c:v",
                "libx264",
                "-b:v",
                f"{video_bitrate}k",
                "-c:a",
                "aac",
                "-b:a",
                f"{_DEFAULT_AUDIO_BITRATE_KBPS}k",
            ]

        if category == "audio":
            bitrate_kbps = max(
                1, int((self.target_bytes * 8) / (duration_seconds * 1000))
            )
            return ["-b:a", f"{bitrate_kbps}k"]

        return []

    # ------------------------------------------------------------------ #
    # Pillow argument builders (images only)
    # ------------------------------------------------------------------ #

    def to_pillow_kwargs(self, output_ext: str) -> dict[str, object]:
        """Convert these options to Pillow ``.save()`` keyword arguments.

        Args:
            output_ext: Target image format extension (without dot).

        Returns:
            Keyword arguments dict for ``Image.save()``.

        """
        ext = output_ext.lower().lstrip(".")

        if self.mode is CompressionMode.LOSSLESS:
            return self._pillow_lossless(ext)

        if self.mode is CompressionMode.LOSSY:
            return self._pillow_lossy(ext)

        if self.mode is CompressionMode.TARGET_SIZE:
            # Target-size for images is handled by the binary search in
            # image_engine; start with the quality as an initial guess.
            return self._pillow_lossy(ext)

        return {}

    @staticmethod
    def _pillow_lossless(ext: str) -> dict[str, object]:
        if ext in {"png"}:
            return {"compress_level": 9, "optimize": True}
        if ext in {"webp"}:
            return {"lossless": True}
        if ext in {"tiff", "tif"}:
            return {"compression": "tiff_lzw"}
        if ext in {"bmp", "ico"}:
            return {}
        # JPEG has no true lossless mode; use max quality
        if ext in {"jpg", "jpeg"}:
            return {"quality": 95, "subsampling": 0}
        return {}

    def _pillow_lossy(self, ext: str) -> dict[str, object]:
        if ext in {"jpg", "jpeg"}:
            return {"quality": self.quality, "optimize": True}
        if ext in {"webp"}:
            return {"quality": self.quality}
        if ext in {"png"}:
            # PNG is always lossless; use compression level proportional to quality
            level = max(0, min(9, 9 - round(self.quality * 9 / 100)))
            return {"compress_level": level, "optimize": True}
        if ext in {"avif"}:
            return {"quality": self.quality}
        return {}

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def requires_two_pass(self, output_ext: str) -> bool:
        """Return True if the output format needs two-pass encoding.

        Two-pass is used for target-size video to distribute bits optimally.
        """
        if self.mode is not CompressionMode.TARGET_SIZE:
            return False
        return ext_category(output_ext) == "video"

    def estimate_size(self, input_path: str | Path) -> int | None:
        """Return a rough estimated output size in bytes, or None if unknown.

        For TARGET_SIZE mode, the estimate is simply the target itself.
        For LOSSY, the estimate is derived from the input size scaled by the
        quality ratio. For LOSSLESS, the original size is returned unmodified
        since lossless compression has highly variable results.
        """
        input_path = Path(input_path)
        if not input_path.exists():
            return None

        original_bytes = input_path.stat().st_size
        if original_bytes == 0:
            return 0

        if self.mode is CompressionMode.TARGET_SIZE:
            return self.target_bytes

        if self.mode is CompressionMode.LOSSLESS:
            return original_bytes

        # LOSSY: approximate output size using a quadratic quality curve.
        ratio = (self.quality / 100) ** 2
        return max(1, int(original_bytes * ratio))
