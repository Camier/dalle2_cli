#!/usr/bin/env python3
"""
Quick fix for DALL-E generation
"""
import os
from openai import OpenAI
from pathlib import Path
from datetime import datetime

# Check for API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    # Try to load from saved preferences
    pref_file = Path.home() / ".dalle2_cli" / "preferences.json"
    if pref_file.exists():
        import json
        with open(pref_file) as f:
            prefs = json.load(f)
            api_key = prefs.get("api_key")

if not api_key:
    print("❌ No API key found!")
    print("Please set your OpenAI API key:")
    print("  export OPENAI_API_KEY='your-key-here'")
    print("Or run: ./dalle_cli_ultra.py setup")
    exit(1)

# Your prompt
prompt = "Don Quixote ON HIS HORSE IS A fluo STICKMAN AND HE CHARGES AT WINDMILLS MADE OF EVIL STICKS"

print(f"🎨 Generating: {prompt}")

try:
    client = OpenAI(api_key=api_key)
    
    # Generate with DALL-E 2 (no quality parameter)
    response = client.images.generate(
        model="dall-e-2",
        prompt=prompt,
        size="1024x1024",
        n=1
    )
    
    # Save image
    save_dir = Path.home() / ".dalle2_cli" / "images"
    save_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dalle_fix_{timestamp}.png"
    filepath = save_dir / filename
    
    # Download
    import requests
    img_data = requests.get(response.data[0].url).content
    with open(filepath, 'wb') as f:
        f.write(img_data)
    
    print(f"✅ Success! Image saved to: {filepath}")
    print(f"URL: {response.data[0].url}")
    
    # Try to open it
    if os.system(f"xdg-open {filepath} 2>/dev/null") != 0:
        print(f"\nTo view: xdg-open {filepath}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nPossible issues:")
    print("1. Check your API key is valid")
    print("2. Check your OpenAI account has credits")
    print("3. Try a simpler prompt first")