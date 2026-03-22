"""FFmpeg missing exception."""

class FFmpegNotFoundError(Exception):
    """Raised when FFmpeg or ffprobe executables cannot be found on PATH."""
    pass
