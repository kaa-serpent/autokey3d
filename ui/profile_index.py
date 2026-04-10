"""
ProfileIndex — loads and saves profiles.json.

Parses existing .scad files on first run to build the index.
All paths in the index are relative to BASE_DIR (the project root).
"""

import json
import os
import re


class ProfileIndex:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self._json_path = os.path.join(base_dir, "profiles.json")
        self.profiles = []
        self.systems = []

    def load(self):
        """Load from profiles.json, rebuilding from .scad files if missing."""
        if os.path.exists(self._json_path):
            with open(self._json_path, 'r') as f:
                data = json.load(f)
            self.profiles = data.get("profiles", [])
            self.systems = data.get("systems", [])
        else:
            self.rebuild_from_disk()

    def rebuild_from_disk(self):
        """Walk profiles/ and definitions/, parse .scad files, write profiles.json."""
        self.profiles = []
        self.systems = []

        profiles_dir = os.path.join(self.base_dir, "profiles")
        for fname in sorted(os.listdir(profiles_dir)):
            if not fname.endswith(".scad"):
                continue
            name = fname[:-5]  # strip .scad
            scad_path = os.path.join(profiles_dir, fname)
            entry = self._parse_profile_scad(scad_path, name)
            if entry:
                self.profiles.append(entry)

        defs_dir = os.path.join(self.base_dir, "definitions")
        for fname in sorted(os.listdir(defs_dir)):
            if not fname.endswith(".scad"):
                continue
            name = fname[:-5]
            scad_path = os.path.join(defs_dir, fname)
            entry = self._parse_system_scad(scad_path, name)
            if entry:
                self.systems.append(entry)

        self.save()

    def _parse_profile_scad(self, scad_path, name):
        """Return a profile dict parsed from a .scad file, or None on failure."""
        with open(scad_path, 'r') as f:
            content = f.read()

        tol = None
        ph_base = None
        ph_has_tol = False
        khcx = None
        khcz = None
        thin_handle = False
        match_handle = False

        for line in content.splitlines():
            # tol = 0.2;  or  tol=0.2;
            m = re.match(r'\s*tol\s*=\s*([\d.]+)\s*;', line)
            if m:
                tol = float(m.group(1))
                continue

            # ph=8.25 + 2*tol;
            m = re.match(r'\s*ph\s*=\s*([\d.]+)\s*\+\s*2\s*\*\s*tol\s*;', line)
            if m:
                ph_base = float(m.group(1))
                ph_has_tol = True
                continue

            # ph=8.75;  (no + 2*tol)
            m = re.match(r'\s*ph\s*=\s*([\d.]+)\s*;', line)
            if m:
                ph_base = float(m.group(1))
                ph_has_tol = False
                continue

            # khcx=2.5;
            m = re.match(r'\s*khcx\s*=\s*([\d.]+)\s*;', line)
            if m:
                khcx = float(m.group(1))
                continue

            # khcz=7;
            m = re.match(r'\s*khcz\s*=\s*([\d.]+)\s*;', line)
            if m:
                khcz = float(m.group(1))
                continue

            if re.search(r'\bthin_handle\s*=\s*true', line):
                thin_handle = True

            if re.search(r'\bmatch_handle\s*=\s*true', line):
                match_handle = True

        if tol is None or ph_base is None:
            return None

        # Build relative paths
        svg_rel = "profiles/%s.svg" % name
        scad_rel = "profiles/%s.scad" % name
        dxf_rel = "profiles/%s.dxf" % name

        return {
            "name": name,
            "svg_path": svg_rel,
            "scad_path": scad_rel,
            "dxf_path": dxf_rel,
            "tol": tol,
            "ph_base": ph_base,
            "ph_has_tol": ph_has_tol,
            "khcx": khcx,
            "khcz": khcz,
            "thin_handle": thin_handle,
            "match_handle": match_handle,
            "default_system": None,
        }

    def _parse_system_scad(self, scad_path, name):
        """Return a system dict parsed from a .scad file, or None on failure."""
        with open(scad_path, 'r') as f:
            content = f.read()

        kl = None
        aspace = None
        pinspace = None
        hcut_offset = None
        cutspace = None
        cutangle = None
        platspace = None

        for line in content.splitlines():
            m = re.match(r'\s*kl\s*=\s*([\d.]+)\s*;', line)
            if m:
                kl = float(m.group(1))
                continue

            # aspace = 4.42;  (not aspaces)
            m = re.match(r'\s*aspace\s*=\s*([\d.]+)\s*;', line)
            if m:
                aspace = float(m.group(1))
                continue

            m = re.match(r'\s*pinspace\s*=\s*([\d.]+)\s*;', line)
            if m:
                pinspace = float(m.group(1))
                continue

            # hcut = ph - 2*tol - 4.66;  (capture trailing offset)
            m = re.match(r'\s*hcut\s*=\s*ph\s*-\s*2\s*\*\s*tol\s*-\s*([\d.]+)', line)
            if m:
                hcut_offset = float(m.group(1))
                continue

            m = re.match(r'\s*cutspace\s*=\s*([\d.]+)', line)
            if m:
                cutspace = float(m.group(1))
                continue

            m = re.match(r'\s*cutangle\s*=\s*([\d.]+)', line)
            if m:
                cutangle = float(m.group(1))
                continue

            m = re.match(r'\s*platspace\s*=\s*([\d.]+)', line)
            if m:
                platspace = float(m.group(1))
                continue

        if kl is None:
            return None

        return {
            "name": name,
            "scad_path": "definitions/%s.scad" % name,
            "kl": kl,
            "aspace": aspace,
            "pinspace": pinspace,
            "hcut_offset": hcut_offset,
            "cutspace": cutspace,
            "cutangle": cutangle,
            "platspace": platspace,
        }

    def save(self):
        """Write profiles.json to disk."""
        with open(self._json_path, 'w') as f:
            json.dump({"profiles": self.profiles, "systems": self.systems}, f, indent=2)

    def set_profile_default_system(self, profile_name, system_name):
        """Persist a default system association for a profile."""
        for p in self.profiles:
            if p["name"] == profile_name:
                p["default_system"] = system_name
                break
        self.save()

    def add_profile(self, entry):
        self.profiles.append(entry)
        self.save()

    def add_system(self, entry):
        self.systems.append(entry)
        self.save()
