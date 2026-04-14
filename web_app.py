"""
autokey3d web interface.

Run with:
    python web_app.py

Then open http://localhost:5000 in a browser.
"""

import json
import os
import re
import tempfile
import threading
import time
import uuid

from flask import Flask, jsonify, redirect, render_template, request, send_file

from src import autokey_core
from src.profile_index import ProfileIndex

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")

# ── Job store (in-memory, fine for single-user local/Docker use) ─────────────
# { job_id: {"status": "pending"|"running"|"done"|"error",
#             "stl_path": str|None,
#             "error": str|None} }
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _load_index() -> ProfileIndex:
    idx = ProfileIndex(BASE_DIR)
    idx.load()
    return idx


# ── Page routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", active_page="generate")


@app.route("/profiles")
def page_profiles():
    return render_template("profiles.html", active_page="profiles")


@app.route("/systems")
def page_systems():
    return render_template("systems.html", active_page="systems")


@app.route("/profile/<name>")
def page_profile_detail(name):
    idx = _load_index()
    profile = next((p for p in idx.profiles if p["name"] == name), None)
    if profile is None:
        return "Profile not found", 404
    systems = idx.systems
    return render_template("profile_detail.html", active_page="profiles",
                           profile=profile, systems=systems)


@app.route("/system/<name>")
def page_system_detail(name):
    idx = _load_index()
    system = next((s for s in idx.systems if s["name"] == name), None)
    if system is None:
        return "System not found", 404
    # Profiles that use this system as their default
    using_profiles = [p["name"] for p in idx.profiles if p.get("default_system") == name]
    return render_template("system_detail.html", active_page="systems",
                           system=system, using_profiles=using_profiles,
                           all_profiles=idx.profiles)


@app.route("/add-profile")
def page_add_profile():
    return render_template("add_profile.html", active_page="profiles")


@app.route("/add-system")
def page_add_system():
    return render_template("add_system.html", active_page="systems")


@app.route("/guide")
def page_guide():
    return render_template("guide.html", active_page="guide")


# ── API: list all ─────────────────────────────────────────────────────────────

@app.route("/api/profiles")
def api_profiles():
    idx = _load_index()
    return jsonify({
        "profiles": idx.profiles,
        "systems": idx.systems,
    })


# ── API: single profile/system ────────────────────────────────────────────────

@app.route("/api/profiles/<name>")
def api_profile_get(name):
    idx = _load_index()
    profile = next((p for p in idx.profiles if p["name"] == name), None)
    if profile is None:
        return jsonify({"error": f"Unknown profile: {name}"}), 404
    return jsonify(profile)


@app.route("/api/systems/<name>")
def api_system_get(name):
    idx = _load_index()
    system = next((s for s in idx.systems if s["name"] == name), None)
    if system is None:
        return jsonify({"error": f"Unknown system: {name}"}), 404
    return jsonify(system)


# ── API: update profile ───────────────────────────────────────────────────────

@app.route("/api/profiles/<name>", methods=["PUT"])
def api_profile_update(name):
    idx = _load_index()
    profile = next((p for p in idx.profiles if p["name"] == name), None)
    if profile is None:
        return jsonify({"error": f"Unknown profile: {name}"}), 404

    data = request.get_json(force=True)

    try:
        tol = float(data.get("tol", profile["tol"]))
    except (TypeError, ValueError):
        return jsonify({"error": "tol must be a number"}), 400

    try:
        ph_base = float(data.get("ph_base", profile["ph_base"]))
    except (TypeError, ValueError):
        return jsonify({"error": "ph_base must be a number"}), 400

    khcx_raw = data.get("khcx", profile.get("khcx"))
    khcz_raw = data.get("khcz", profile.get("khcz"))
    khcx = None
    khcz = None
    if khcx_raw not in (None, ""):
        try:
            khcx = float(khcx_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "khcx must be a number"}), 400
    if khcz_raw not in (None, ""):
        try:
            khcz = float(khcz_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "khcz must be a number"}), 400

    thin_handle = bool(data.get("thin_handle", profile.get("thin_handle", False)))
    match_handle = bool(data.get("match_handle", profile.get("match_handle", False)))
    default_system = data.get("default_system", profile.get("default_system")) or None
    if default_system == "":
        default_system = None

    autokey_core.write_profile_scad(
        BASE_DIR, name, tol, ph_base,
        khcx=khcx, khcz=khcz,
        thin_handle=thin_handle, match_handle=match_handle,
    )

    idx.update_profile(name, {
        "tol": tol,
        "ph_base": ph_base,
        "khcx": khcx,
        "khcz": khcz,
        "thin_handle": thin_handle,
        "match_handle": match_handle,
        "default_system": default_system,
    })
    return jsonify({"ok": True})


