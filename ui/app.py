"""
App — root Tk window with frame-stack navigation.

Usage:
    from ui.app import App
    import tkinter as tk
    root = tk.Tk()
    app = App(root, base_dir)
    root.mainloop()
"""

import tkinter as tk
from tkinter import ttk

from ui.profile_index import ProfileIndex


class App(tk.Frame):
    def __init__(self, root, base_dir):
        super().__init__(root)
        self.root = root
        self.base_dir = base_dir

        self.profile_index = ProfileIndex(base_dir)
        self.profile_index.load()

        self.pack(fill=tk.BOTH, expand=True)
        self._build_menu()
        self._build_frames()
        self.show_screen("home")

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Add New Profile", command=lambda: self.show_screen("add_profile"))
        file_menu.add_command(label="Add New System", command=lambda: self.show_screen("add_system"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    # ------------------------------------------------------------------
    # Frames
    # ------------------------------------------------------------------

    def _build_frames(self):
        # Lazy import to avoid circular dependencies
        from ui.home_screen import HomeScreen
        from ui.profile_detail import ProfileDetail
        from ui.add_profile import AddProfile
        from ui.add_system import AddSystem

        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self._frames = {}
        for ScreenClass, name in [
            (HomeScreen,    "home"),
            (ProfileDetail, "detail"),
            (AddProfile,    "add_profile"),
            (AddSystem,     "add_system"),
        ]:
            frame = ScreenClass(container, self)
            frame.grid(row=0, column=0, sticky="nsew")
            self._frames[name] = frame

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_screen(self, name, **kwargs):
        frame = self._frames[name]
        frame.refresh(**kwargs)
        frame.tkraise()

    def navigate_back(self):
        self.show_screen("home")
