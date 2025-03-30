@echo off
echo === Starting DeepSeek-X Service ===

REM Check if virtual environment exists
if not exist venv (
    echo Error: Virtual environment not found. Please run setup.bat to install dependencies first.
    pause
    exit /b 1
)

REM Check if config file exists
if not exist config.json (
    echo Error: config.json file not found. Please run setup.bat or create the configuration file manually.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Start service
echo Starting DeepSeek-X service...
uvicorn main:app --host 127.0.0.1 --port 8000

REM Capture exit code
set exit_code=%errorlevel%

if %exit_code% neq 0 (
    echo Service exited abnormally, exit code: %exit_code%
) else (
    echo Service stopped normally
)

pause
exit /b %exit_code% 