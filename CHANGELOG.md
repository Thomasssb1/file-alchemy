# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-05-22

### Added

- **GIF Compression**: Added GIF compression support, including animated GIF preservation, palette reduction, and target-size compression.
- **GIF Frame Sampling**: Added a GIF-only frame sampling control to keep 1 out of every N frames during compression.

## [1.1.0] - 2026-04-01

### Added

- **File Compression**: New dedicated Compress page supporting lossy, lossless, and target-size compression for video, audio, and image files, with output directory selection and per-file results.
- **ICO/ICNS Conversion**: Images can now be converted to ICO and ICNS icon formats via the media converter.
- **Two-Pass Video Encoding**: Target-size video compression now uses two-pass encoding for improved accuracy.
- **macOS/Linux Title-Bar Layout**: Window control buttons (close, minimise, maximise) are now positioned on the left on macOS and Linux to match native platform conventions.

### Updated

- **Media page renamed to Convert**: The navigation label has been changed from "Media" to "Convert" for clarity.

## [1.0.0] - 2026-03-22

### Added

- **Media Engine Core**: FFmpeg-powered conversion routing and execution system.
- **Fluent User Interface**: Highly polished, animated dark-mode UI utilizing `qfluentwidgets`.
- **Media Converter Page**: Intuitive drag-and-drop batch file processing with categorical format detection and real-time progress aggregation.
- **Sequential Task Queuing**: Concurrent-safe thread execution queue preventing PC lockups on massive batches.
- **PyInstaller Bundling**: Configured standalone Windows `.exe` deployment containing all assets out-of-the-box.
