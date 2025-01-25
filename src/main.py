import tkinter as tk
from gui.app import VolumeControlApp

def main():
    root = tk.Tk()
    app = VolumeControlApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()