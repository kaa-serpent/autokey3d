"""
AddSystem — form to add a new lock system definition.
"""

import re
import tkinter as tk
from tkinter import messagebox, ttk

import autokey_core


class AddSystem(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build_ui()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Header
        header = tk.Frame(self, pady=6, padx=10)
        header.pack(fill=tk.X)
        ttk.Button(header, text="← Back", command=self.app.navigate_back).pack(side=tk.LEFT)
        tk.Label(header, text="Add New System", font=("TkDefaultFont", 13, "bold")).pack(
            side=tk.LEFT, padx=10
        )

        ttk.Separator(self, orient="horizontal").pack(fill=tk.X)

        # Form
        form = tk.Frame(self, padx=20, pady=14)
        form.pack(fill=tk.BOTH, expand=True)

        self._fields = {}

        def row(label, key, default="", note=""):
            f = tk.Frame(form, pady=3)
            f.pack(fill=tk.X)
            display = label + ("  (%s)" % note if note else "")
            tk.Label(f, text=display, width=40, anchor="w").pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            ttk.Entry(f, textvariable=var, width=18).pack(side=tk.LEFT)
            self._fields[key] = var

        row("System name (e.g. MY-LOCK1)", "name")
        row("Key length — kl (mm)", "kl")
        row("Shoulder to first pin — aspace (mm)", "aspace")
        row("Pin spacing — pinspace (mm)", "pinspace")
        row("Highest cut offset — hcut_offset", "hcut_offset",
            note="constant in: hcut = ph - 2*tol - <this>")
        row("Cut level spacing — cutspace (mm)", "cutspace")
        row("V-cut angle — cutangle (degrees)", "cutangle")
        row("Plateau width — platspace (mm)", "platspace")

        ttk.Button(form, text="Save System", command=self._on_save).pack(pady=10, anchor="w")

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self, **kwargs):
        for var in self._fields.values():
            var.set("")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self):
        name = self._fields["name"].get().strip()

        if not re.match(r'^[A-Za-z0-9_\-]+$', name):
            messagebox.showerror("Validation", "Name must contain only letters, digits, - or _.")
            return

        float_fields = {
            "kl": "Key length",
            "aspace": "Shoulder (aspace)",
            "pinspace": "Pin spacing",
            "hcut_offset": "Highest cut offset",
            "cutspace": "Cut spacing",
            "cutangle": "Cut angle",
            "platspace": "Plateau width",
        }
        values = {}
        for key, label in float_fields.items():
            s = self._fields[key].get().strip()
            try:
                values[key] = float(s)
            except ValueError:
                messagebox.showerror("Validation", "%s must be a number." % label)
                return

        # Write .scad
        autokey_core.write_system_scad(
            self.app.base_dir,
            name,
            kl=values["kl"],
            aspace=values["aspace"],
            pinspace=values["pinspace"],
            hcut_offset=values["hcut_offset"],
            cutspace=values["cutspace"],
            cutangle=values["cutangle"],
            platspace=values["platspace"],
        )

        # Add to index
        entry = {
            "name": name,
            "scad_path": "definitions/%s.scad" % name,
            "kl": values["kl"],
            "aspace": values["aspace"],
            "pinspace": values["pinspace"],
            "hcut_offset": values["hcut_offset"],
            "cutspace": values["cutspace"],
            "cutangle": values["cutangle"],
            "platspace": values["platspace"],
        }
        self.app.profile_index.add_system(entry)

        messagebox.showinfo("Saved", "System '%s' saved successfully." % name)
        self.app.show_screen("home")
