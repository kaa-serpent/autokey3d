"""
HomeScreen — profile browser with search filter and SVG card grid.
"""

import os
import tkinter as tk
from tkinter import ttk

from ui import svg_renderer

CARD_WIDTH = 150
CARD_HEIGHT = 140
SVG_W = 120
SVG_H = 80
COLS = 3
PAD = 10


class HomeScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._all_profiles = []
        self._photo_refs = []  # keep refs to prevent GC
        self._build_ui()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Header
        header = tk.Frame(self, pady=6, padx=10)
        header.pack(fill=tk.X)
        tk.Label(header, text="AutoKey3D", font=("TkDefaultFont", 14, "bold")).pack(side=tk.LEFT)

        # Search bar
        search_frame = tk.Frame(self, padx=10, pady=4)
        search_frame.pack(fill=tk.X)
        tk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter())
        ttk.Entry(search_frame, textvariable=self._search_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0)
        )

        # Scrollable canvas for card grid
        outer = tk.Frame(self)
        outer.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(outer, borderwidth=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._grid_frame = tk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._grid_frame, anchor="nw"
        )

        self._grid_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        # Mouse wheel scrolling
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_frame_configure(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event=None):
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Refresh / filter
    # ------------------------------------------------------------------

    def refresh(self, **kwargs):
        self._all_profiles = list(self.app.profile_index.profiles)
        self._search_var.set("")
        self._render_grid(self._all_profiles)

    def _filter(self):
        query = self._search_var.get().lower()
        if query:
            filtered = [p for p in self._all_profiles if query in p["name"].lower()]
        else:
            filtered = self._all_profiles
        self._render_grid(filtered)

    # ------------------------------------------------------------------
    # Grid rendering
    # ------------------------------------------------------------------

    def _render_grid(self, profiles):
        # Destroy existing cards
        for widget in self._grid_frame.winfo_children():
            widget.destroy()
        self._photo_refs = []

        for i in range(COLS):
            self._grid_frame.columnconfigure(i, weight=1, minsize=CARD_WIDTH + PAD)

        for idx, profile in enumerate(profiles):
            row, col = divmod(idx, COLS)
            card = self._make_card(self._grid_frame, profile)
            card.grid(row=row, column=col, padx=PAD, pady=PAD, sticky="n")

    def _make_card(self, parent, profile):
        card = tk.Frame(
            parent,
            relief=tk.RAISED,
            borderwidth=1,
            cursor="hand2",
            width=CARD_WIDTH,
            height=CARD_HEIGHT,
        )
        card.pack_propagate(False)

        # SVG preview
        svg_path = os.path.join(self.app.base_dir, profile["svg_path"])
        photo = svg_renderer.render(svg_path, SVG_W, SVG_H) if os.path.exists(svg_path) else None

        if photo:
            self._photo_refs.append(photo)
            img_label = tk.Label(card, image=photo, bg="white")
        else:
            img_label = tk.Label(
                card, text="[SVG]", width=12, height=4,
                bg="#e8e8e8", fg="#888888", font=("TkDefaultFont", 9)
            )
        img_label.pack(pady=(8, 4))

        name_label = tk.Label(
            card, text=profile["name"],
            font=("TkDefaultFont", 9, "bold"),
            wraplength=CARD_WIDTH - 10,
        )
        name_label.pack()

        # Bind click on all sub-widgets
        def on_click(event, p=profile):
            self.app.show_screen("detail", profile=p)

        for widget in (card, img_label, name_label):
            widget.bind("<Button-1>", on_click)

        return card
