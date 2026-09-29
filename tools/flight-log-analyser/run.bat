@echo off
REM ============================================================
REM  Drone Data Analytics - Windows launcher
REM ============================================================
setlocal EnableDelayedExpansion

cd /d "%~dp0"

REM --- Check Python is on PATH ---
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python is not on PATH.
    echo.
    echo Install Python 3.10 or later from https://www.python.org/downloads/windows/
    echo Make sure "Add Python to PATH" is checked during install.
    echo.
    pause
    exit /b 1
)

REM --- Check Python version is 3.10+ ---
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Found Python !PYVER!

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo.
    echo [ERROR] Python 3.10 or later is required. You have !PYVER!.
    echo Please upgrade from https://www.python.org/downloads/windows/
    echo.
    pause
    exit /b 1
)

REM --- Create venv if missing ---
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to create virtual environment.
        echo Check that the "venv" module is available: python -m venv --help
        echo.
        pause
        exit /b 1
    )
)

REM --- Activate venv ---
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate virtual environment.
    pause
    exit /b 1
)

REM --- Install / update dependencies ---
echo.
echo Installing dependencies (first run may take a few minutes)...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency install failed.
    echo If this is a pymavlink build error, install Microsoft C++ Build Tools
    echo or try:    pip install --only-binary=:all: pymavlink
    echo.
    pause
    exit /b 1
)

REM --- Launch Streamlit ---
echo.
echo ============================================================
echo  Starting Drone Analytics on http://localhost:8501
echo  Press Ctrl+C in this window to stop.
echo ============================================================
echo.
streamlit run app.py

endlocal
