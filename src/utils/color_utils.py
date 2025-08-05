import winreg


def get_windows_accent_color():
    """Retrieve the Windows accent color from the registry."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM"
        ) as key:
            accent_color = winreg.QueryValueEx(key, "ColorizationColor")[0]
            blue = accent_color & 0xFF
            green = (accent_color >> 8) & 0xFF
            red = (accent_color >> 16) & 0xFF
            return "#{:02x}{:02x}{:02x}".format(red, green, blue)
    except OSError as e:
        print(f"Error accessing registry: {e}")
    return "#2196F3"


def darken_color(hex_color, percentage):
    """Darken a hex color by a given percentage."""
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    r = int(r * (1 - percentage))
    g = int(g * (1 - percentage))
    b = int(b * (1 - percentage))

    return "#{:02x}{:02x}{:02x}".format(r, g, b) 