@echo off
setlocal enabledelayedexpansion

echo === DeepSeek-X Installation Script ===
echo Setting up development environment...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not available. Please install Python 3.11 or higher.
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%a in ('python --version 2^>^&1') do set py_ver=%%a
for /f "tokens=1,2 delims=." %%a in ("!py_ver!") do set py_major=%%a& set py_minor=%%b

REM Check Python version
if !py_major! neq 3 (
    echo Error: Python 3.11 or higher is required, current version: !py_ver!
    exit /b 1
)

if !py_minor! lss 11 (
    echo Error: Python 3.11 or higher is required, current version: !py_ver!
    exit /b 1
)

echo Python version check passed: !py_ver!

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install core dependencies
echo Installing core dependencies...
pip install fastapi uvicorn pydantic httpx python-dotenv aiohttp sse-starlette

REM If pyproject.toml exists, use pip to install project dependencies
if exist pyproject.toml (
    echo Detected pyproject.toml, installing project dependencies...
    pip install -e .
)

REM Create config file
echo Setting up configuration...
call setup.bat

echo Installation complete!
echo Use the following command to run the application:
echo   run.bat

pause 