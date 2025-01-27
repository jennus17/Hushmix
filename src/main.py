import tkinter as tk
from gui.app import HusmixApp

def main():
    root = tk.Tk()
    app = HusmixApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()