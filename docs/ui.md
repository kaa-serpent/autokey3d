# UI Reference

The Tkinter UI is launched via `autokey_ui.py`. All UI code lives in `ui/`.

---

## App Startup

`autokey_ui.py` creates an 880×600 px `Tk` root (minimum 700×520), instantiates `App`, and calls `mainloop()`.

`App.__init__()` (`ui/app.py`):
1. Loads `ProfileIndex` from `profiles.json` (rebuilds from disk on first run).
2. Instantiates all four screens once and stacks them as frames.
3. Adds a **File** menu: Add New Profile, Add New System, Exit.
4. Shows `HomeScreen` initially.

---

## Frame-Stack Navigation

All screens are instantiated once at startup and stacked on top of each other. Navigation raises a frame to the top without destroying and recreating it.

```python
app.show_screen("detail", profile=entry)   # navigate to a screen
app.navigate_back()                         # always returns to HomeScreen
```

`show_screen(name, **kwargs)` calls `frame.refresh(**kwargs)` before raising the frame, so the screen re-reads fresh data every time it is shown.

**Screen names:** `"home"`, `"detail"`, `"add_profile"`, `"add_system"`

---

## Screens

### HomeScreen (`ui/home_screen.py`)

Displays all profiles as a scrollable card grid.

- **Search bar** — live filter (case-insensitive match on name) as the user types.
- **Card grid** — 3 columns, 150×140 px cards; each shows a 120×80 px SVG thumbnail and the profile name.
- **Click a card** → navigate to `ProfileDetail` with that profile.
- Mouse wheel scrolling supported.
- `refresh()` reloads the profile list and redraws the grid.

### ProfileDetail (`ui/profile_detail.py`)

Shows metadata for the selected profile and triggers key generation.

**Left panel:**
- SVG preview (160×110 px).

**Right panel:**
- Profile info: `tol`, `ph_base` (with `± 2×tol` note if applicable), `khcx`, `khcz`, thin/match handle flags.
- **System dropdown** — lists all known systems; remembers the profile's `default_system`.
  - Smart pre-selection order: stored default → brand-prefix match → first in list.
  - **Set as default** button persists the choice to `profiles.json`.
- **Mode radio buttons:** Key blank / Bump key / Key combination.
- **Combination entry** — enabled only in Key combination mode; example placeholder `"1,2,3,4,5"`.
- **Tolerance override** — optional float; leave blank to use the profile's own `tol`.
- **Generate Key** button — disabled during generation; shows an indeterminate progress bar.

**Generation flow:**
1. Validate inputs (combination required if mode is key; tolerance must be float if given).
2. Disable button, show progress bar.
3. Call `autokey_core.generate_key()` in a background thread (prevents UI freeze).
4. OpenSCAD is launched non-blocking.
5. Show success message; re-enable button.
6. On error: show messagebox with the exception, re-enable button.

### AddProfile (`ui/add_profile.py`)

Form to create a new profile.

| Field | Required | Notes |
|-------|----------|-------|
| Name | yes | `^[A-Za-z0-9_\-]+$` |
| SVG file | yes | Browse dialog; file is copied to `profiles/<name>.svg` |
| Tolerance (`tol`) | yes | Float, default `0.0` |
| Height base (`ph_base`) | yes | Float (mm) |
| Handle X (`khcx`) | no | Float; blank = use global default |
| Handle Z (`khcz`) | no | Float; blank = use global default |
| Thin handle | no | Checkbox |
| Match handle | no | Checkbox |
| Default system | no | Dropdown of existing systems |

On save:
1. Validate all inputs.
2. Copy SVG → `profiles/<name>.svg`.
3. Generate DXF via `autokey_core.svg_to_dxf()` (warns if Inkscape is unavailable but continues).
4. Write SCAD via `autokey_core.write_profile_scad()`.
5. Append entry to `profiles.json` via `ProfileIndex.add_profile()`.
6. Navigate back to HomeScreen.

### AddSystem (`ui/add_system.py`)

Form to create a new lock system definition.

| Field | Required | Notes |
|-------|----------|-------|
| Name | yes | `^[A-Za-z0-9_\-]+$` |
| Key length (`kl`) | yes | Float (mm) |
| Shoulder (`aspace`) | yes | Float (mm) |
| Pin spacing (`pinspace`) | yes | Float (mm) |
| Highest cut offset (`hcut_offset`) | yes | Float (mm) |
| Cut spacing (`cutspace`) | yes | Float (mm) |
| V-cut angle (`cutangle`) | yes | Float (degrees) |
| Plateau width (`platspace`) | yes | Float (mm) |

On save:
1. Validate all inputs.
2. Write SCAD via `autokey_core.write_system_scad()`.
3. Append entry to `profiles.json` via `ProfileIndex.add_system()`.
4. Navigate back to HomeScreen.

---

## ProfileIndex (`ui/profile_index.py`)

The data layer. Holds all profile and system entries in memory; `profiles.json` is the on-disk store.

| Method | Description |
|--------|-------------|
| `load()` | Load from `profiles.json`; calls `rebuild_from_disk()` if file is missing. |
| `rebuild_from_disk()` | Scan `profiles/` and `definitions/` for `.scad` files; parse each and write `profiles.json`. |
| `save()` | Write current state to `profiles.json` (pretty-printed). |
| `add_profile(entry)` | Append a profile dict and save. |
| `add_system(entry)` | Append a system dict and save. |
| `set_profile_default_system(name, system_name)` | Persist a profile's default system choice. |

**Parsing logic:**
- Regex extraction of `varname = value;` patterns.
- Detects two `ph` formulas: `ph = X + 2*tol` (`ph_has_tol=true`) vs `ph = X` (`ph_has_tol=false`).
- Extracts `hcut_offset` from `hcut = ph - 2*tol - <offset>`.
- Detects boolean flags: `thin_handle = true`, `match_handle = true`.

---

## SVG Thumbnail Caching (`ui/svg_renderer.py`)

Thumbnails are generated once and cached.

- **Memory cache:** `{(svg_path, width, height): PhotoImage}` — survives for the app session.
- **Disk cache:** `%TEMP%/autokey3d_thumbs/<name>_<mtime>_<width>.png` — survives app restarts.

Cache key includes the file's modification time, so editing an SVG invalidates its cached thumbnail automatically.

`render(svg_path, width=120, height=80)` returns a `PIL.ImageTk.PhotoImage` or `None` (if Pillow is not installed or Inkscape fails).

Requires: **Pillow** (`pip install Pillow`). Inkscape is used for the actual SVG→PNG export.

---

## Testing (`tests/test_app.py`)

- A single module-level `tk.Tk()` root is created once (Tkinter only supports one root per process).
- Screens are tested by constructing them with a `_MockApp` stub (minimal stand-in for `App`).
- State is driven via `StringVar.set()` / direct method calls.
- `autokey_core.generate_key` and `tkinter.messagebox` are patched to avoid real subprocess calls.
- `pump()` helper processes pending Tkinter events between state changes and assertions.
- Tests are organised into classes: `TestProfileIndex`, `TestHomeScreen`, `TestProfileDetail`, `TestAddProfile`, `TestAddSystem`.
