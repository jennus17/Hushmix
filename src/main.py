import customtkinter as ctk
from gui.app import HushmixApp

def main():
    root = ctk.CTk()
    app = HushmixApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()