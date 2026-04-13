#!/bin/sh
set -e

# Start a virtual framebuffer so OpenSCAD and Inkscape have a display to
# connect to. Both tools require one on Linux even for headless/batch use.
Xvfb :99 -screen 0 1024x768x24 -nolisten tcp &

exec /venv/bin/python3 web_app.py
