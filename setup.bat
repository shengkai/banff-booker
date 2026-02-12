@echo off
REM ============================================================
REM  Banff Auto-Booker — One-click setup (Windows)
REM  Run:  setup.bat
REM ============================================================

echo.
echo ===================================
echo   Banff Campsite Auto-Booker Setup
echo ===================================
echo.

REM -- Check Python is available --
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    echo         Make sure "Add Python to PATH" is checked during install.
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/4] Installing dependencies...
pip install -e ".[dev]"
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [4/4] Installing Playwright Chromium browser...
playwright install chromium
if errorlevel 1 (
    echo [ERROR] Failed to install Chromium. You can retry later with: playwright install chromium
)

echo.
echo ===================================
echo   Setup complete!
echo ===================================
echo.
echo Next steps:
echo   1. Copy and edit your config:
echo        copy config.example.yaml config.yaml
echo        notepad config.yaml
echo.
echo   2. Activate the venv (if opening a new terminal):
echo        venv\Scripts\activate.bat
echo.
echo   3. Run the booker:
echo        auto-booker
echo.
pause
