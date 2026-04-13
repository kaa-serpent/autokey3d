"""
AutoKey3D ProfileIndex tests.

Run with:  python -m pytest tests/
"""

import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from profile_index import ProfileIndex

# ---------------------------------------------------------------------------
# Minimal sample .scad content
# ---------------------------------------------------------------------------

PROFILE_SCAD = """\
tol = 0.0;
ph=8.25 + 2*tol;
profile_path = "profiles/TEST-P1.dxf"
"""

PROFILE_SCAD_THIN = """\
tol = 0.2;
ph=7.8 + 2*tol;
khcz=7;
thin_handle=true;
match_handle=true;
profile_path = "profiles/TEST-P2.dxf"
"""

PROFILE_SCAD_NO_TOL_IN_PH = """\
tol=0.2;
ph=8.75;
khcx=2.5;
profile_path = "profiles/TEST-P3.dxf"
"""

SYSTEM_SCAD = """\
kl=27;
aspace = 4.42;
pinspace = 4.0;
hcut = ph - 2*tol - 4.66;
cutspace = 0.44;
cutangle = 112;
platspace = 0.0;
"""


def _make_temp_project():
    d = tempfile.mkdtemp(prefix="autokey3d_test_")
    os.makedirs(os.path.join(d, "profiles"))
    os.makedirs(os.path.join(d, "definitions"))
    os.makedirs(os.path.join(d, "branding"))

    for name, content in [("TEST-P1", PROFILE_SCAD), ("TEST-P2", PROFILE_SCAD_THIN),
                           ("TEST-P3", PROFILE_SCAD_NO_TOL_IN_PH)]:
        with open(os.path.join(d, "profiles", "%s.scad" % name), "w") as f:
            f.write(content)
        with open(os.path.join(d, "profiles", "%s.svg" % name), "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>')

    with open(os.path.join(d, "definitions", "TEST-SYS1.scad"), "w") as f:
        f.write(SYSTEM_SCAD)

    return d


class TestProfileIndex(unittest.TestCase):

    def setUp(self):
        self.base_dir = _make_temp_project()

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_rebuild_finds_all_profiles(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        names = [p["name"] for p in idx.profiles]
        self.assertIn("TEST-P1", names)
        self.assertIn("TEST-P2", names)
        self.assertIn("TEST-P3", names)

    def test_rebuild_finds_system(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        names = [s["name"] for s in idx.systems]
        self.assertIn("TEST-SYS1", names)

    def test_profile_fields_standard(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        p = next(p for p in idx.profiles if p["name"] == "TEST-P1")
        self.assertAlmostEqual(p["tol"], 0.0)
        self.assertAlmostEqual(p["ph_base"], 8.25)
        self.assertTrue(p["ph_has_tol"])
        self.assertIsNone(p["khcx"])
        self.assertFalse(p["thin_handle"])

    def test_profile_fields_thin(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        p = next(p for p in idx.profiles if p["name"] == "TEST-P2")
        self.assertAlmostEqual(p["tol"], 0.2)
        self.assertAlmostEqual(p["khcz"], 7.0)
        self.assertTrue(p["thin_handle"])
        self.assertTrue(p["match_handle"])

    def test_profile_fields_no_tol_in_ph(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        p = next(p for p in idx.profiles if p["name"] == "TEST-P3")
        self.assertFalse(p["ph_has_tol"])
        self.assertAlmostEqual(p["ph_base"], 8.75)
        self.assertAlmostEqual(p["khcx"], 2.5)

    def test_system_fields(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        s = idx.systems[0]
        self.assertAlmostEqual(s["kl"], 27.0)
        self.assertAlmostEqual(s["aspace"], 4.42)
        self.assertAlmostEqual(s["pinspace"], 4.0)
        self.assertAlmostEqual(s["hcut_offset"], 4.66)
        self.assertAlmostEqual(s["cutspace"], 0.44)
        self.assertAlmostEqual(s["cutangle"], 112.0)
        self.assertAlmostEqual(s["platspace"], 0.0)

    def test_save_and_load_roundtrip(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        idx2 = ProfileIndex(self.base_dir)
        idx2.load()
        self.assertEqual(len(idx2.profiles), len(idx.profiles))
        self.assertEqual(len(idx2.systems), len(idx.systems))

    def test_add_profile_persists(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        entry = {"name": "NEW-P", "svg_path": "profiles/NEW-P.svg",
                 "scad_path": "profiles/NEW-P.scad", "dxf_path": "profiles/NEW-P.dxf",
                 "tol": 0.1, "ph_base": 9.0, "ph_has_tol": True,
                 "khcx": None, "khcz": None, "thin_handle": False, "match_handle": False}
        idx.add_profile(entry)

        idx2 = ProfileIndex(self.base_dir)
        idx2.load()
        names = [p["name"] for p in idx2.profiles]
        self.assertIn("NEW-P", names)

    def test_add_system_persists(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        entry = {"name": "NEW-SYS", "scad_path": "definitions/NEW-SYS.scad",
                 "kl": 30.0, "aspace": 5.0, "pinspace": 3.5, "hcut_offset": 4.0,
                 "cutspace": 0.5, "cutangle": 90.0, "platspace": 0.3}
        idx.add_system(entry)

        idx2 = ProfileIndex(self.base_dir)
        idx2.load()
        names = [s["name"] for s in idx2.systems]
        self.assertIn("NEW-SYS", names)

    def test_rebuild_creates_json(self):
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()
        self.assertTrue(os.path.exists(os.path.join(self.base_dir, "profiles.json")))

    def test_load_uses_existing_json(self):
        """load() reads profiles.json without touching .scad files."""
        idx = ProfileIndex(self.base_dir)
        idx.rebuild_from_disk()

        for f in os.listdir(os.path.join(self.base_dir, "profiles")):
            if f.endswith(".scad"):
                os.remove(os.path.join(self.base_dir, "profiles", f))

        idx2 = ProfileIndex(self.base_dir)
        idx2.load()
        self.assertEqual(len(idx2.profiles), 3)
