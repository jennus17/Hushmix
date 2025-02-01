from PIL import Image, ImageDraw
from pathlib import Path
import os

class IconManager:
    @staticmethod
    def create_tray_icon():
        """Loads the volume icon from PNG file."""
        try:
            bundle_dir = Path(__file__).parent
            icon_path =  Path.cwd() / bundle_dir / "assets\\volume_icon.png"
            return Image.open(icon_path)
        except Exception as e:
            print(f"Error loading icon: {e}")
            # Fallback to creating a basic icon
            size = 64
            image = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle([size//3, size//3, size*2//3, size*2//3], fill="#2196F3")
            return image

    @staticmethod
    def create_ico_file():
        """Creates and saves a temporary .ico file for Windows compatibility."""
        try:
            # Load both icons
            bundle_dir = Path(__file__).parent
            icon_path = Path.cwd() / bundle_dir / "assets\\volume_icon.png"
            icon32_path = Path.cwd() / bundle_dir / "assets\\volume_icon32.png"
            
            icon_image = Image.open(icon_path)
            icon32_image = Image.open(icon32_path)
            
            # Save as ICO file
            ico_path = Path.cwd() / bundle_dir / "assets\\temp_icon.ico"
            
            # Create a list of sizes and their corresponding source images
            icon_sizes = [
                (16, 16, icon32_image),
                (20, 20, icon32_image),
                (24, 24, icon32_image),
                (32, 32, icon32_image),
                (40, 40, icon_image),
                (48, 48, icon_image),
                (64, 64, icon_image),
                (96, 96, icon_image),
                (128, 128, icon_image),
                (256, 256, icon_image)
            ]
            
            icon_images = []
            for width, height, source_image in icon_sizes:
                new_image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                
                if width <= 32:
                    resized = source_image.resize((width, height), Image.Resampling.NEAREST)
                else:
                    resized = source_image.resize((width, height), Image.Resampling.LANCZOS)
                
                paste_x = (width - resized.width) // 2
                paste_y = (height - resized.height) // 2
                new_image.paste(resized, (paste_x, paste_y), resized)
                
                icon_images.append(new_image)
            
            # Save with all sizes
            icon_images[0].save(
                ico_path,
                format='ICO',
                sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48),
                      (64, 64), (96, 96), (128, 128), (256, 256)]
            )
            return ico_path
        except Exception as e:
            print(f"Error creating ico file: {e}")
            return None 