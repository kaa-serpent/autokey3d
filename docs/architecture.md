# Architecture Reference

## Two-Layer Design

The project has a CLI layer and a Flask web app:

- **`src/autokey_core.py`** — pure generation logic. Key functions: `generate_key()`, `write_profile_scad()`, `write_system_scad()`.
- **`AutoKey.py`** — thin CLI wrapper that delegates to `autokey_core.generate_key()`. Original interface preserved.
- **`src/profile_index.py`** — data layer: loads/saves `profiles.json`, parses `.scad` files.
- **`web_app.py`** — Flask web server (pages + REST API).
- **`web/templates/`** — Jinja2 templates (extend `base.html`).
- **`web/static/`** — static assets (Bootstrap loaded from CDN).

---

## Two Separate Data Concepts

A key model requires **two independent files** used together:

1. **Profile** (`profiles/<name>.scad` + `.svg` + `.dxf`) — the keyway shape.
   - Parameters: `tol` (tolerance), `ph` (profile height).
   - Optional: `khcx`, `khcz`, `thin_handle`, `match_handle`.
   - See [profile.md](profile.md) for full reference.

2. **System definition** (`definitions/<name>.scad`) — the lock's mechanical spec.
   - Parameters: `kl` (key length), `aspace`, `pinspace`, `hcut`, `cutspace`, `cutangle`, `platspace`.
   - See [system.md](system.md) for full reference.

---

## External Tool Dependencies

| Tool | Required for | Notes |
|------|-------------|-------|
| **OpenSCAD** | STL rendering | Must be on `PATH`. Called headless: `openscad -o output.stl key.scad`. |
| **Inkscape** | Branding DXF | Called only when the SVG has `<text>` elements (always true for the built-in branding template). Flattens text to paths before the pure-Python DXF writer runs. |

`pstoedit` is **not used** — branding conversion is handled entirely by Inkscape + the pure-Python SVG→DXF parser in `autokey_core.py`.

Profile DXF files (`profiles/<name>.dxf`) are regenerated from the SVG on each run using the pure-Python parser — Inkscape is not involved.

Tool discovery order: `PATH` first, then common Windows install directories. See [generation.md](generation.md) for details.

---

## Data Flow Summary

```
profiles/<name>.svg  ──► svg_to_dxf() ──► profiles/<name>.dxf ──┐
profiles/<name>.scad ──────────────────────────────────────────── ├──► settings.scad ──► openscad key.scad ──► key.stl
definitions/<name>.scad ───────────────────────────────────────── ┘
```

`settings.scad` is auto-generated on each run — do not edit it manually.