# ── API: update system ────────────────────────────────────────────────────────

@app.route("/api/systems/<name>", methods=["PUT"])
def api_system_update(name):
    idx = _load_index()
    system = next((s for s in idx.systems if s["name"] == name), None)
    if system is None:
        return jsonify({"error": f"Unknown system: {name}"}), 404

    data = request.get_json(force=True)
    float_fields = ["kl", "aspace", "pinspace", "hcut_offset", "cutspace", "cutangle", "platspace"]
    values = {}
    for key in float_fields:
        raw = data.get(key, system.get(key))
        try:
            values[key] = float(raw)
        except (TypeError, ValueError):
            return jsonify({"error": f"{key} must be a number"}), 400

    autokey_core.write_system_scad(BASE_DIR, name, **values)
    idx.update_system(name, values)
    return jsonify({"ok": True})


# ── API: thumbnails ───────────────────────────────────────────────────────────

@app.route("/thumbnails/<profile_name>")
def thumbnail(profile_name):
    """Serve the SVG profile thumbnail directly — browsers render SVG natively."""
    svg_path = os.path.join(BASE_DIR, "profiles", profile_name + ".svg")
    if not os.path.isfile(svg_path):
        return "", 404
    return send_file(svg_path, mimetype="image/svg+xml")


# ── API: key generation ───────────────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True)

    profile_name = data.get("profile")
    system_name = data.get("system")
    mode = data.get("mode", "blank")
    combination = data.get("combination") or None
    tol_override_raw = data.get("tol_override")
    thin_handle = bool(data.get("thin_handle", False))
    match_handle = bool(data.get("match_handle", False))

    if not profile_name or not system_name:
        return jsonify({"error": "profile and system are required"}), 400
    if mode not in ("blank", "bumpkey", "key"):
        return jsonify({"error": "mode must be blank, bumpkey, or key"}), 400
    if mode == "key" and not combination:
        return jsonify({"error": "combination is required for mode=key"}), 400

    tol_override = None
    if tol_override_raw not in (None, ""):
        try:
            tol_override = float(tol_override_raw)
        except ValueError:
            return jsonify({"error": "tol_override must be a number"}), 400

    idx = _load_index()
    profile = next((p for p in idx.profiles if p["name"] == profile_name), None)
    system = next((s for s in idx.systems if s["name"] == system_name), None)

    if profile is None:
        return jsonify({"error": f"Unknown profile: {profile_name}"}), 400
    if system is None:
        return jsonify({"error": f"Unknown system: {system_name}"}), 400

    profile_svg = os.path.join(BASE_DIR, profile["svg_path"])
    definition_scad = os.path.join(BASE_DIR, system["scad_path"])

    job_id = str(uuid.uuid4())
    stl_path = os.path.join(tempfile.gettempdir(), f"autokey3d_{job_id}.stl")

    with _jobs_lock:
        _jobs[job_id] = {"status": "pending", "stl_path": None, "error": None}

    def _run():
        with _jobs_lock:
            _jobs[job_id]["status"] = "running"
        try:
            autokey_core.generate_key(
                profile_svg_path=profile_svg,
                definition_path=definition_scad,
                mode=mode,
                combination=combination,
                tol_override=tol_override,
                thin_handle=thin_handle,
                match_handle_connector=match_handle,
                export_stl=stl_path,
            )
            with _jobs_lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["stl_path"] = stl_path
        except Exception as exc:
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = str(exc)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def api_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "unknown job"}), 404
    return jsonify({
        "status": job["status"],
        "error": job["error"],
    })


@app.route("/api/download/<job_id>")
def api_download(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "unknown job"}), 404
    if job["status"] != "done":
        return jsonify({"error": "not ready"}), 400
    stl_path = job["stl_path"]
    if not stl_path or not os.path.isfile(stl_path):
        return jsonify({"error": "STL file not found"}), 500
    return send_file(stl_path, as_attachment=True, download_name="key.stl")


