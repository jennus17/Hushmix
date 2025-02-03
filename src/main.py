import customtkinter as ctk
from gui.app import HushmixApp
import ctypes
def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception as e:
        print(f"Error setting DPI awareness: {e}")

    root = ctk.CTk()
    app = HushmixApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()