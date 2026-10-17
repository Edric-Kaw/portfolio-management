@echo off
rem Navigate to the script directory
cd /d "%~dp0"

echo ===================================================
echo Launching Asset Analysis Dashboard...
echo ===================================================

rem Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python and check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

rem Create virtual environment if it does not exist
if not exist .venv (
    echo Creating Python virtual environment (.venv)...
    python -m venv .venv
)

rem Install/update dependencies
echo Installing/updating dependencies...
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install package dependencies.
    pause
    exit /b 1
)

rem Start Streamlit
echo Starting Streamlit...
.venv\Scripts\streamlit run app.py
if errorlevel 1 (
    echo [ERROR] Streamlit failed to start or crashed.
    pause
    exit /b 1
)

pause
