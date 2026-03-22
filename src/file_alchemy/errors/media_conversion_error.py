"""Media conversion execution errors."""


class MediaConversionError(Exception):
    """Raised when FFmpeg/ffprobe fails to execute or convert a file upon invocation."""

    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.stderr = stderr
