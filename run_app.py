#!/usr/bin/env python3
"""
DALL-E 2 API GUI Application Runner
This script runs the application with proper imports
"""
import subprocess
import sys
import os

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)

# Use the virtual environment Python if available
venv_python = os.path.join(script_dir, 'venv', 'bin', 'python')
if os.path.exists(venv_python):
    python_exe = venv_python
else:
    python_exe = sys.executable

# Run the application
print("Starting DALL-E 2 API GUI Application...")
print("You will need to enter your OpenAI API key on first run.")

# Change to parent directory and run as module
os.chdir(parent_dir)
subprocess.run([python_exe, '-m', 'dalle2_app.gui.main_window'])
