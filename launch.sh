#!/bin/bash
# DALL-E 2 App Launcher

# Get the directory of this script
DIR=""

# Activate virtual environment if it exists
if [ -d "/venv" ]; then
    source "/venv/bin/activate"
fi

# Run from parent directory to make imports work
cd "/.."
python -m dalle2_app.gui.main_window ""
