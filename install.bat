@echo off
echo === DeepSeek-X Installation Script ===
echo Setting up development environment...

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not available. Please install Python 3.8 or higher.
    echo You can download Python from https://www.python.org/downloads/
    exit /b 1
)

REM Check Python version
python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" > tmp.txt
set /p py_ver=<tmp.txt
del tmp.txt

REM Simple version comparison
for /f "tokens=1,2 delims=." %%a in ("%py_ver%") do (
    set major=%%a
    set minor=%%b
)

if %major% LSS 3 (
    echo Error: Python 3.8 or higher is required, current version: %py_ver%
    exit /b 1
)

if %major% EQU 3 (
    if %minor% LSS 8 (
        echo Error: Python 3.8 or higher is required, current version: %py_ver%
        exit /b 1
    )
)

echo Python version check passed: %py_ver%

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