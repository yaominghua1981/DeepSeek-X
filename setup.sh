#!/bin/bash

echo "=== DeepSeek-X Setup ==="
echo "Initializing configuration..."

if [ -f "config.json" ]; then
    echo "Configuration file already exists."
else
    if [ -f "config_example.json" ]; then
        echo "Creating config.json from config_example.json template"
        cp config_example.json config.json
        echo "Configuration file created. Please edit config.json to configure your API keys."
    else
        echo "Error: config_example.json not found. Cannot create configuration file."
        exit 1
    fi
fi

echo "Setup complete."
echo "Please verify and update your API keys in config.json before running the service."
echo "You can start the service by running: ./run.sh" 