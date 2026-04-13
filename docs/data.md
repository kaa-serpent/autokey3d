# Data Layer Reference

## ProfileIndex (`profile_index.py`)

The data layer. Holds all profile and system entries in memory; `profiles.json` is the on-disk store.

| Method | Description |
|--------|-------------|
| `load()` | Load from `profiles.json`; calls `rebuild_from_disk()` if file is missing. |
| `rebuild_from_disk()` | Scan `profiles/` and `definitions/` for `.scad` files; parse each and write `profiles.json`. |
| `save()` | Write current state to `profiles.json` (pretty-printed). |
| `add_profile(entry)` | Append a profile dict and save. |
| `add_system(entry)` | Append a system dict and save. |
| `update_profile(name, updates)` | Merge a dict of changes into an existing profile entry and save. |
| `update_system(name, updates)` | Merge a dict of changes into an existing system entry and save. |
| `set_profile_default_system(name, system_name)` | Persist a profile's default system choice. |

**Parsing logic:**
- Regex extraction of `varname = value;` patterns.
- Detects two `ph` formulas: `ph = X + 2*tol` (`ph_has_tol=true`) vs `ph = X` (`ph_has_tol=false`).
- Extracts `hcut_offset` from `hcut = ph - 2*tol - <offset>`.
- Detects boolean flags: `thin_handle = true`, `match_handle = true`.

---

## Testing (`tests/test_profile_index.py`)

- Tests use a temporary directory that mimics the project structure (profiles/ + definitions/).
- `ProfileIndex` is constructed with the temp dir as `base_dir`.
- Tests cover: rebuild, field parsing, save/load roundtrip, add_profile, add_system.
