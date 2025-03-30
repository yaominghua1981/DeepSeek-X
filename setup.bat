@echo off
echo === DeepSeek-X Installation Script ===
echo Setting up development environment...

REM Check Python version
python -c "import sys; print('Python %s.%s' % (sys.version_info[0], sys.version_info[1]))" > tmp.txt
set /p python_version=<tmp.txt
del tmp.txt

echo Detected %python_version%

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

REM Create config file (if it doesn't exist)
if not exist config.json (
    if exist config.example.json (
        echo Creating configuration file...
        copy config.example.json config.json
        echo Please edit config.json file to set your API keys and other configuration options
    )
)

echo Installation complete!
echo Use the following command to run the application:
echo   run.bat

pause 