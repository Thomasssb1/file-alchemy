# <img src="./assets/logo.ico" alt="Logo" height="40" style="vertical-align:middle"> File Alchemy

[![CI](https://github.com/Thomasssb1/file-alchemy/actions/workflows/ci.yml/badge.svg)](https://github.com/Thomasssb1/file-alchemy/actions/workflows/ci.yml) [![Coverage](https://img.shields.io/badge/coverage-unknown-lightgrey)](https://github.com/Thomasssb1/file-alchemy/actions/workflows/ci.yml) [![Version](https://img.shields.io/github/v/release/Thomasssb1/file-alchemy?display_name=tag)](https://github.com/Thomasssb1/file-alchemy/releases) [![License](https://img.shields.io/github/license/Thomasssb1/file-alchemy)](https://github.com/Thomasssb1/file-alchemy/blob/main/LICENSE)

Universal file converter with FFmpeg integration and a modern Windows-inspired UI.

![File Alchemy](./assets/screenshots/main-init.png)

## Prerequisites

- Python ≥ 3.11
- [FFmpeg](https://ffmpeg.org/download.html) on PATH (required for media conversions)

## 1. Setup & Installation

```bash
# Create a virtual environment
python -m venv .venv

# Install the application and development dependencies in editable mode
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 2. Running the Application

```bash
# Run the application
.venv\Scripts\python.exe -m file_alchemy

# Alternatively, since it's installed, you can just run:
.venv\Scripts\file-alchemy
```

## 3. Testing

Tests run with coverage checks enabled by default (minimum 80% enforced):

```bash
# Run all tests (coverage runs automatically)
.venv\Scripts\python.exe -m pytest

# Run only the UI component tests
.venv\Scripts\python.exe -m pytest tests/test_media_page.py -v

# Generate an HTML coverage report
.venv\Scripts\python.exe -m pytest --cov-report=html
```

Tests work headlessly in CI — `QT_QPA_PLATFORM=offscreen` is set automatically.

## 4. Linting

```bash
# Check for issues
ruff check .

# Auto-format
ruff format .
```

## 5. Building the Executable

To bundle the application into a distribution folder containing the executable and its dependencies, use the provided PyInstaller spec file.

Run this command from the root of the project:

```bash
.venv\Scripts\pyinstaller "file_alchemy.spec"
```

- The final application and its compiled dependencies will be generated inside the `dist/File Alchemy/` folder. The primary executable is `dist/File Alchemy/File Alchemy.exe`.
- You can safely delete the `build/` folder that generates during the process.
