# Web Interface Reference

The Flask web app is launched via `web_app.py` and served at `http://localhost:5000`.

```bash
python web_app.py
```

All templates live in `web/templates/`. Static assets (empty — Bootstrap is loaded from CDN) live in `web/static/`.

---

## Pages

### Navigation

Every page extends `web/templates/base.html`, which provides:
- A dark navbar with **AutoKey 3D** brand and three nav links: **Generate**, **Profiles**, **Systems**.
- The active link is highlighted via the `active_page` template variable passed from the route.
- Bootstrap 5.3 + Bootstrap Icons loaded from CDN.

---

### Generate (`/`)

Template: `index.html`

The main workflow page:
1. **Profile grid** — responsive thumbnail grid (2–6 columns). Clicking a card selects it; hovering reveals an info icon that opens the profile detail page in a new tab.
2. **Configure panel** — lock system dropdown, mode selector (blank / bump key / key combination), combination input (enabled only in key mode), tolerance override, thin-handle and match-connector checkboxes.
3. **Generate STL button** — disabled until a profile + system are selected (and combination filled if mode=key).

Generation is asynchronous:
- `POST /api/generate` → returns `job_id` immediately.
- Page polls `GET /api/status/<job_id>` every 2 s.
- On completion a **Download STL** button appears linking to `GET /api/download/<job_id>`.

**Deep-link:** `/?profile=<name>` pre-selects a profile on load (used by the profile detail page's "Generate key" button).

---

### Profiles (`/profiles`)

Template: `profiles.html`

Thumbnail grid of all profiles with:
- SVG thumbnail, name, `tol`, `ph_base`, thin/match badges, default system name.
- Live search filter (JS, case-insensitive name match).
- Clicking any card navigates to `/profile/<name>`.
- **+ Add Profile** button → `/add-profile`.

---

### Profile Detail (`/profile/<name>`)

Template: `profile_detail.html`

Two-column layout: SVG thumbnail on the left, parameters on the right.

**View mode** (default): read-only `<dl>` list showing all parameters.

**Edit mode** (click "Edit"): parameters become input fields in-place (no page reload). Click **Save** → `PUT /api/profiles/<name>` → rewrites the `.scad` file and `profiles.json`, then redirects to `/profiles`. Click **Cancel** → reverts to view mode.

Parameters shown/editable:
- `tol`, `ph_base`, `khcx` (optional), `khcz` (optional)
- `thin_handle`, `match_handle` checkboxes
- `default_system` dropdown

A **"Generate key"** button links to `/?profile=<name>` for a direct jump to the generate workflow.

---

### Systems (`/systems`)

Template: `systems.html`

A `table-hover` table listing all lock systems. Columns: name, `kl`, `aspace`, `pinspace`, `hcut_offset`, `cutspace`, `cutangle`, `platspace`. Numeric cells use monospace font.

- Live search filter.
- Clicking any row (or the Edit button) navigates to `/system/<name>`.
- **+ Add System** button → `/add-system`.

---

### System Detail (`/system/<name>`)

Template: `system_detail.html`

Same view/edit toggle pattern as profile detail.

**View mode:** labelled read-only values for all 7 numeric parameters plus the `.scad` file path.

**Edit mode:** number inputs; Save → `PUT /api/systems/<name>` → rewrites `.scad` + `profiles.json`, redirects to `/systems`.

A **"Used as default by"** sidebar card lists profile names that reference this system as their default, each with a thumbnail link.

---

### Add Profile (`/add-profile`)

Template: `add_profile.html`

Form fields: name, SVG file upload, `tol`, `ph_base`, `khcx`, `khcz`, thin/match checkboxes, default system dropdown. On submit → `POST /api/add-profile` (multipart). Redirects to `/profiles` on success. Cancel → `/profiles`.

---

### Add System (`/add-system`)

Template: `add_system.html`

Form fields: name, `kl`, `aspace`, `pinspace`, `hcut_offset`, `cutspace`, `cutangle`, `platspace`. On submit → `POST /api/add-system` (JSON). Redirects to `/systems` on success. Cancel → `/systems`.

---

## API Endpoints

### List

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/profiles` | All profiles and systems as `{ profiles: [...], systems: [...] }` |
| `GET` | `/thumbnails/<name>` | Serve `profiles/<name>.svg` directly (browser renders natively) |

### Single record

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/api/profiles/<name>` | Single profile JSON |
| `GET` | `/api/systems/<name>` | Single system JSON |

### Create

| Method | Route | Body | Description |
|--------|-------|------|-------------|
| `POST` | `/api/add-profile` | multipart/form-data | Create profile, write `.scad`, update `profiles.json` |
| `POST` | `/api/add-system` | JSON | Create system, write `.scad`, update `profiles.json` |

### Update

| Method | Route | Body | Description |
|--------|-------|------|-------------|
| `PUT` | `/api/profiles/<name>` | JSON | Update profile params → rewrite `.scad` + `profiles.json` |
| `PUT` | `/api/systems/<name>` | JSON | Update system params → rewrite `.scad` + `profiles.json` |

### Generation

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/api/generate` | Start async key generation; returns `{ job_id }` |
| `GET` | `/api/status/<job_id>` | Returns `{ status, error }` (`pending`/`running`/`done`/`error`) |
| `GET` | `/api/download/<job_id>` | Download completed STL file |

---

## Job Store

Generation jobs are kept in an in-memory dict `_jobs` (keyed by UUID). This is intentional — the app targets single-user local/Docker use. Jobs are never persisted to disk; they vanish on server restart.

---

## ProfileIndex in the web layer

`web_app.py` calls `_load_index()` on every request (cheap — just reads `profiles.json`). This avoids stale state between requests without needing a global singleton.

Relevant `ProfileIndex` methods used by the web layer:

| Method | Used by |
|--------|---------|
| `add_profile(entry)` | `POST /api/add-profile` |
| `add_system(entry)` | `POST /api/add-system` |
| `update_profile(name, updates)` | `PUT /api/profiles/<name>` |
| `update_system(name, updates)` | `PUT /api/systems/<name>` |
