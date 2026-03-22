# File Alchemy

<img src="./assets/logo.ico" alt="Logo" height="20" style="vertical-align:middle"> Universal file converter with FFmpeg integration, niche 3D pipelines, and a modern Fluent UI.

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

```bash
.venv\Scripts\pyinstaller --name "File Alchemy" --onefile --icon=assets/logo.ico --windowed src/file_alchemy/app.py
```

- The final `.exe` will be generated inside the `dist/` folder.
- You can safely delete the `build/` folder and `File Alchemy.spec` file that generate during the process.
