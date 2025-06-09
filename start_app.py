#!/usr/bin/env python3
"""
DALL-E 2 API GUI Application Launcher
This script properly sets up the package structure for running the app
"""
import sys
import os

# Run the main_window module as a script
if __name__ == "__main__":
    print("Starting DALL-E 2 API GUI Application...")
    print("You will need to enter your OpenAI API key on first run.")
    
    # Run the module using Python's -m flag
    os.system(f"{sys.executable} -m dalle2_app.gui.main_window")
