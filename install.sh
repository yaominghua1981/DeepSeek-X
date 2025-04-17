#!/bin/bash

echo "=== DeepSeek-X Installation Script ==="
echo "Setting up development environment..."

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if [ $? -ne 0 ]; then
    echo "Error: Python is not available. Please install Python 3.11 or higher."
    exit 1
fi

# Check if Python version is 3.11 or higher
if [[ "$(printf '%s\n' "3.11" "$python_version" | sort -V | head -n1)" != "3.11" ]]; then
    echo "Error: Python 3.11 or higher is required, current version: $python_version"
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

# Create config file
echo "Setting up configuration..."
./setup.sh

echo "Installation complete!"
echo "Use the following commands to activate the environment and run the application:"
echo "  source venv/bin/activate"
echo "  ./run.sh" 