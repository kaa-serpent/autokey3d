"""
ProfileDetail — shows profile metadata and lets the user generate a key.
"""

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ui import svg_renderer

SVG_W = 160
SVG_H = 110


class ProfileDetail(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._profile = None
        self._photo_ref = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self):
        # --- Header ---
        header = tk.Frame(self, pady=6, padx=10)
        header.pack(fill=tk.X)
        ttk.Button(header, text="← Back", command=self.app.navigate_back).pack(side=tk.LEFT)
        self._title_label = tk.Label(
            header, text="", font=("TkDefaultFont", 13, "bold")
        )
        self._title_label.pack(side=tk.LEFT, padx=10)

        ttk.Separator(self, orient="horizontal").pack(fill=tk.X)

        # --- Body ---
        body = tk.Frame(self, padx=14, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        # Left column: SVG preview
        left = tk.Frame(body)
        left.pack(side=tk.LEFT, anchor="n", padx=(0, 16))
        self._img_label = tk.Label(left, bg="white", relief=tk.SUNKEN, width=SVG_W, height=SVG_H)
        self._img_label.pack()

        # Right column: metadata + controls
        right = tk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor="n")

        # Metadata frame
        meta = ttk.LabelFrame(right, text="Profile info", padding=8)
        meta.pack(fill=tk.X)
        self._meta_labels = {}
        for field in ("Tolerance (tol)", "Height base (ph)", "Handle X (khcx)",
                      "Handle Z (khcz)", "Thin handle", "Match handle"):
            row = tk.Frame(meta)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=field + ":", width=20, anchor="w").pack(side=tk.LEFT)
            lbl = tk.Label(row, text="", anchor="w")
            lbl.pack(side=tk.LEFT)
            self._meta_labels[field] = lbl

        # System selection
        sys_frame = tk.Frame(right, pady=8)
        sys_frame.pack(fill=tk.X)
        tk.Label(sys_frame, text="System definition:").pack(side=tk.LEFT)
        self._system_var = tk.StringVar()
        self._system_combo = ttk.Combobox(
            sys_frame, textvariable=self._system_var, state="readonly", width=28
        )
        self._system_combo.pack(side=tk.LEFT, padx=6)
        self._set_default_btn = ttk.Button(
            sys_frame, text="Set as default", command=self._on_set_default
        )
        self._set_default_btn.pack(side=tk.LEFT)

        # Mode selection
        mode_frame = ttk.LabelFrame(right, text="Mode", padding=8)
        mode_frame.pack(fill=tk.X, pady=(4, 0))
        self._mode_var = tk.StringVar(value="blank")
        for label, val in [("Key blank", "blank"), ("Bump key", "bumpkey"), ("Key combination", "key")]:
            rb = ttk.Radiobutton(
                mode_frame, text=label, variable=self._mode_var,
                value=val, command=self._on_mode_change
            )
            rb.pack(side=tk.LEFT, padx=8)

        # Combination entry
        combo_frame = tk.Frame(right, pady=4)
        combo_frame.pack(fill=tk.X)
        tk.Label(combo_frame, text="Combination (e.g. 1,2,3,4,5):").pack(side=tk.LEFT)
        self._combo_var = tk.StringVar()
        self._combo_entry = ttk.Entry(combo_frame, textvariable=self._combo_var, width=20)
        self._combo_entry.pack(side=tk.LEFT, padx=6)
        self._combo_entry.config(state="disabled")

        # Tolerance override
        tol_frame = tk.Frame(right, pady=2)
        tol_frame.pack(fill=tk.X)
        tk.Label(tol_frame, text="Tolerance override (leave blank to use profile default):").pack(side=tk.LEFT)
        self._tol_var = tk.StringVar()
        ttk.Entry(tol_frame, textvariable=self._tol_var, width=8).pack(side=tk.LEFT, padx=6)

        # Generate button + progress
        gen_frame = tk.Frame(right, pady=10)
        gen_frame.pack(fill=tk.X)
        self._gen_button = ttk.Button(gen_frame, text="Generate Key", command=self._on_generate)
        self._gen_button.pack(side=tk.LEFT)
        self._progress = ttk.Progressbar(gen_frame, mode="indeterminate", length=140)
        self._progress.pack(side=tk.LEFT, padx=10)
        self._progress.pack_forget()  # hidden initially

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self, profile=None, **kwargs):
        if profile is None:
            return
        self._profile = profile
        self._title_label.config(text=profile["name"])

        # SVG preview
        svg_path = os.path.join(self.app.base_dir, profile["svg_path"])
        photo = svg_renderer.render(svg_path, SVG_W, SVG_H) if os.path.exists(svg_path) else None
        if photo:
            self._photo_ref = photo
            self._img_label.config(image=photo, width=SVG_W, height=SVG_H)
        else:
            self._photo_ref = None
            self._img_label.config(image="", text="[SVG]", width=SVG_W, height=SVG_H)

        # Metadata
        self._meta_labels["Tolerance (tol)"].config(text=str(profile.get("tol", "")))
        ph = profile.get("ph_base", "")
        if profile.get("ph_has_tol"):
            ph = "%s + 2×tol" % ph
        self._meta_labels["Height base (ph)"].config(text=str(ph))
        self._meta_labels["Handle X (khcx)"].config(
            text=str(profile["khcx"]) if profile.get("khcx") is not None else "—"
        )
        self._meta_labels["Handle Z (khcz)"].config(
            text=str(profile["khcz"]) if profile.get("khcz") is not None else "—"
        )
        self._meta_labels["Thin handle"].config(
            text="yes" if profile.get("thin_handle") else "no"
        )
        self._meta_labels["Match handle"].config(
            text="yes" if profile.get("match_handle") else "no"
        )

        # System dropdown
        systems = self.app.profile_index.systems
        names = [s["name"] for s in systems]
        self._system_combo["values"] = names
        # Pre-select: use stored default_system, fall back to brand prefix match
        stored_default = profile.get("default_system")
        if stored_default and stored_default in names:
            preselect = stored_default
        else:
            prefix = profile["name"].split("-")[0] + "-" if "-" in profile["name"] else ""
            preselect = next((n for n in names if n.startswith(prefix)), names[0] if names else "")
        self._system_var.set(preselect)

        # Reset mode + tol override
        self._mode_var.set("blank")
        self._combo_entry.config(state="disabled")
        self._combo_var.set("")
        self._tol_var.set("")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_set_default(self):
        system_name = self._system_var.get()
        if not system_name or not self._profile:
            return
        self.app.profile_index.set_profile_default_system(self._profile["name"], system_name)
        self._profile["default_system"] = system_name
        messagebox.showinfo("Saved", "'%s' set as default system for %s." % (system_name, self._profile["name"]))

    def _on_mode_change(self):
        if self._mode_var.get() == "key":
            self._combo_entry.config(state="normal")
        else:
            self._combo_entry.config(state="disabled")

    def _on_generate(self):
        import autokey_core

        profile = self._profile
        if not profile:
            return

        system_name = self._system_var.get()
        if not system_name:
            messagebox.showerror("Error", "Please select a system definition.")
            return

        system = next((s for s in self.app.profile_index.systems if s["name"] == system_name), None)
        if not system:
            messagebox.showerror("Error", "System not found.")
            return

        mode = self._mode_var.get()
        combination = self._combo_var.get().strip() if mode == "key" else None
        if mode == "key" and not combination:
            messagebox.showerror("Error", "Please enter a key combination (e.g. 1,2,3,4,5).")
            return

        tol_str = self._tol_var.get().strip()
        tol_override = None
        if tol_str:
            try:
                tol_override = float(tol_str)
            except ValueError:
                messagebox.showerror("Error", "Tolerance must be a number.")
                return

        profile_svg = os.path.join(self.app.base_dir, profile["svg_path"])
        definition_path = os.path.join(self.app.base_dir, system["scad_path"])

        thin_handle = bool(profile.get("thin_handle"))
        match_handle = bool(profile.get("match_handle"))

        self._gen_button.config(state="disabled")
        self._progress.pack(side=tk.LEFT, padx=10)
        self._progress.start(10)

        def _run():
            try:
                autokey_core.generate_key(
                    profile_svg_path=profile_svg,
                    definition_path=definition_path,
                    mode=mode,
                    combination=combination,
                    tol_override=tol_override,
                    thin_handle=thin_handle,
                    match_handle_connector=match_handle,
                )
                self.app.root.after(0, self._on_done)
            except Exception as exc:
                self.app.root.after(0, self._on_error, str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _on_done(self):
        self._progress.stop()
        self._progress.pack_forget()
        self._gen_button.config(state="normal")
        messagebox.showinfo("OpenSCAD launched", "The key model is open in OpenSCAD.")

    def _on_error(self, msg):
        self._progress.stop()
        self._progress.pack_forget()
        self._gen_button.config(state="normal")
        messagebox.showerror("Generation failed", msg)
