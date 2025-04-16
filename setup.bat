@echo off
echo === DeepSeek-X Setup ===
echo Initializing configuration...

if exist config.json (
    echo Configuration file already exists.
) else (
    if exist config_example.json (
        echo Creating config.json from config_example.json template
        copy config_example.json config.json
        echo Configuration file created. Please edit config.json to configure your API keys.
    ) else (
        echo Error: config_example.json not found. Cannot create configuration file.
        exit /b 1
    )
)

echo Setup complete.
echo Please verify and update your API keys in config.json before running the service.
echo You can start the service by running: run.bat 