#!/usr/bin/env python3
"""
DALL-E 2 API GUI Application
Run this script to start the application
"""
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Change to project directory
os.chdir(project_root)

# Now we can import and run the main application
if __name__ == "__main__":
    print("Starting DALL-E 2 API GUI Application...")
    print("You will need to enter your OpenAI API key on first run.")
    
    # Import here after path is set
    from gui.main_window import main
    main()
