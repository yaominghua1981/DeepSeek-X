#!/bin/bash

echo "=== Starting DeepSeek-X Service ==="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found. Please run ./setup.sh to install dependencies first."
    exit 1
fi

# Check if config file exists
if [ ! -f "config.json" ]; then
    echo "Error: config.json file not found. Please run setup.sh or create the configuration file manually."
    exit 1
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