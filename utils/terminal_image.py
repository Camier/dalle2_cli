"""
Terminal image display utilities
Supports various methods for showing images in terminal
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import base64
from io import BytesIO

class TerminalImageViewer:
    """Display images in terminal using various methods"""
    
    @staticmethod
    def get_terminal_size() -> Tuple[int, int]:
        """Get terminal size in characters"""
        size = shutil.get_terminal_size((80, 24))
        return size.columns, size.lines
    
    @staticmethod
    def supports_sixel() -> bool:
        """Check if terminal supports sixel graphics"""
        term = os.environ.get('TERM', '')
        return 'xterm' in term or 'mlterm' in term
    
    @staticmethod
    def supports_iterm2() -> bool:
        """Check if running in iTerm2"""
        return os.environ.get('TERM_PROGRAM') == 'iTerm.app'
    
    @staticmethod
    def supports_kitty() -> bool:
        """Check if running in Kitty terminal"""
        return os.environ.get('TERM') == 'xterm-kitty'
    
    @staticmethod
    def ascii_art(image_path: Path, width: int = 80) -> str:
        """Convert image to ASCII art"""
        # ASCII characters from darkest to lightest
        ascii_chars = " .:-=+*#%@"
        
        try:
            # Open and resize image
            img = Image.open(image_path)
            
            # Calculate height to maintain aspect ratio
            aspect_ratio = img.height / img.width
            height = int(width * aspect_ratio * 0.5)  # Adjust for character aspect ratio
            
            img = img.resize((width, height))
            
            # Convert to grayscale
            img = img.convert('L')
            
            # Convert pixels to ASCII
            pixels = img.getdata()
            ascii_str = ""
            
            for i, pixel in enumerate(pixels):
                # Map pixel value (0-255) to ASCII character
                ascii_str += ascii_chars[pixel * len(ascii_chars) // 256]
                
                # Add newline at end of each row
                if (i + 1) % width == 0:
                    ascii_str += '\n'
            
            return ascii_str
            
        except Exception as e:
            return f"Error creating ASCII art: {e}"
    
    @staticmethod
    def block_art(image_path: Path, width: int = 40) -> str:
        """Convert image to colored block characters using ANSI colors"""
        try:
            img = Image.open(image_path)
            
            # Calculate height to maintain aspect ratio
            aspect_ratio = img.height / img.width
            height = int(width * aspect_ratio * 0.5)
            
            img = img.resize((width, height))
            img = img.convert('RGB')
            
            output = []
            pixels = list(img.getdata())
            
            for i in range(0, len(pixels), width):
                row = pixels[i:i + width]
                line = ""
                
                for r, g, b in row:
                    # Convert to ANSI 256 color
                    # Simplified conversion - could be improved
                    if r == g == b:
                        # Grayscale
                        gray = r
                        if gray < 8:
                            color = 16
                        elif gray > 248:
                            color = 231
                        else:
                            color = 232 + int((gray - 8) / 10)
                    else:
                        # Color cube
                        r6 = int(r * 5 / 255)
                        g6 = int(g * 5 / 255)
                        b6 = int(b * 5 / 255)
                        color = 16 + (36 * r6) + (6 * g6) + b6
                    
                    line += f"\033[48;5;{color}m  \033[0m"
                
                output.append(line)
            
            return '\n'.join(output)
            
        except Exception as e:
            return f"Error creating block art: {e}"
    
    @staticmethod
    def iterm2_inline(image_path: Path, width: Optional[int] = None, 
                     height: Optional[int] = None, preserve_aspect: bool = True) -> str:
        """Display image inline in iTerm2"""
        try:
            with open(image_path, 'rb') as f:
                img_data = f.read()
            
            b64_data = base64.b64encode(img_data).decode('ascii')
            
            # Build iTerm2 proprietary escape sequence
            esc = '\033]1337;File='
            
            args = [f'name={base64.b64encode(str(image_path).encode()).decode()}']
            
            if width:
                args.append(f'width={width}')
            if height:
                args.append(f'height={height}')
            if preserve_aspect:
                args.append('preserveAspectRatio=1')
            
            esc += ';'.join(args)
            esc += f':{b64_data}\a'
            
            return esc
            
        except Exception as e:
            return f"Error displaying image in iTerm2: {e}"
    
    @staticmethod
    def kitty_icat(image_path: Path) -> bool:
        """Display image using Kitty's icat"""
        try:
            subprocess.run(['kitty', '+kitten', 'icat', str(image_path)], 
                         check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    @staticmethod
    def sixel_graphics(image_path: Path, width: int = 400) -> str:
        """Convert image to sixel format"""
        # This is a placeholder - full sixel implementation is complex
        # In practice, you'd use a library like libsixel
        return "Sixel graphics not fully implemented"
    
    @classmethod
    def display_image(cls, image_path: Path, method: Optional[str] = None,
                     width: Optional[int] = None) -> bool:
        """Display image using best available method"""
        if not image_path.exists():
            print(f"Image not found: {image_path}")
            return False
        
        # Auto-detect best method if not specified
        if method is None:
            if cls.supports_iterm2():
                method = 'iterm2'
            elif cls.supports_kitty():
                method = 'kitty'
            else:
                method = 'block'  # Fallback to block art
        
        # Get terminal width if not specified
        if width is None:
            term_width, _ = cls.get_terminal_size()
            width = min(term_width - 2, 80)  # Leave some margin
        
        # Display using selected method
        if method == 'ascii':
            print(cls.ascii_art(image_path, width))
            return True
        
        elif method == 'block':
            print(cls.block_art(image_path, width // 2))  # Each block is 2 chars wide
            return True
        
        elif method == 'iterm2' and cls.supports_iterm2():
            print(cls.iterm2_inline(image_path, width))
            return True
        
        elif method == 'kitty' and cls.supports_kitty():
            return cls.kitty_icat(image_path)
        
        else:
            # Fallback to ASCII art
            print(cls.ascii_art(image_path, width))
            return True
    
    @classmethod
    def create_thumbnail_grid(cls, image_paths: list, columns: int = 3,
                            thumb_size: Tuple[int, int] = (200, 200)) -> Path:
        """Create a grid of thumbnails from multiple images"""
        if not image_paths:
            return None
        
        try:
            # Create thumbnails
            thumbnails = []
            for path in image_paths:
                if Path(path).exists():
                    img = Image.open(path)
                    img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                    thumbnails.append(img)
            
            if not thumbnails:
                return None
            
            # Calculate grid size
            rows = (len(thumbnails) + columns - 1) // columns
            
            # Create grid image
            grid_width = columns * thumb_size[0]
            grid_height = rows * thumb_size[1]
            grid = Image.new('RGB', (grid_width, grid_height), 'white')
            
            # Paste thumbnails
            for i, thumb in enumerate(thumbnails):
                row = i // columns
                col = i % columns
                
                # Center thumbnail in its cell
                x = col * thumb_size[0] + (thumb_size[0] - thumb.width) // 2
                y = row * thumb_size[1] + (thumb_size[1] - thumb.height) // 2
                
                grid.paste(thumb, (x, y))
            
            # Save grid
            grid_path = Path.home() / ".dalle_cli" / "temp_grid.png"
            grid_path.parent.mkdir(exist_ok=True)
            grid.save(grid_path)
            
            return grid_path
            
        except Exception as e:
            print(f"Error creating thumbnail grid: {e}")
            return None

class ImageInfo:
    """Extract and display image information"""
    
    @staticmethod
    def get_info(image_path: Path) -> dict:
        """Get image metadata"""
        try:
            img = Image.open(image_path)
            
            info = {
                "filename": image_path.name,
                "format": img.format,
                "mode": img.mode,
                "size": f"{img.width}x{img.height}",
                "file_size": f"{image_path.stat().st_size / 1024:.1f} KB"
            }
            
            # Extract EXIF data if available
            if hasattr(img, '_getexif') and img._getexif():
                exif = img._getexif()
                # Add relevant EXIF data
                # This is simplified - full EXIF parsing is more complex
                
            return info
            
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def format_info_table(info: dict) -> str:
        """Format image info as a nice table"""
        lines = ["Image Information:"]
        lines.append("-" * 30)
        
        for key, value in info.items():
            lines.append(f"{key.title():<15}: {value}")
        
        return '\n'.join(lines)