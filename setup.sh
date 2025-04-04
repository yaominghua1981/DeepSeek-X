#!/bin/bash

echo "=== DeepSeek-X Installation Script ==="
echo "Setting up development environment..."

# Check Python version
python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python 3.8 or higher is required, current version: $python_version"
    exit 1
fi

echo "Python version check passed: $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install core dependencies
echo "Installing core dependencies..."
pip install fastapi uvicorn pydantic httpx python-dotenv aiohttp sse-starlette

# If pyproject.toml exists, use pip to install dependencies
if [ -f "pyproject.toml" ]; then
    echo "Detected pyproject.toml, installing project dependencies with pip..."
    pip install -e .
fi

# Create config file (if it doesn't exist)
if [ ! -f "config.json" ] && [ -f "config.example.json" ]; then
    echo "Creating configuration file..."
    cp config.example.json config.json
    echo "Please edit config.json file to set your API keys and other configuration options"
fi

echo "Installation complete!"
echo "Use the following commands to activate the environment and run the application:"
echo "  source venv/bin/activate"
echo "  ./run.sh" 