import tkinter as tk
from gui.app import HushmixApp

def main():
    root = tk.Tk()
    app = HushmixApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()