from PIL import Image, ImageDraw
from pathlib import Path
import os

class IconManager:
    @staticmethod
    def get_ico_file():
        """Creates and saves a temporary .ico file for Windows compatibility."""
        try:
            # Load both icons
            bundle_dir = Path(__file__).parent
            icon_path = Path.cwd() / bundle_dir / "assets\\volume_icon32.ico"
            return icon_path
        
        except Exception as e:
            print(f"Error getting ico file: {e}")
            size = 64
            image = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle([size//3, size//3, size*2//3, size*2//3], fill="#2196F3")
            return image