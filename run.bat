@echo off
echo === Starting DeepSeek-X Service ===

REM Check if virtual environment exists
if not exist venv (
    echo Error: Virtual environment not found. Please run install.bat to install dependencies first.
    exit /b 1
)

REM Check if config file exists
if not exist config.json (
    if exist config_example.json (
        echo config.json file not found, but config_example.json exists.
        set /p choice="Would you like to run setup.bat to create the configuration file now? (y/n): "
        if /i "%choice%"=="y" (
            call setup.bat
        ) else (
            echo Please run setup.bat manually to create the configuration file before starting the service.
            exit /b 1
        )
    ) else (
        echo Error: Neither config.json nor config_example.json found. Cannot create configuration.
        exit /b 1
    )
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

exit /b %exit_code% 