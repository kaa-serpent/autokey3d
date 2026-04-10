"""
AutoKey3D UI tests.

Drives the Tkinter UI programmatically — no screen interaction required.
Run with:  python -m pytest tests/  (or python -m unittest tests.test_app)
"""

import json
import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is on the path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ui.profile_index import ProfileIndex
from ui.home_screen import HomeScreen
from ui.profile_detail import ProfileDetail
from ui.add_profile import AddProfile
from ui.add_system import AddSystem

# Single Tk root shared across all test classes — Tkinter supports only one per process.
_ROOT = tk.Tk()
_ROOT.withdraw()

# ---------------------------------------------------------------------------
# Minimal sample .scad content used across tests
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_temp_project():
    """
    Return a temp directory that looks like the project root.
    Caller is responsible for cleanup.
    """
    d = tempfile.mkdtemp(prefix="autokey3d_test_")
    os.makedirs(os.path.join(d, "profiles"))
    os.makedirs(os.path.join(d, "definitions"))
    os.makedirs(os.path.join(d, "branding"))

    # Two profiles
    for name, content in [("TEST-P1", PROFILE_SCAD), ("TEST-P2", PROFILE_SCAD_THIN),
                           ("TEST-P3", PROFILE_SCAD_NO_TOL_IN_PH)]:
        with open(os.path.join(d, "profiles", "%s.scad" % name), "w") as f:
            f.write(content)
        # Stub SVG
        with open(os.path.join(d, "profiles", "%s.svg" % name), "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>')

    # One system
    with open(os.path.join(d, "definitions", "TEST-SYS1.scad"), "w") as f:
        f.write(SYSTEM_SCAD)

    return d


class _MockApp:
    """Minimal stand-in for ui.app.App used by screen tests."""
    def __init__(self, root, base_dir, profile_index):
        self.root = root
        self.base_dir = base_dir
        self.profile_index = profile_index
        self.last_screen = None
        self.last_screen_kwargs = {}

    def show_screen(self, name, **kwargs):
        self.last_screen = name
        self.last_screen_kwargs = kwargs

    def navigate_back(self):
        self.show_screen("home")


# ---------------------------------------------------------------------------
# ProfileIndex tests  (no Tkinter)
# ---------------------------------------------------------------------------

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
        # Reload
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

        # Remove all .scad files — load() should still work from JSON
        for f in os.listdir(os.path.join(self.base_dir, "profiles")):
            if f.endswith(".scad"):
                os.remove(os.path.join(self.base_dir, "profiles", f))

        idx2 = ProfileIndex(self.base_dir)
        idx2.load()
        self.assertEqual(len(idx2.profiles), 3)


# ---------------------------------------------------------------------------
# Base class for Tkinter screen tests
# ---------------------------------------------------------------------------

class TkTestCase(unittest.TestCase):
    """Sets up a hidden Tk root and a temp project directory."""

    @classmethod
    def setUpClass(cls):
        cls.root = _ROOT  # reuse the single module-level root

    def setUp(self):
        self.base_dir = _make_temp_project()
        self.index = ProfileIndex(self.base_dir)
        self.index.rebuild_from_disk()
        self.app = _MockApp(self.root, self.base_dir, self.index)

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def pump(self):
        """Process pending Tkinter events."""
        self.root.update()
        self.root.update_idletasks()

    def _card_names(self, home):
        """Return the text of all name labels in the card grid."""
        names = []
        for card in home._grid_frame.winfo_children():
            for child in card.winfo_children():
                text = child.cget("text")
                # Name labels are bold and contain the profile name
                if text and text not in ("[SVG]",):
                    names.append(text)
        return names


# ---------------------------------------------------------------------------
# HomeScreen tests
# ---------------------------------------------------------------------------

class TestHomeScreen(TkTestCase):

    def _make_screen(self):
        screen = HomeScreen(self.root, self.app)
        screen.refresh()
        self.pump()
        return screen

    def test_shows_all_profiles(self):
        screen = self._make_screen()
        names = self._card_names(screen)
        self.assertIn("TEST-P1", names)
        self.assertIn("TEST-P2", names)
        self.assertIn("TEST-P3", names)

    def test_search_filter_reduces_cards(self):
        screen = self._make_screen()
        screen._search_var.set("TEST-P1")
        self.pump()
        names = self._card_names(screen)
        self.assertIn("TEST-P1", names)
        self.assertNotIn("TEST-P2", names)

    def test_search_filter_case_insensitive(self):
        screen = self._make_screen()
        screen._search_var.set("test-p2")
        self.pump()
        names = self._card_names(screen)
        self.assertIn("TEST-P2", names)
        self.assertNotIn("TEST-P1", names)

    def test_clear_search_restores_all(self):
        screen = self._make_screen()
        screen._search_var.set("TEST-P1")
        self.pump()
        screen._search_var.set("")
        self.pump()
        names = self._card_names(screen)
        self.assertEqual(len(names), 3)

    def test_search_no_match_shows_empty_grid(self):
        screen = self._make_screen()
        screen._search_var.set("ZZZNOMATCH")
        self.pump()
        names = self._card_names(screen)
        self.assertEqual(names, [])

    def test_click_card_navigates_to_detail(self):
        screen = self._make_screen()
        # Find any card and simulate click
        card = screen._grid_frame.winfo_children()[0]
        card.event_generate("<Button-1>")
        self.pump()
        self.assertEqual(self.app.last_screen, "detail")
        self.assertIn("profile", self.app.last_screen_kwargs)

    def test_refresh_reloads_profiles(self):
        screen = self._make_screen()
        # Add a new profile to index and refresh
        self.index.profiles.append({
            "name": "EXTRA-P", "svg_path": "profiles/EXTRA-P.svg",
            "scad_path": "profiles/EXTRA-P.scad", "dxf_path": "profiles/EXTRA-P.dxf",
            "tol": 0.0, "ph_base": 8.0, "ph_has_tol": True,
            "khcx": None, "khcz": None, "thin_handle": False, "match_handle": False,
        })
        screen.refresh()
        self.pump()
        names = self._card_names(screen)
        self.assertIn("EXTRA-P", names)


# ---------------------------------------------------------------------------
# ProfileDetail tests
# ---------------------------------------------------------------------------

SAMPLE_PROFILE = {
    "name": "TEST-P1",
    "svg_path": "profiles/TEST-P1.svg",
    "scad_path": "profiles/TEST-P1.scad",
    "dxf_path": "profiles/TEST-P1.dxf",
    "tol": 0.0,
    "ph_base": 8.25,
    "ph_has_tol": True,
    "khcx": None,
    "khcz": None,
    "thin_handle": False,
    "match_handle": False,
}


class TestProfileDetail(TkTestCase):

    def _make_screen(self, profile=None):
        screen = ProfileDetail(self.root, self.app)
        screen.refresh(profile=profile or SAMPLE_PROFILE)
        self.pump()
        return screen

    def test_title_label(self):
        screen = self._make_screen()
        self.assertEqual(screen._title_label.cget("text"), "TEST-P1")

    def test_metadata_tol(self):
        screen = self._make_screen()
        self.assertEqual(screen._meta_labels["Tolerance (tol)"].cget("text"), "0.0")

    def test_metadata_ph_with_tol(self):
        screen = self._make_screen()
        # ph_has_tol=True → should show "8.25 + 2×tol"
        text = screen._meta_labels["Height base (ph)"].cget("text")
        self.assertIn("8.25", text)
        self.assertIn("tol", text)

    def test_metadata_optional_fields_dash(self):
        screen = self._make_screen()
        self.assertEqual(screen._meta_labels["Handle X (khcx)"].cget("text"), "—")
        self.assertEqual(screen._meta_labels["Handle Z (khcz)"].cget("text"), "—")

    def test_metadata_thin_handle_no(self):
        screen = self._make_screen()
        self.assertEqual(screen._meta_labels["Thin handle"].cget("text"), "no")

    def test_metadata_thin_handle_yes(self):
        profile = dict(SAMPLE_PROFILE, thin_handle=True, name="TEST-P2",
                       svg_path="profiles/TEST-P2.svg", scad_path="profiles/TEST-P2.scad")
        screen = self._make_screen(profile)
        self.assertEqual(screen._meta_labels["Thin handle"].cget("text"), "yes")

    def test_system_dropdown_populated(self):
        screen = self._make_screen()
        self.assertIn("TEST-SYS1", screen._system_combo["values"])

    def test_default_mode_is_blank(self):
        screen = self._make_screen()
        self.assertEqual(screen._mode_var.get(), "blank")

    def test_combo_entry_disabled_in_blank_mode(self):
        screen = self._make_screen()
        self.assertEqual(str(screen._combo_entry.cget("state")), "disabled")

    def test_combo_entry_enabled_in_key_mode(self):
        screen = self._make_screen()
        screen._mode_var.set("key")
        screen._on_mode_change()
        self.pump()
        self.assertEqual(str(screen._combo_entry.cget("state")), "normal")

    def test_combo_entry_disabled_again_in_bumpkey(self):
        screen = self._make_screen()
        screen._mode_var.set("key")
        screen._on_mode_change()
        screen._mode_var.set("bumpkey")
        screen._on_mode_change()
        self.pump()
        self.assertEqual(str(screen._combo_entry.cget("state")), "disabled")

    @patch("tkinter.messagebox.showerror")
    def test_generate_key_mode_requires_combination(self, mock_err):
        screen = self._make_screen()
        screen._mode_var.set("key")
        screen._on_mode_change()
        screen._combo_var.set("")  # empty combination
        screen._on_generate()
        self.pump()
        mock_err.assert_called_once()
        self.assertIn("combination", mock_err.call_args[0][1].lower())

    @patch("tkinter.messagebox.showerror")
    def test_generate_invalid_tol_override(self, mock_err):
        screen = self._make_screen()
        screen._tol_var.set("not-a-number")
        screen._on_generate()
        self.pump()
        mock_err.assert_called_once()

    @patch("tkinter.messagebox.showerror")
    def test_generate_no_system_selected(self, mock_err):
        screen = self._make_screen()
        screen._system_var.set("")
        screen._on_generate()
        self.pump()
        mock_err.assert_called_once()

    @patch("tkinter.messagebox.showinfo")
    @patch("autokey_core.generate_key")
    def test_generate_blank_calls_generate_key(self, mock_gen, mock_info):
        screen = self._make_screen()
        screen._mode_var.set("blank")
        screen._on_generate()
        # Wait for the background thread
        self.root.after(200, lambda: None)
        self.pump()
        import time; time.sleep(0.3)
        self.pump()
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        self.assertEqual(kwargs["mode"], "blank")
        self.assertIsNone(kwargs["combination"])

    @patch("tkinter.messagebox.showinfo")
    @patch("autokey_core.generate_key")
    def test_generate_key_combination_passes_combo(self, mock_gen, mock_info):
        screen = self._make_screen()
        screen._mode_var.set("key")
        screen._on_mode_change()
        screen._combo_var.set("1,2,3,4,5")
        screen._on_generate()
        import time; time.sleep(0.3)
        self.pump()
        mock_gen.assert_called_once()
        _, kwargs = mock_gen.call_args
        self.assertEqual(kwargs["mode"], "key")
        self.assertEqual(kwargs["combination"], "1,2,3,4,5")

    @patch("tkinter.messagebox.showinfo")
    @patch("autokey_core.generate_key")
    def test_generate_tol_override_passed(self, mock_gen, mock_info):
        screen = self._make_screen()
        screen._tol_var.set("0.15")
        screen._on_generate()
        import time; time.sleep(0.3)
        self.pump()
        _, kwargs = mock_gen.call_args
        self.assertAlmostEqual(kwargs["tol_override"], 0.15)

    @patch("tkinter.messagebox.showerror")
    def test_generate_error_shows_dialog(self, mock_err):
        # Test the error handler directly — root.after() can't be called
        # from background threads without mainloop() running in tests.
        screen = self._make_screen()
        screen._on_error("openscad not found")
        self.pump()
        mock_err.assert_called_once()
        self.assertIn("openscad not found", mock_err.call_args[0][1])


# ---------------------------------------------------------------------------
# AddProfile tests
# ---------------------------------------------------------------------------

class TestAddProfile(TkTestCase):

    def _make_screen(self):
        screen = AddProfile(self.root, self.app)
        screen.refresh()
        self.pump()
        return screen

    def _fill_valid(self, screen, svg_path):
        screen._fields["name"].set("MY-LOCK1")
        screen._svg_var.set(svg_path)
        screen._fields["tol"].set("0.0")
        screen._fields["ph_base"].set("8.5")

    @patch("tkinter.messagebox.showerror")
    def test_empty_name_rejected(self, mock_err):
        screen = self._make_screen()
        screen._on_save()
        mock_err.assert_called_once()

    @patch("tkinter.messagebox.showerror")
    def test_invalid_name_chars_rejected(self, mock_err):
        screen = self._make_screen()
        screen._fields["name"].set("bad name!")
        screen._on_save()
        mock_err.assert_called_once()

    @patch("tkinter.messagebox.showerror")
    def test_missing_svg_rejected(self, mock_err):
        screen = self._make_screen()
        screen._fields["name"].set("MY-LOCK1")
        screen._svg_var.set("/nonexistent/file.svg")
        screen._fields["tol"].set("0.0")
        screen._fields["ph_base"].set("8.5")
        screen._on_save()
        mock_err.assert_called_once()

    @patch("tkinter.messagebox.showerror")
    def test_invalid_tol_rejected(self, mock_err):
        screen = self._make_screen()
        svg = os.path.join(self.base_dir, "profiles", "TEST-P1.svg")
        screen._fields["name"].set("MY-LOCK1")
        screen._svg_var.set(svg)
        screen._fields["tol"].set("abc")
        screen._fields["ph_base"].set("8.5")
        screen._on_save()
        mock_err.assert_called_once()

    @patch("tkinter.messagebox.showerror")
    def test_invalid_ph_rejected(self, mock_err):
        screen = self._make_screen()
        svg = os.path.join(self.base_dir, "profiles", "TEST-P1.svg")
        screen._fields["name"].set("MY-LOCK1")
        screen._svg_var.set(svg)
        screen._fields["tol"].set("0.0")
        screen._fields["ph_base"].set("not-a-number")
        screen._on_save()
        mock_err.assert_called_once()

    @patch("autokey_core.svg_to_dxf")
    @patch("tkinter.messagebox.showinfo")
    def test_valid_form_saves_scad(self, mock_info, mock_dxf):
        screen = self._make_screen()
        svg = os.path.join(self.base_dir, "profiles", "TEST-P1.svg")
        self._fill_valid(screen, svg)
        screen._on_save()
        self.pump()
        scad_path = os.path.join(self.base_dir, "profiles", "MY-LOCK1.scad")
        self.assertTrue(os.path.exists(scad_path))

    @patch("autokey_core.svg_to_dxf")
    @patch("tkinter.messagebox.showinfo")
    def test_valid_form_adds_to_index(self, mock_info, mock_dxf):
        screen = self._make_screen()
        svg = os.path.join(self.base_dir, "profiles", "TEST-P1.svg")
        self._fill_valid(screen, svg)
        screen._on_save()
        self.pump()
        names = [p["name"] for p in self.index.profiles]
        self.assertIn("MY-LOCK1", names)

    @patch("autokey_core.svg_to_dxf")
    @patch("tkinter.messagebox.showinfo")
    def test_valid_form_navigates_home(self, mock_info, mock_dxf):
        screen = self._make_screen()
        svg = os.path.join(self.base_dir, "profiles", "TEST-P1.svg")
        self._fill_valid(screen, svg)
        screen._on_save()
        self.pump()
        self.assertEqual(self.app.last_screen, "home")

    @patch("autokey_core.svg_to_dxf")
    @patch("tkinter.messagebox.showinfo")
    def test_scad_content_correct(self, mock_info, mock_dxf):
        screen = self._make_screen()
        svg = os.path.join(self.base_dir, "profiles", "TEST-P1.svg")
        self._fill_valid(screen, svg)
        screen._fields["tol"].set("0.2")
        screen._fields["ph_base"].set("7.5")
        screen._thin_handle_var.set(True)
        screen._on_save()
        self.pump()
        scad_path = os.path.join(self.base_dir, "profiles", "MY-LOCK1.scad")
        content = open(scad_path).read()
        self.assertIn("tol = 0.2", content)
        self.assertIn("ph=7.5 + 2*tol", content)
        self.assertIn("thin_handle=true", content)

    @patch("autokey_core.svg_to_dxf")
    @patch("tkinter.messagebox.showinfo")
    def test_optional_khcx_written_when_set(self, mock_info, mock_dxf):
        screen = self._make_screen()
        svg = os.path.join(self.base_dir, "profiles", "TEST-P1.svg")
        self._fill_valid(screen, svg)
        screen._fields["khcx"].set("2.5")
        screen._on_save()
        self.pump()
        scad_path = os.path.join(self.base_dir, "profiles", "MY-LOCK1.scad")
        content = open(scad_path).read()
        self.assertIn("khcx=2.5", content)

    @patch("autokey_core.svg_to_dxf")
    @patch("tkinter.messagebox.showinfo")
    def test_dxf_generated_on_save(self, mock_info, mock_dxf):
        screen = self._make_screen()
        svg = os.path.join(self.base_dir, "profiles", "TEST-P1.svg")
        self._fill_valid(screen, svg)
        screen._on_save()
        self.pump()
        expected_dxf = os.path.join(self.base_dir, "profiles", "MY-LOCK1.dxf")
        mock_dxf.assert_called_once_with(
            os.path.join(self.base_dir, "profiles", "MY-LOCK1.svg"),
            expected_dxf,
        )

    def test_refresh_clears_form(self):
        screen = self._make_screen()
        screen._fields["name"].set("SOMETHING")
        screen._fields["tol"].set("0.9")
        screen.refresh()
        self.pump()
        self.assertEqual(screen._fields["name"].get(), "")
        self.assertEqual(screen._fields["tol"].get(), "0.0")


# ---------------------------------------------------------------------------
# AddSystem tests
# ---------------------------------------------------------------------------

class TestAddSystem(TkTestCase):

    def _make_screen(self):
        screen = AddSystem(self.root, self.app)
        screen.refresh()
        self.pump()
        return screen

    def _fill_valid(self, screen):
        screen._fields["name"].set("MY-SYS1")
        screen._fields["kl"].set("30.0")
        screen._fields["aspace"].set("5.0")
        screen._fields["pinspace"].set("3.5")
        screen._fields["hcut_offset"].set("4.0")
        screen._fields["cutspace"].set("0.5")
        screen._fields["cutangle"].set("90")
        screen._fields["platspace"].set("0.3")

    @patch("tkinter.messagebox.showerror")
    def test_empty_name_rejected(self, mock_err):
        screen = self._make_screen()
        screen._on_save()
        mock_err.assert_called_once()

    @patch("tkinter.messagebox.showerror")
    def test_non_numeric_kl_rejected(self, mock_err):
        screen = self._make_screen()
        screen._fields["name"].set("MY-SYS1")
        screen._fields["kl"].set("bad")
        screen._on_save()
        mock_err.assert_called_once()

    @patch("tkinter.messagebox.showinfo")
    def test_valid_form_saves_scad(self, mock_info):
        screen = self._make_screen()
        self._fill_valid(screen)
        screen._on_save()
        self.pump()
        scad_path = os.path.join(self.base_dir, "definitions", "MY-SYS1.scad")
        self.assertTrue(os.path.exists(scad_path))

    @patch("tkinter.messagebox.showinfo")
    def test_valid_form_adds_to_index(self, mock_info):
        screen = self._make_screen()
        self._fill_valid(screen)
        screen._on_save()
        self.pump()
        names = [s["name"] for s in self.index.systems]
        self.assertIn("MY-SYS1", names)

    @patch("tkinter.messagebox.showinfo")
    def test_valid_form_navigates_home(self, mock_info):
        screen = self._make_screen()
        self._fill_valid(screen)
        screen._on_save()
        self.pump()
        self.assertEqual(self.app.last_screen, "home")

    @patch("tkinter.messagebox.showinfo")
    def test_scad_content_correct(self, mock_info):
        screen = self._make_screen()
        self._fill_valid(screen)
        screen._on_save()
        self.pump()
        scad_path = os.path.join(self.base_dir, "definitions", "MY-SYS1.scad")
        content = open(scad_path).read()
        self.assertIn("kl=30.0", content)
        self.assertIn("aspace = 5.0", content)
        self.assertIn("hcut = ph - 2*tol - 4.0", content)
        self.assertIn("cutangle = 90.0", content)

    def test_refresh_clears_fields(self):
        screen = self._make_screen()
        screen._fields["name"].set("SOMETHING")
        screen._fields["kl"].set("99")
        screen.refresh()
        self.pump()
        self.assertEqual(screen._fields["name"].get(), "")
        self.assertEqual(screen._fields["kl"].get(), "")


if __name__ == "__main__":
    unittest.main()
