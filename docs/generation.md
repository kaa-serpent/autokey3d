# Generation Pipeline Reference

Key generation is handled by `autokey_core.generate_key()`. The CLI (`AutoKey.py`) and the UI both delegate to this function.

---

## `generate_key()` Signature

**Location:** `autokey_core.py`

```python
def generate_key(
    profile_svg_path,       # str  — path to profiles/<name>.svg
    definition_path,        # str  — path to definitions/<name>.scad
    mode,                   # str  — "blank" | "bumpkey" | "key"
    combination=None,       # str  — "1,2,3,4,5" (required when mode=="key")
    tol_override=None,      # float — overrides tol from profile .scad
    thin_handle=False,      # bool
    match_handle_connector=False,  # bool
    branding_model=None,    # str  — overrides label in branding text
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `profile_svg_path` | str | Path to the profile `.svg` file. The matching `.scad` and `.dxf` are derived from this path. |
| `definition_path` | str | Path to the system `.scad` file. |
| `mode` | str | `"blank"` — no cuts. `"bumpkey"` — enhanced bump cuts. `"key"` — specific combination. |
| `combination` | str or None | Comma-separated cut depths, e.g. `"1,2,3,4,5"`. Only used when `mode == "key"`. |
| `tol_override` | float or None | If set, replaces the `tol` value parsed from the profile `.scad`. |
| `thin_handle` | bool | Activates thin handle geometry (for impressioning grips). |
| `match_handle_connector` | bool | Sets grip thickness equal to connector width. |
| `branding_model` | str or None | Replaces the model name in the branding label engraved on the key. |

---

## The 6-Step Pipeline

### 1. Read source files
- Parse the profile `.scad` → extract `tol`, `ph`, optional handle overrides.
- Parse the system `.scad` → extract `kl`, cut parameters, detect custom modules.
- Detect whether the system defines `keycombcuts()` or `keytipcuts()` modules; if not, the default includes will be added.

### 2. Generate branding DXF
- Load `branding/branding-template.svg`.
- Replace placeholders: `%model%`, `%length%` (kl), `%tol%`.
- If the SVG contains text, call Inkscape to flatten text → paths.
- Convert the result to `branding/branding.dxf` via the internal SVG→DXF converter.

### 3. Prepare profile DXF
- Check whether `profiles/<name>.dxf` exists.
- If missing: convert `profiles/<name>.svg` → `profiles/<name>.dxf` via `svg_to_dxf()`.
- The resulting DXF is normalised to origin (0, 0) and Y-flipped.

### 4. Compose `settings.scad`
Blocks are concatenated in this order:
```
include <pre-settings.scad>;
<handle flags: match_handle, thin_handle>
<mode flags: bumpkey, blank>
<combination array>
<profile .scad content>
<system .scad content>
<base-settings.scad content>
[include <includes/default-keytipcuts.scad>;]   ← only if system has no keytipcuts
[include <includes/default-keycombcuts.scad>;]  ← only if system has no keycombcuts
```

`settings.scad` is auto-generated every run. Never edit it manually.

### 5. Launch OpenSCAD (non-blocking)
```bash
openscad key.scad
```
OpenSCAD is started as a background subprocess. The Python process returns immediately after launch.

### 6. Return
No return value. Errors raise exceptions caught by the caller (UI shows a messagebox; CLI prints to stderr).

---

## Generation Modes

| Mode | `bumpkey` flag | `blank` flag | `combination` used |
|------|---------------|-------------|-------------------|
| `"blank"` | false | true | no |
| `"bumpkey"` | true | false | no |
| `"key"` | false | false | yes |

---

## CLI Interface (`AutoKey.py`)

```bash
python AutoKey.py --bumpkey  --profile profiles/AB-AB95.svg --definition definitions/AB-E20.scad
python AutoKey.py --blank    --profile profiles/AB-AB1.svg  --definition definitions/AB-C83.scad
python AutoKey.py --key 1,2,3,4,5 --profile profiles/AB-AB1.svg --definition definitions/AB-C83.scad
```

### All arguments

| Argument | Description |
|----------|-------------|
| `--bumpkey` | Mode: bump key |
| `--blank` | Mode: key blank |
| `--key COMBINATION` | Mode: key with comma-separated combination |
| `--profile FILE` | Path to profile `.svg` (required) |
| `--definition FILE` | Path to system `.scad` (required) |
| `--tolerance TOL` | Float — overrides profile tolerance |
| `--branding-model MODEL` | String — overrides branding label |
| `--thin-handle` | Enable thin handle flag |
| `--match-handle-connector` | Match handle to connector width |
| `--version` | Print version and exit |
| `--isolate FILE` | (Experimental) Interactive profile extraction from a photo; requires OpenCV |

---

## SVG → DXF Conversion

`svg_to_dxf()` is a pure-Python converter — no Cairo, no librsvg required.

**Pipeline:**
1. Parse `<path>` elements from the SVG XML.
2. If `<text>` elements are present, run Inkscape first to flatten text to paths.
3. Process each path's `d` attribute:
   - Supported commands: `M`, `L`, `H`, `V`, `C`, `S`, `Q`, `T`, `A`, `Z`
   - Curves are approximated as polylines (cubic Bézier → `_bezier_cubic()`, quadratic → `_bezier_quad()`, arc → `_svg_arc()`)
4. Flip Y-axis (SVG origin is top-left; DXF/OpenSCAD origin is bottom-left).
5. Normalize bounding box to (0, 0).
6. Write DXF R12 format with `LINE` entities only (OpenSCAD requires R12 LINE entities).

---

## Tool Discovery (`_find_tool`)

External tools (Inkscape, OpenSCAD) are located via:
1. `PATH` environment variable.
2. Common Windows install directories:
   - `C:\Program Files\Inkscape\bin\inkscape.exe`
   - `C:\Program Files (x86)\Inkscape\bin\inkscape.exe`
   - `C:\Program Files\OpenSCAD\openscad.exe`
   - etc.

If a tool is not found, the function returns the bare command name (e.g. `"inkscape"`) and relies on the OS to resolve it at subprocess launch time.
