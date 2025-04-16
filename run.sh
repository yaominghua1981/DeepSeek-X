#!/bin/bash

echo "=== Starting DeepSeek-X Service ==="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Please run ./setup.sh to install dependencies first."
    exit 1
fi

# Check if config file exists
if [ ! -f "config.json" ]; then
    if [ -f "config_example.json" ]; then
        echo "config.json file not found, but config_example.json exists."
        echo "Would you like to run setup.sh to create the configuration file now? (y/n)"
        read -r choice
        if [[ "$choice" =~ ^[Yy]$ ]]; then
            ./setup.sh
        else
            echo "Please run setup.sh manually to create the configuration file before starting the service."
            exit 1
        fi
    else
        echo "Error: Neither config.json nor config_example.json found. Cannot create configuration."
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Start service
echo "Starting DeepSeek-X service..."
uvicorn main:app --host 127.0.0.1 --port 8000

# Capture exit code
exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "Service exited abnormally, exit code: $exit_code"
else
    echo "Service stopped normally"
fi

exit $exit_code 