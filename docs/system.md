# System Definition Reference

A **system definition** describes the mechanical parameters of a lock: how long the key is, where the pins sit, how deep the cuts go, and the geometry of each cut. It is independent of the keyway shape (see [profile.md](profile.md)).

---

## File Structure

One file per lock system: `definitions/<name>.scad`

Example (`definitions/AB-C83.scad`):
```scad
kl = 27;
aspace = 4.42;
pinspace = 4.0;
hcut = ph - 2*tol - 4.66;
cutspace = 0.44;
cutangle = 112;
platspace = 0.0;
```

The system file is included into `settings.scad` after the profile, so it can read `ph` and `tol` set by the profile.

---

## Naming Convention

`BRAND-MODEL`, e.g. `AB-C83`, `BK-PZ88`, `MD-BIAX`. Same character rules as profiles: alphanumeric + `-` `_`.

---

## Parameters

| Parameter | Type | Unit | Required | Description |
|-----------|------|------|----------|-------------|
| `kl` | float | mm | YES | Total key length (shoulder to tip). |
| `aspace` | float | mm | no | Distance from shoulder to centre of first pin. |
| `pinspace` | float | mm | no | Centre-to-centre distance between consecutive pins. |
| `hcut` | float | mm | no | Height of the shallowest (highest) cut. Typically expressed as `ph - 2*tol - <offset>`. |
| `cutspace` | float | mm | no | Vertical distance between consecutive cut depth levels. |
| `cutangle` | float | degrees | no | Included angle of the V-cut groove. Typical: 85°–112°. |
| `platspace` | float | mm | no | Flat plateau width at the bottom of each cut (0 = sharp V). |

`kl` is the only strictly required parameter. The others are needed for any mode that applies cuts (bump key or key combination). A blank needs only `kl`.

### `hcut` vs `hcut_offset`

The `.scad` file stores `hcut` as a formula:
```scad
hcut = ph - 2*tol - 4.66;
```
The constant `4.66` is the `hcut_offset` stored in `profiles.json`. This keeps `hcut` correct regardless of which profile is used, because `ph` and `tol` are injected from the profile.

---

## Bump Key Modifier Parameters

These can be set in the system file or fall back to `base-settings.scad` defaults:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `bump_addaspace` | 1.5 mm | Extra shoulder spacing for bump keys. |
| `bump_addplatspace` | 0.4 mm | Extra plateau width for bump keys. |
| `bump_addcutdepth` | 0.2 mm | Additional cut depth for bump keys. |

Example override in a system file:
```scad
bump_addcutdepth = 0.3;
bump_addplatspace = 0.6;
```

---

## Special Cases

### Dual-shoulder systems (`aspaces` array)

Some bi-directional systems use two shoulder values (FORE / AFT pins):
```scad
aspaces = [5.41, 6.99];
```
The custom `keycombcuts()` module reads `aspaces[0]` and `aspaces[1]` separately.

### Rotational cut systems (MD-BIAX, MD-CLASSIC)

These systems encode each pin as a depth + rotation pair.

Combination format: `depth, rotation, depth, rotation, ...`  
Example: `3,S,5,K,4,Q,2,K,2,Q,0,D`

Rotation values:
- **FORE pin:** `K` (−20°), `B` (0°), `Q` (+20°)
- **AFT pin:** `M` (−20°), `D` (0°), `S` (+20°)

Additional parameters used by these systems:
```scad
kt = 2.3;        // key thickness (mm)
add_angle = 0;   // rotation offset applied globally
```

### Systems with custom modules

A system file can define `keycombcuts()` and/or `keytipcuts()` as OpenSCAD modules. If present, they replace the default implementations included from `includes/`. This allows fully custom cutting logic. See `definitions/MD-BIAX.scad` for an example.

---

## profiles.json Entry Schema

```json
{
  "name": "AB-C83",
  "scad_path": "definitions/AB-C83.scad",
  "kl": 27.0,
  "aspace": 4.42,
  "pinspace": 4.0,
  "hcut_offset": 4.66,
  "cutspace": 0.44,
  "cutangle": 112.0,
  "platspace": 0.0
}
```

Fields that are absent from the `.scad` file are stored as `null` in `profiles.json`.

---

## How to Add a System

### Via UI (AddSystem screen)

1. Go to **File → Add New System**.
2. Fill in all numeric fields (all are required in the standard UI form).
3. Click **Save**. The app:
   - Writes `definitions/<name>.scad` via `autokey_core.write_system_scad()`
   - Appends entry to `profiles.json`

### Via CLI / Python

```python
from autokey_core import write_system_scad

path = write_system_scad(
    base_dir=".",
    name="MY-SYSTEM",
    kl=28.0,
    aspace=4.5,
    pinspace=3.8,
    hcut_offset=4.2,
    cutspace=0.5,
    cutangle=100.0,
    platspace=0.0,
)
```

For advanced systems (custom modules, dual-pin arrays), write the `.scad` file manually and add the entry to `profiles.json` by hand or via `ProfileIndex.add_system()`.
