#!/usr/bin/env python3
"""
Auto-collect addon for DALL-E CLI
Add this to any generation function to automatically copy to ALL_IMAGES
"""
import shutil
from pathlib import Path
from datetime import datetime

def auto_collect_images(image_files, source_folder_name=""):
    """Automatically copy generated images to ALL_IMAGES folder"""
    permanent_dir = Path.home() / ".dalle2_cli" / "ALL_IMAGES"
    permanent_dir.mkdir(parents=True, exist_ok=True)
    
    collected = []
    
    for img_path in image_files:
        try:
            # Create descriptive filename
            if source_folder_name:
                new_name = f"{source_folder_name}_{img_path.name}"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = f"img_{timestamp}_{img_path.name}"
            
            dest_path = permanent_dir / new_name
            
            # Handle duplicates
            if dest_path.exists():
                base = dest_path.stem
                ext = dest_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = permanent_dir / f"{base}_{counter}{ext}"
                    counter += 1
            
            shutil.copy2(img_path, dest_path)
            collected.append(dest_path)
            
        except Exception as e:
            print(f"Error collecting {img_path}: {e}")
    
    return collected

# Quick access functions
def open_all_images_folder():
    """Open the ALL_IMAGES folder"""
    permanent_dir = Path.home() / ".dalle2_cli" / "ALL_IMAGES"
    if permanent_dir.exists():
        import os
        os.system(f"xdg-open '{permanent_dir}' 2>/dev/null || open '{permanent_dir}' 2>/dev/null || explorer.exe '{permanent_dir}' 2>/dev/null")
        return True
    return False

def get_all_images_count():
    """Get count of all collected images"""
    permanent_dir = Path.home() / ".dalle2_cli" / "ALL_IMAGES"
    if permanent_dir.exists():
        return len(list(permanent_dir.glob("*.png")) + list(permanent_dir.glob("*.jpg")))
    return 0
