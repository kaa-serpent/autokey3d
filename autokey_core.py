"""
Core key generation logic for AutoKey3D.
Extracted from AutoKey.py so the UI can call generate_key() directly.
"""

from __future__ import print_function

import math
import os
import re
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
BRAND_DIR = os.path.join(BASE_DIR, "branding")

# ---------------------------------------------------------------------------
# Tool path resolution
# Tools may not be on PATH (common on Windows), so we search known locations.
# ---------------------------------------------------------------------------

_TOOL_SEARCH_DIRS = [
    r"C:\Program Files\Inkscape\bin",
    r"C:\Program Files (x86)\Inkscape\bin",
    r"C:\Program Files\OpenSCAD",
    r"C:\Program Files (x86)\OpenSCAD",
]

_tool_cache = {}


def _find_tool(name):
    """
    Return the full path to a tool executable, or just the bare name
    (letting the OS resolve it from PATH) if we can't find it ourselves.

    Checks PATH first, then common Windows installation directories.
    Raises RuntimeError if the tool cannot be located at all.
    """
    if name in _tool_cache:
        return _tool_cache[name]

    # 1. Try PATH via shutil.which
    found = shutil.which(name)
    if found:
        _tool_cache[name] = found
        return found

    # 2. Search known Windows install directories
    for directory in _TOOL_SEARCH_DIRS:
        for ext in ("", ".exe", ".com"):
            candidate = os.path.join(directory, name + ext)
            if os.path.isfile(candidate):
                _tool_cache[name] = candidate
                return candidate

    # 3. Fall back to bare name — subprocess will raise a clear error if missing
    _tool_cache[name] = name
    return name


def _ensure_profile_dxf(profile_svg_path):
    """
    Generate profile.dxf in BASE_DIR from the profile SVG.

    Always regenerates from the SVG so that the output is guaranteed to use
    LINE entities (required by OpenSCAD's 2D import).  The pure-Python parser
    is fast enough that caching pre-computed DXF files is not needed.
    """
    dest_dxf = os.path.join(BASE_DIR, "profile.dxf")
    svg_to_dxf(profile_svg_path, dest_dxf)


def _bezier_cubic(p0, p1, p2, p3, n=12):
    """Approximate a cubic bezier with n line segments, returning n points (excluding p0)."""
    pts = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        pts.append((
            u**3*p0[0] + 3*u**2*t*p1[0] + 3*u*t**2*p2[0] + t**3*p3[0],
            u**3*p0[1] + 3*u**2*t*p1[1] + 3*u*t**2*p2[1] + t**3*p3[1],
        ))
    return pts


def _bezier_quad(p0, p1, p2, n=8):
    """Approximate a quadratic bezier with n line segments, returning n points (excluding p0)."""
    pts = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        pts.append((
            u**2*p0[0] + 2*u*t*p1[0] + t**2*p2[0],
            u**2*p0[1] + 2*u*t*p1[1] + t**2*p2[1],
        ))
    return pts


