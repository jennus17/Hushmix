import customtkinter as ctk
from gui.app import HushmixApp


def main():
    root = ctk.CTk()  
    root.update_idletasks()

    window_width = root.winfo_width()
    window_height = root.winfo_height()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    position_x = int((screen_width - window_width) / 2.2)
    position_y = int((screen_height - window_height) / 2.7)

    root.geometry(f"+{position_x}+{position_y}")

    app = HushmixApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
