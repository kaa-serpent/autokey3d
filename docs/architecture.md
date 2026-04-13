# Architecture Reference

## Two-Layer Design

The project has a CLI layer and a Flask web app:

- **`autokey_core.py`** — pure generation logic. Key functions: `generate_key()`, `write_profile_scad()`, `write_system_scad()`.
- **`AutoKey.py`** — thin CLI wrapper that delegates to `autokey_core.generate_key()`. Original interface preserved.
- **`profile_index.py`** — data layer: loads/saves `profiles.json`, parses `.scad` files.
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

OpenSCAD, Inkscape, and pstoedit must be on `PATH`. They are invoked as subprocesses.

- **Inkscape** — converts branding SVG text to paths, and SVG → EPS → DXF when no pre-computed DXF exists.
- **OpenSCAD** — renders `key.scad` into the final STL.
- **pstoedit** — part of the branding DXF conversion chain.

The pre-computed `.dxf` files in `profiles/` allow key generation without Inkscape for the profile step.

Tool discovery order: `PATH` first, then common Windows install directories. See [generation.md § Tool Discovery](generation.md#tool-discovery-_find_tool) for details.

---

## Data Flow Summary

```
profiles/<name>.svg  ──► svg_to_dxf() ──► profiles/<name>.dxf ──┐
profiles/<name>.scad ──────────────────────────────────────────── ├──► settings.scad ──► openscad key.scad ──► key.stl
definitions/<name>.scad ───────────────────────────────────────── ┘
```

`settings.scad` is auto-generated on each run — do not edit it manually.