def _svg_arc(x1, y1, rx, ry, phi_deg, fa, fs, x2, y2, n=12):
    """Convert an SVG arc segment to a list of (x, y) points (excluding start)."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [(x2, y2)]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(phi_deg)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p =  cp * dx + sp * dy
    y1p = -sp * dx + cp * dy
    # Radius correction
    lam = (x1p / rx)**2 + (y1p / ry)**2
    if lam > 1:
        sq = math.sqrt(lam)
        rx, ry = sq * rx, sq * ry
    # Center in rotated frame
    num = rx**2 * ry**2 - rx**2 * y1p**2 - ry**2 * x1p**2
    den = rx**2 * y1p**2 + ry**2 * x1p**2
    sq = math.sqrt(max(0.0, num / den)) * (1 if fa != fs else -1)
    cxp, cyp = sq * rx * y1p / ry, -sq * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2
    # Angles
    def angle(ux, uy, vx, vy):
        n_ = math.sqrt((ux**2 + uy**2) * (vx**2 + vy**2))
        a = math.acos(max(-1.0, min(1.0, (ux*vx + uy*vy) / n_))) if n_ else 0
        return -a if ux * vy - uy * vx < 0 else a
    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle((x1p - cxp) / rx, (y1p - cyp) / ry,
                   (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dtheta > 0:
        dtheta -= 2 * math.pi
    elif fs and dtheta < 0:
        dtheta += 2 * math.pi
    pts = []
    for i in range(1, n + 1):
        t = theta1 + dtheta * i / n
        pts.append((
            cp * rx * math.cos(t) - sp * ry * math.sin(t) + cx,
            sp * rx * math.cos(t) + cp * ry * math.sin(t) + cy,
        ))
    return pts


def _svg_path_to_polylines(d):
    """Parse an SVG path d attribute into a list of polylines [(x, y), ...]."""
    RE = re.compile(r'([MmLlHhVvCcSsQqTtAaZz])|'
                    r'([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)')
    toks = RE.findall(d)

    polylines = []
    current = []
    x = y = sx = sy = 0.0
    last_cp = None
    cmd = None
    idx = 0

    def read_nums(n):
        nonlocal idx
        result = []
        while len(result) < n and idx < len(toks):
            c, v = toks[idx]
            if v:
                result.append(float(v))
                idx += 1
            elif c:
                break
            else:
                idx += 1
        return result

    while idx < len(toks):
        c, v = toks[idx]
        if c:
            cmd = c
            idx += 1
        # else: number → implicit repeat of last command; read_nums will consume it

        if cmd is None:
            continue

        if cmd in ('M', 'm'):
            nums = read_nums(2)
            if len(nums) < 2:
                break
            if current:
                polylines.append(current)
            x, y = (nums[0], nums[1]) if cmd == 'M' else (x + nums[0], y + nums[1])
            current = [(x, y)]
            sx, sy = x, y
            last_cp = None
            cmd = 'L' if cmd == 'M' else 'l'

        elif cmd in ('L', 'l'):
            nums = read_nums(2)
            if len(nums) < 2:
                break
            x, y = (nums[0], nums[1]) if cmd == 'L' else (x + nums[0], y + nums[1])
            current.append((x, y))
            last_cp = None

        elif cmd in ('H', 'h'):
            nums = read_nums(1)
            if not nums:
                break
            x = nums[0] if cmd == 'H' else x + nums[0]
            current.append((x, y))
            last_cp = None

        elif cmd in ('V', 'v'):
            nums = read_nums(1)
            if not nums:
                break
            y = nums[0] if cmd == 'V' else y + nums[0]
            current.append((x, y))
            last_cp = None

        elif cmd in ('C', 'c'):
            nums = read_nums(6)
            if len(nums) < 6:
                break
            if cmd == 'C':
                cx1, cy1, cx2, cy2, ex, ey = nums
            else:
                cx1, cy1, cx2, cy2, ex, ey = (
                    x+nums[0], y+nums[1], x+nums[2], y+nums[3], x+nums[4], y+nums[5])
            current.extend(_bezier_cubic((x, y), (cx1, cy1), (cx2, cy2), (ex, ey)))
            last_cp = (cx2, cy2)
            x, y = ex, ey

        elif cmd in ('S', 's'):
            nums = read_nums(4)
            if len(nums) < 4:
                break
            cx1 = 2*x - last_cp[0] if last_cp else x
            cy1 = 2*y - last_cp[1] if last_cp else y
            cx2, cy2, ex, ey = (
                (nums[0], nums[1], nums[2], nums[3]) if cmd == 'S'
                else (x+nums[0], y+nums[1], x+nums[2], y+nums[3]))
            current.extend(_bezier_cubic((x, y), (cx1, cy1), (cx2, cy2), (ex, ey)))
            last_cp = (cx2, cy2)
            x, y = ex, ey

        elif cmd in ('Q', 'q'):
            nums = read_nums(4)
            if len(nums) < 4:
                break
            if cmd == 'Q':
                cx1, cy1, ex, ey = nums
            else:
                cx1, cy1, ex, ey = x+nums[0], y+nums[1], x+nums[2], y+nums[3]
            current.extend(_bezier_quad((x, y), (cx1, cy1), (ex, ey)))
            last_cp = (cx1, cy1)
            x, y = ex, ey

        elif cmd in ('T', 't'):
            nums = read_nums(2)
            if len(nums) < 2:
                break
            cx1 = 2*x - last_cp[0] if last_cp else x
            cy1 = 2*y - last_cp[1] if last_cp else y
            ex, ey = (nums[0], nums[1]) if cmd == 'T' else (x + nums[0], y + nums[1])
            current.extend(_bezier_quad((x, y), (cx1, cy1), (ex, ey)))
            last_cp = (cx1, cy1)
            x, y = ex, ey

        elif cmd in ('A', 'a'):
            nums = read_nums(7)
            if len(nums) < 7:
                break
            rx_, ry_, xrot, fa, fs, ex, ey = nums
            if cmd == 'a':
                ex, ey = x + ex, y + ey
            current.extend(_svg_arc(x, y, rx_, ry_, xrot, int(fa), int(fs), ex, ey))
            x, y = ex, ey
            last_cp = None

        elif cmd in ('Z', 'z'):
            if current:
                current.append((sx, sy))
                polylines.append(current)
                current = []
            x, y = sx, sy
            last_cp = None

    if current:
        polylines.append(current)
    return polylines


def _svg_file_to_polylines(svg_path):
    """
    Extract all <path> elements from an SVG as Y-flipped polylines, normalised
    so that the overall bounding box starts at (0, 0).

    The normalisation ensures that regardless of where the profile shape sits on
    the SVG canvas, the DXF output always starts at the origin.  key.scad
    expects the profile to begin near (0, 0) so that after resize() the blade
    aligns with the handle connector.
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()
    h_str = root.get('height', '100')
    h = float(re.findall(r'[\d.eE+\-]+', h_str)[0])
    polylines = []
    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag == 'path':
            d = elem.get('d', '')
            if d:
                for poly in _svg_path_to_polylines(d):
                    polylines.append([(px, h - py) for px, py in poly])

    if polylines:
        all_x = [px for poly in polylines for px, _ in poly]
        all_y = [py for poly in polylines for _, py in poly]
        x_min, y_min = min(all_x), min(all_y)
        polylines = [[(px - x_min, py - y_min) for px, py in poly]
                     for poly in polylines]

    return polylines