@app.route("/api/stl/<job_id>")
def api_stl_inline(job_id):
    """Serve STL for in-browser preview (no Content-Disposition attachment)."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "unknown job"}), 404
    if job["status"] != "done":
        return jsonify({"error": "not ready"}), 400
    stl_path = job["stl_path"]
    if not stl_path or not os.path.isfile(stl_path):
        return jsonify({"error": "STL file not found"}), 500
    return send_file(stl_path, mimetype="model/stl")


# ── API: add profile / system ─────────────────────────────────────────────────

@app.route("/api/profiles/<name>", methods=["DELETE"])
def api_profile_delete(name):
    idx = _load_index()
    profile = next((p for p in idx.profiles if p["name"] == name), None)
    if profile is None:
        return jsonify({"error": f"Unknown profile: {name}"}), 404

    for rel in ("svg_path", "scad_path", "dxf_path"):
        path = profile.get(rel)
        if path:
            full = os.path.join(BASE_DIR, path)
            if os.path.isfile(full):
                os.remove(full)

    idx.remove_profile(name)
    return jsonify({"ok": True})


@app.route("/api/systems/<name>", methods=["DELETE"])
def api_system_delete(name):
    idx = _load_index()
    system = next((s for s in idx.systems if s["name"] == name), None)
    if system is None:
        return jsonify({"error": f"Unknown system: {name}"}), 404

    scad_path = system.get("scad_path")
    if scad_path:
        full = os.path.join(BASE_DIR, scad_path)
        if os.path.isfile(full):
            os.remove(full)

    idx.remove_system(name)
    return jsonify({"ok": True})


@app.route("/api/add-profile", methods=["POST"])
def api_add_profile():
    import shutil

    name = request.form.get("name", "").strip()
    tol_str = request.form.get("tol", "0.0").strip()
    ph_str = request.form.get("ph_base", "").strip()
    khcx_str = request.form.get("khcx", "").strip()
    khcz_str = request.form.get("khcz", "").strip()
    thin_handle = request.form.get("thin_handle") == "on"
    match_handle = request.form.get("match_handle") == "on"
    default_system = request.form.get("default_system", "").strip() or None
    svg_file = request.files.get("svg_file")

    if not re.match(r'^[A-Za-z0-9_\-]+$', name):
        return jsonify({"error": "Name must contain only letters, digits, - or _"}), 400
    if not svg_file or not svg_file.filename:
        return jsonify({"error": "SVG file is required"}), 400
    try:
        tol = float(tol_str)
    except ValueError:
        return jsonify({"error": "Tolerance must be a number"}), 400
    try:
        ph_base = float(ph_str)
    except ValueError:
        return jsonify({"error": "Height base (ph_base) must be a number"}), 400

    khcx = None
    if khcx_str:
        try:
            khcx = float(khcx_str)
        except ValueError:
            return jsonify({"error": "Handle connector X must be a number"}), 400

    khcz = None
    if khcz_str:
        try:
            khcz = float(khcz_str)
        except ValueError:
            return jsonify({"error": "Handle connector Z must be a number"}), 400

    dest_svg = os.path.join(BASE_DIR, "profiles", f"{name}.svg")
    svg_file.save(dest_svg)

    dest_dxf = os.path.join(BASE_DIR, "profiles", f"{name}.dxf")
    try:
        autokey_core.svg_to_dxf(dest_svg, dest_dxf)
    except Exception:
        pass  # DXF generated lazily on first key generation

    autokey_core.write_profile_scad(
        BASE_DIR, name, tol, ph_base,
        khcx=khcx, khcz=khcz,
        thin_handle=thin_handle, match_handle=match_handle,
    )

    idx = _load_index()
    idx.add_profile({
        "name": name,
        "svg_path": f"profiles/{name}.svg",
        "scad_path": f"profiles/{name}.scad",
        "dxf_path": f"profiles/{name}.dxf",
        "tol": tol,
        "ph_base": ph_base,
        "ph_has_tol": True,
        "khcx": khcx,
        "khcz": khcz,
        "thin_handle": thin_handle,
        "match_handle": match_handle,
        "default_system": default_system,
    })
    return jsonify({"ok": True})


@app.route("/api/add-system", methods=["POST"])
def api_add_system():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()

    if not re.match(r'^[A-Za-z0-9_\-]+$', name):
        return jsonify({"error": "Name must contain only letters, digits, - or _"}), 400

    float_fields = ["kl", "aspace", "pinspace", "hcut_offset", "cutspace", "cutangle", "platspace"]
    values = {}
    for key in float_fields:
        raw = data.get(key, "")
        try:
            values[key] = float(raw)
        except (TypeError, ValueError):
            return jsonify({"error": f"{key} must be a number"}), 400

    autokey_core.write_system_scad(BASE_DIR, name, **values)

    idx = _load_index()
    idx.add_system({
        "name": name,
        "scad_path": f"definitions/{name}.scad",
        **values,
    })
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
