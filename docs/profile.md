# Profile Reference

A **profile** defines the keyway cross-sectional shape — the silhouette of the key blade as seen end-on. It is entirely separate from the lock's mechanical parameters (see [system.md](system.md)).

---

## Three-File Structure

Every profile requires three files under `profiles/`:

| File | Purpose |
|------|---------|
| `profiles/<name>.svg` | Vectorized keyway outline (source of truth) |
| `profiles/<name>.scad` | Metadata: tolerance, height, optional handle overrides |
| `profiles/<name>.dxf` | Pre-computed DXF used by OpenSCAD; regenerated from SVG if absent |

All three must share the same base name. The `.dxf` can be regenerated at generation time — the `.svg` is the actual source.

---

## Naming Convention

`BRAND-MODEL`, e.g. `AB-AB1`, `BK-BK1`, `MD-CLASSIC`. Use only alphanumeric characters, hyphens, and underscores.

---

## Profile SCAD File

Minimal example (`profiles/AB-AB1.scad`):
```scad
tol = 0.0;
ph = 8.25 + 2*tol;
profile_path = "profiles/AB-AB1.dxf";
```

Optional overrides:
```scad
khcx = 2.5;
khcz = 7.0;
thin_handle = true;
match_handle = true;
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tol` | float (mm) | — | Material tolerance removed from profile shape. |
| `ph` | float (mm) | — | Profile height used by OpenSCAD. Either `ph_base + 2*tol` or just `ph_base` (see below). |
| `profile_path` | string | — | Relative path to the DXF file. Always `"profiles/<name>.dxf"`. |
| `khcx` | float (mm) | 3.0 | Handle connector width (X axis). Overrides global default from `base-settings.scad`. |
| `khcz` | float (mm) | 5.0 | Handle connector length (Z axis). Overrides global default. |
| `thin_handle` | bool | false | Use a thin handle (suitable for impressioning grips). |
| `match_handle` | bool | false | Match handle thickness to the connector width for a snug fit. |

---

## Tolerance (`tol`)

`tol` is the amount of material (mm) removed uniformly from the profile boundary via a Minkowski operation in OpenSCAD. It compensates for measurement uncertainty when the profile was extracted from a photo of the keyway rather than from a physical key blank.

- `tol = 0.0` — profile extracted from a key blank or precise template; no material removed.
- `tol = 0.1–0.25` — profile extracted from a keyway photo; typical value ≈ 0.2.

The sign matters: larger tolerance = thinner blade = more clearance inside the lock.

---

## Profile Height (`ph`) and `ph_has_tol`

`ph` is the total height of the key profile used by OpenSCAD. There are two conventions:

| Convention | SCAD formula | `ph_has_tol` (in profiles.json) |
|------------|-------------|----------------------------------|
| Height includes tolerance | `ph = ph_base + 2*tol` | `true` |
| Height is absolute | `ph = ph_base` | `false` |

The `+ 2*tol` form is used when `ph_base` was measured on the lock rather than on the blank — adding `2*tol` adjusts for the material that will be removed from both sides.

---

## Handle Connector Overrides (`khcx`, `khcz`)

The handle connector is the stub that joins the key blade to the handle grip. Global defaults are in `base-settings.scad`:
- `khcx = 3` mm (width)
- `khcz = 5` mm (length)

Some profiles need narrower connectors (e.g., `khcx = 2.3`) to fit inside the keyway correctly. Override these in the `.scad` file only when the default does not fit.

`thin_handle = true` reduces the grip dimensions for slim impressioning blanks.  
`match_handle = true` sets the grip thickness equal to `khcx` for a flush appearance.

---

## profiles.json Entry Schema

```json
{
  "name": "AB-AB1",
  "svg_path": "profiles/AB-AB1.svg",
  "scad_path": "profiles/AB-AB1.scad",
  "dxf_path": "profiles/AB-AB1.dxf",
  "tol": 0.0,
  "ph_base": 8.25,
  "ph_has_tol": true,
  "khcx": null,
  "khcz": null,
  "thin_handle": false,
  "match_handle": false,
  "default_system": null
}
```

`khcx`, `khcz`, and `default_system` are `null` when not set. `default_system` is a system name string (e.g. `"AB-C83"`) and is pre-selected in the UI dropdown for convenience.

---

## How to Add a Profile

### Via UI (AddProfile screen)

1. Open the app, go to **File → Add New Profile**.
2. Fill in:
   - **Name** — alphanumeric + `-` `_` only.
   - **SVG file** — browse to the keyway SVG; it is copied to `profiles/<name>.svg`.
   - **Tolerance** — float, default `0.0`.
   - **Height base (ph_base)** — float in mm.
   - **Handle X / Handle Z** — optional floats; leave blank for defaults.
   - **Thin handle / Match handle** — checkboxes.
   - **Default system** — optional dropdown.
3. Click **Save**. The app:
   - Copies SVG → `profiles/<name>.svg`
   - Generates `profiles/<name>.dxf` via `autokey_core.svg_to_dxf()`
   - Writes `profiles/<name>.scad` via `autokey_core.write_profile_scad()`
   - Appends entry to `profiles.json`

### Via CLI / Python

```python
from autokey_core import write_profile_scad

path = write_profile_scad(
    base_dir=".",
    name="MY-PROFILE",
    tol=0.2,
    ph_base=9.0,
    khcx=None,       # use default
    khcz=None,       # use default
    thin_handle=False,
    match_handle=False,
)
```

Then add the DXF manually or let `generate_key()` create it on first run.

---

## SVG Requirements

- Must contain `<path>` elements outlining the keyway cross-section.
- If the SVG contains `<text>` elements, Inkscape is invoked first to flatten them to paths.
- Coordinate system: SVG Y-axis is flipped during conversion — the converter handles this automatically.
- The DXF output is normalized to origin (0, 0) regardless of SVG placement.