def _write_dxf(polylines, dxf_path):
    """Write polylines as DXF R12 LINE entities."""
    with open(dxf_path, 'w') as f:
        f.write('  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n')
        f.write('  0\nSECTION\n  2\nENTITIES\n')
        for poly in polylines:
            for i in range(len(poly) - 1):
                x1, y1 = poly[i]
                x2, y2 = poly[i + 1]
                if abs(x1 - x2) > 1e-9 or abs(y1 - y2) > 1e-9:
                    f.write('  0\nLINE\n  8\n0\n')
                    f.write(' 10\n%.6f\n 20\n%.6f\n 30\n0.000000\n' % (x1, y1))
                    f.write(' 11\n%.6f\n 21\n%.6f\n 31\n0.000000\n' % (x2, y2))
        f.write('  0\nENDSEC\n  0\nEOF\n')


def svg_to_dxf(svg_path, dxf_path):
    """
    Convert an SVG to a DXF compatible with OpenSCAD's 2D import().

    Uses pure Python to parse SVG <path> elements and emit LINE entities.
    OpenSCAD resizes the imported DXF to ph automatically, so the raw SVG
    coordinate scale does not need to match physical dimensions.

    If the SVG contains <text> elements (e.g. the branding template),
    Inkscape is called first with --export-text-to-path to flatten them
    into <path> elements before parsing.
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()
    has_text = any(
        (e.tag.split('}')[-1] if '}' in e.tag else e.tag) == 'text'
        for e in root.iter()
    )

    if has_text:
        inkscape = _find_tool('inkscape')
        tmp_svg = svg_path + '.flat.svg'
        try:
            subprocess.check_call(
                [inkscape, '--export-type=svg', '--export-text-to-path',
                 '--export-filename=' + tmp_svg, svg_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            polylines = _svg_file_to_polylines(tmp_svg)
        finally:
            if os.path.exists(tmp_svg):
                os.remove(tmp_svg)
    else:
        polylines = _svg_file_to_polylines(svg_path)

    _write_dxf(polylines, dxf_path)


def generate_key(
    profile_svg_path,
    definition_path,
    mode,
    combination=None,
    tol_override=None,
    thin_handle=False,
    match_handle_connector=False,
    branding_model=None,
):
    """
    Generate a key model and open it in OpenSCAD (non-blocking).

    Args:
        profile_svg_path: path to the profile .svg file
        definition_path:  path to the system .scad definition file
        mode:             "blank" | "bumpkey" | "key"
        combination:      comma-separated depths string, e.g. "1,2,3,4,5"
                          (only used when mode=="key")
        tol_override:     float or None — overrides tolerance from profile .scad
        thin_handle:      bool
        match_handle_connector: bool
        branding_model:   string or None — overrides the model label in branding
    """
    # --- branding ---
    with open(os.path.join(BRAND_DIR, "branding-template.svg"), 'r') as f:
        branding = f.read()

    model = os.path.basename(definition_path).replace(".scad", "")
    if branding_model:
        model = branding_model

    # --- read system definition ---
    with open(definition_path, 'r') as f:
        definition = f.read()

    need_default_keycombcuts = "module keycombcuts()" not in definition
    need_default_keytipcuts = "module keytipcuts()" not in definition

    # --- read profile definition ---
    profile_definition_file = os.path.splitext(profile_svg_path)[0] + ".scad"
    with open(profile_definition_file, 'r') as f:
        profile_definition = f.read()

    khcx_override = "khcx=" in profile_definition
    khcz_override = "khcz=" in profile_definition
    khcxoff_override = "khcxoff=" in profile_definition

    def_tol = None
    def_kl = None
    def_tol_idx = None

    for line in definition.splitlines():
        m = re.match(r"\s*kl\s*=\s*([\d.]+)\s*;", line)
        if m:
            def_kl = m.group(1)

    for idx, line in enumerate(profile_definition.splitlines()):
        m = re.match(r"\s*tol\s*=\s*([\d.]+)\s*;", line)
        if m:
            def_tol = m.group(1)
            def_tol_idx = idx

    if def_kl is None:
        raise ValueError("Failed to find key length (kl) in system definition file: %s" % definition_path)

    if def_tol is None:
        raise ValueError("Failed to find key tolerance (tol) in profile definition file: %s" % profile_definition_file)

    if tol_override is not None:
        lines = profile_definition.splitlines()
        lines[def_tol_idx] = "tol = %s;" % tol_override
        profile_definition = "\n".join(lines)
        def_tol = str(tol_override)

    branding = branding.replace("%model%", model)
    branding = branding.replace("%length%", "%s" % def_kl)
    branding = branding.replace("%tol%", "%s" % def_tol)
    branding_svg = os.path.join(BRAND_DIR, "branding.svg")
    with open(branding_svg, 'w') as f:
        f.write(branding)

    # Convert branding SVG → DXF directly via Inkscape 1.x (no pstoedit needed)
    svg_to_dxf(branding_svg, os.path.join(BRAND_DIR, "branding.dxf"))

    # --- read base settings ---
    with open(os.path.join(BASE_DIR, "base-settings.scad"), 'r') as f:
        base_settings = f.read()

    if khcx_override:
        base_settings = base_settings.replace("khcx=", "//khcx=")
    if khcz_override:
        base_settings = base_settings.replace("khcz=", "//khcz=")
    if khcxoff_override:
        base_settings = base_settings.replace("khcxoff=", "//khcxoff=")

    # --- compose settings.scad ---
    with open(os.path.join(BASE_DIR, "settings.scad"), 'w') as f:
        f.write("/* AUTO-GENERATED FILE - DO NOT EDIT */\n\n")
        f.write("include <pre-settings.scad>;\n")

        f.write("match_handle = %s;\n" % ("true" if match_handle_connector else "false"))
        f.write("bumpkey = %s;\n" % ("true" if mode == "bumpkey" else "false"))
        f.write("blank = %s;\n" % ("true" if mode == "blank" else "false"))

        if mode == "key" and combination:
            parts = combination.split(",")
            for i in range(len(parts)):
                try:
                    int(parts[i])
                except ValueError:
                    parts[i] = '"%s"' % parts[i]
            f.write("combination = [%s];\n" % ",".join(parts))
        else:
            f.write("combination = 0;\n")

        f.write("thin_handle = %s;\n" % ("true" if thin_handle else "false"))

        f.write(profile_definition)
        f.write("\n")
        f.write(definition)
        f.write("\n")
        f.write(base_settings)
        f.write("\n")

        if need_default_keytipcuts:
            f.write("include <includes/default-keytipcuts.scad>;\n")
        if need_default_keycombcuts:
            f.write("include <includes/default-keycombcuts.scad>;\n")

    # --- profile DXF ---
    _ensure_profile_dxf(profile_svg_path)

    # --- launch OpenSCAD (non-blocking) ---
    subprocess.Popen([_find_tool("openscad"), os.path.join(BASE_DIR, "key.scad")])


def write_profile_scad(base_dir, name, tol, ph_base, khcx=None, khcz=None,
                       thin_handle=False, match_handle=False):
    """
    Write profiles/<name>.scad in the existing project format.
    Returns the absolute path to the written file.

    ph_base is the raw height before tolerance (i.e. ph = ph_base + 2*tol).
    """
    lines = [
        "// The tolerance to use when removing material from the profile",
        "tol = %s;" % tol,
        "",
        "// Key profile height (including tolerance, i.e. measured on the lock, not the blank)",
        "// If you have information on the key blank height, add 2*tol.",
        "ph=%s + 2*tol;" % ph_base,
        'profile_path = "profiles/%s.dxf";' % name,
    ]
    if khcx is not None:
        lines.append("khcx=%s;" % khcx)
    if khcz is not None:
        lines.append("khcz=%s;" % khcz)
    if thin_handle:
        lines.append("thin_handle=true;")
    if match_handle:
        lines.append("match_handle=true;")

    dest = os.path.join(base_dir, "profiles", "%s.scad" % name)
    with open(dest, 'w') as f:
        f.write("\n".join(lines) + "\n")
    return dest


def write_system_scad(base_dir, name, kl, aspace, pinspace, hcut_offset,
                      cutspace, cutangle, platspace):
    """
    Write definitions/<name>.scad in the existing project format.
    Returns the absolute path to the written file.

    hcut_offset is the constant subtracted in: hcut = ph - 2*tol - <hcut_offset>
    """
    content = (
        "// Key length\n"
        "kl={kl};\n"
        "\n"
        "// Combination cuts\n"
        "\n"
        "// Shoulder\n"
        "aspace = {aspace};\n"
        "\n"
        "// Pin distance\n"
        "pinspace = {pinspace};\n"
        "\n"
        "// Highest cut\n"
        "hcut = ph - 2*tol - {hcut_offset};\n"
        "\n"
        " // Cut spacing\n"
        "cutspace = {cutspace};\n"
        "\n"
        "// Cut angle\n"
        "cutangle = {cutangle};\n"
        "\n"
        "// Plateau spacing of the cut\n"
        "platspace = {platspace};\n"
    ).format(
        kl=kl, aspace=aspace, pinspace=pinspace, hcut_offset=hcut_offset,
        cutspace=cutspace, cutangle=cutangle, platspace=platspace,
    )

    dest = os.path.join(base_dir, "definitions", "%s.scad" % name)
    with open(dest, 'w') as f:
        f.write(content)
    return dest
