"""
SVG → ImageTk.PhotoImage renderer with disk-cached PNG thumbnails.

Uses Inkscape (already required by the project) to convert SVGs to PNG,
then loads them with Pillow. No Cairo or native SVG library needed.

Requires: pip install Pillow
"""

import os
import subprocess
import tempfile
import tkinter as tk

_mem_cache = {}   # (svg_path, width, height) → ImageTk.PhotoImage
_png_cache_dir = os.path.join(tempfile.gettempdir(), "autokey3d_thumbs")

try:
    from PIL import Image, ImageTk
    _pillow_available = True
except ImportError:
    _pillow_available = False


def render(svg_path, width=120, height=80):
    """
    Convert an SVG file to an ImageTk.PhotoImage of the given size.

    Returns a PhotoImage on success, or None if rendering fails.
    Keep a reference to the returned object in your widget to prevent GC.
    """
    if not _pillow_available or not os.path.exists(svg_path):
        return None

    key = (svg_path, width, height)
    if key in _mem_cache:
        return _mem_cache[key]

    png_path = _get_cached_png(svg_path, width)
    if png_path is None:
        return None

    try:
        img = Image.open(png_path)
        img.thumbnail((width, height), Image.LANCZOS)

        # Flatten onto white background to handle transparency
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        if img.mode == "RGBA":
            bg.paste(img, mask=img.split()[3])
        else:
            bg.paste(img.convert("RGBA"))

        photo = ImageTk.PhotoImage(bg.convert("RGB"))
        _mem_cache[key] = photo
        return photo
    except Exception:
        return None


def _get_cached_png(svg_path, width):
    """
    Return path to a PNG thumbnail, generating it via Inkscape if needed.
    PNGs are stored in a temp dir and reused across app sessions.
    """
    os.makedirs(_png_cache_dir, exist_ok=True)

    # Cache key: base name + mtime + width
    try:
        mtime = int(os.path.getmtime(svg_path))
    except OSError:
        return None

    base = os.path.splitext(os.path.basename(svg_path))[0]
    png_name = "%s_%d_%d.png" % (base, mtime, width)
    png_path = os.path.join(_png_cache_dir, png_name)

    if os.path.exists(png_path):
        return png_path

    # Ask Inkscape to export a PNG at the requested width
    try:
        from autokey_core import _find_tool
        inkscape = _find_tool("inkscape")
        subprocess.check_call(
            [
                inkscape,
                "--export-type=png",
                "--export-filename=%s" % png_path,
                "--export-width=%d" % width,
                svg_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return png_path if os.path.exists(png_path) else None
    except Exception:
        return None


def is_available():
    """Return True if Pillow is installed (Inkscape is checked lazily per-render)."""
    return _pillow_available
