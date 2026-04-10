"""
AddProfile — form to add a new keyway profile.
"""

import os
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import autokey_core


class AddProfile(tk.Frame):
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
        tk.Label(header, text="Add New Profile", font=("TkDefaultFont", 13, "bold")).pack(
            side=tk.LEFT, padx=10
        )

        ttk.Separator(self, orient="horizontal").pack(fill=tk.X)

        # Form
        form = tk.Frame(self, padx=20, pady=14)
        form.pack(fill=tk.BOTH, expand=True)

        self._fields = {}

        def row(label, key, default="", optional=False):
            f = tk.Frame(form, pady=3)
            f.pack(fill=tk.X)
            lbl_text = label + ("  (optional)" if optional else "")
            tk.Label(f, text=lbl_text, width=32, anchor="w").pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            ttk.Entry(f, textvariable=var, width=28).pack(side=tk.LEFT)
            self._fields[key] = var

        row("Profile name (e.g. MY-LOCK1)", "name")
        self._build_svg_row(form)
        row("Tolerance (tol)", "tol", "0.0")
        row("Height base (ph_base) — before tol", "ph_base")
        row("Handle connector X (khcx)", "khcx", optional=True)
        row("Handle connector Z (khcz)", "khcz", optional=True)

        # Checkboxes
        chk_frame = tk.Frame(form, pady=6)
        chk_frame.pack(fill=tk.X)
        self._thin_handle_var = tk.BooleanVar()
        self._match_handle_var = tk.BooleanVar()
        ttk.Checkbutton(chk_frame, text="Thin handle", variable=self._thin_handle_var).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(chk_frame, text="Match handle connector", variable=self._match_handle_var).pack(side=tk.LEFT, padx=12)

        # Default system
        sys_row = tk.Frame(form, pady=3)
        sys_row.pack(fill=tk.X)
        tk.Label(sys_row, text="Default system  (optional)", width=32, anchor="w").pack(side=tk.LEFT)
        self._default_system_var = tk.StringVar()
        self._default_system_combo = ttk.Combobox(
            sys_row, textvariable=self._default_system_var, state="readonly", width=28
        )
        self._default_system_combo.pack(side=tk.LEFT)

        # Save button
        ttk.Button(form, text="Save Profile", command=self._on_save).pack(pady=10, anchor="w")

    def _build_svg_row(self, parent):
        f = tk.Frame(parent, pady=3)
        f.pack(fill=tk.X)
        tk.Label(f, text="SVG file", width=32, anchor="w").pack(side=tk.LEFT)
        self._svg_var = tk.StringVar()
        ttk.Entry(f, textvariable=self._svg_var, width=28).pack(side=tk.LEFT)
        ttk.Button(f, text="Browse…", command=self._browse_svg).pack(side=tk.LEFT, padx=6)

    def _browse_svg(self):
        path = filedialog.askopenfilename(
            title="Select profile SVG",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")],
        )
        if path:
            self._svg_var.set(path)

    # ------------------------------------------------------------------
    # Refresh (called on each visit — clear the form)
    # ------------------------------------------------------------------

    def refresh(self, **kwargs):
        for var in self._fields.values():
            var.set("")
        self._fields["tol"].set("0.0")
        self._svg_var.set("")
        self._thin_handle_var.set(False)
        self._match_handle_var.set(False)
        system_names = [""] + [s["name"] for s in self.app.profile_index.systems]
        self._default_system_combo["values"] = system_names
        self._default_system_var.set("")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self):
        name = self._fields["name"].get().strip()
        svg_src = self._svg_var.get().strip()
        tol_str = self._fields["tol"].get().strip()
        ph_str = self._fields["ph_base"].get().strip()
        khcx_str = self._fields["khcx"].get().strip()
        khcz_str = self._fields["khcz"].get().strip()

        # Validate
        if not re.match(r'^[A-Za-z0-9_\-]+$', name):
            messagebox.showerror("Validation", "Name must contain only letters, digits, - or _.")
            return
        if not svg_src or not os.path.exists(svg_src):
            messagebox.showerror("Validation", "Please select a valid SVG file.")
            return
        try:
            tol = float(tol_str)
        except ValueError:
            messagebox.showerror("Validation", "Tolerance must be a number (e.g. 0.0 or 0.2).")
            return
        try:
            ph_base = float(ph_str)
        except ValueError:
            messagebox.showerror("Validation", "Height base (ph_base) must be a number.")
            return

        khcx = None
        if khcx_str:
            try:
                khcx = float(khcx_str)
            except ValueError:
                messagebox.showerror("Validation", "Handle X must be a number.")
                return

        khcz = None
        if khcz_str:
            try:
                khcz = float(khcz_str)
            except ValueError:
                messagebox.showerror("Validation", "Handle Z must be a number.")
                return

        thin_handle = self._thin_handle_var.get()
        match_handle = self._match_handle_var.get()

        # Copy SVG if not already in profiles/
        dest_svg = os.path.join(self.app.base_dir, "profiles", "%s.svg" % name)
        if os.path.abspath(svg_src) != os.path.abspath(dest_svg):
            shutil.copy2(svg_src, dest_svg)

        # Generate DXF alongside the SVG
        dest_dxf = os.path.join(self.app.base_dir, "profiles", "%s.dxf" % name)
        try:
            autokey_core.svg_to_dxf(dest_svg, dest_dxf)
        except Exception as exc:
            messagebox.showwarning(
                "DXF conversion",
                "Could not generate DXF (Inkscape may not be on PATH).\n"
                "The profile was saved; DXF will be generated on first key generation.\n\n"
                "Details: %s" % exc,
            )

        # Write .scad
        autokey_core.write_profile_scad(
            self.app.base_dir, name, tol, ph_base,
            khcx=khcx, khcz=khcz,
            thin_handle=thin_handle, match_handle=match_handle,
        )

        default_system = self._default_system_var.get().strip() or None

        # Add to index
        entry = {
            "name": name,
            "svg_path": "profiles/%s.svg" % name,
            "scad_path": "profiles/%s.scad" % name,
            "dxf_path": "profiles/%s.dxf" % name,
            "tol": tol,
            "ph_base": ph_base,
            "ph_has_tol": True,
            "khcx": khcx,
            "khcz": khcz,
            "thin_handle": thin_handle,
            "match_handle": match_handle,
            "default_system": default_system,
        }
        self.app.profile_index.add_profile(entry)

        messagebox.showinfo("Saved", "Profile '%s' saved successfully." % name)
        self.app.show_screen("home")
