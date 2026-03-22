# File Alchemy

[![CI](https://github.com/Thomasssb1/file-alchemy/actions/workflows/ci.yml/badge.svg)](https://github.com/Thomasssb1/file-alchemy/actions/workflows/ci.yml) [![Coverage](https://img.shields.io/badge/coverage-unknown-lightgrey)](https://github.com/Thomasssb1/file-alchemy/actions/workflows/ci.yml) [![Version](https://img.shields.io/github/v/release/Thomasssb1/file-alchemy?display_name=tag)](https://github.com/Thomasssb1/file-alchemy/releases) [![License](https://img.shields.io/github/license/Thomasssb1/file-alchemy)](https://github.com/Thomasssb1/file-alchemy/blob/main/LICENSE)

Universal file converter with FFmpeg integration and a modern Windows-inspired UI.

## 1. Setup & Installation

To develop or run the project locally, create a virtual environment and install the package along with its development dependencies:

```bash
# Create a virtual environment
python -m venv .venv

# Install the application and development dependencies in editable mode
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 2. Running the Application

During development, you can quickly run the application directly from the virtual environment:

```bash
# Run the application
.venv\Scripts\python.exe -m file_alchemy

# Alternatively, since it's installed, you can just run:
.venv\Scripts\file-alchemy
```

## 3. Building the Executable (Rebuild)

To bundle the application into a standalone `.exe` file that you can share on GitHub without requiring users to install Python, use PyInstaller.

Run this command from the root of the project:

```bash
.venv\Scripts\pyinstaller --name "File Alchemy" --onefile --icon=assets/logo.ico --windowed src/file_alchemy/app.py
```

- The final `.exe` will be generated inside the `dist/` folder.
- You can safely delete the `build/` folder and `File Alchemy.spec` file that generate during the process.
