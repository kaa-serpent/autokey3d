#!/usr/bin/env python
"""
AutoKey3D — Tkinter UI entry point.

Usage:
    python autokey_ui.py
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox

# Ensure the project root is on the path so ui/ and autokey_core can import cleanly
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, BASE_DIR)

from ui.app import App


def main():
    root = tk.Tk()
    root.title("AutoKey3D")
    root.minsize(700, 520)
    root.geometry("880x600")

    try:
        app = App(root, BASE_DIR)
    except Exception as exc:
        messagebox.showerror("Startup error", str(exc))
        return 1

    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
