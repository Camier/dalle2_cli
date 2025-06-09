#!/usr/bin/env python3
"""
DALL-E 2 API GUI Application
Main entry point when running as a module
"""
from dalle2_app.gui.main_window import main

if __name__ == "__main__":
    print("Starting DALL-E 2 API GUI Application...")
    print("You will need to enter your OpenAI API key on first run.")
    main()
