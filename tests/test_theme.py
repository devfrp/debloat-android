#!/usr/bin/env python3
"""Thème : palettes claire et sombre, apparence mémorisée."""
import os
import sys
import tempfile
import unittest
import unittest.mock as mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import theme  # noqa: E402


class Palettes(unittest.TestCase):
    def test_memes_couleurs_dans_les_deux_modes(self):
        self.assertEqual(set(theme.PALETTES["light"]), set(theme.PALETTES["dark"]))

    def test_resolution(self):
        self.assertEqual(theme.resolve("dark"), "dark")
        self.assertEqual(theme.resolve("light"), "light")
        self.assertEqual(theme.resolve("n'importe quoi"), "light")
        with mock.patch.object(theme, "system_prefers_dark", return_value=True):
            self.assertEqual(theme.resolve("auto"), "dark")
        with mock.patch.object(theme, "system_prefers_dark", return_value=False):
            self.assertEqual(theme.resolve("auto"), "light")


@unittest.skipIf(sys.platform in ("win32", "darwin"), "chemin XDG")
class ApparenceMemorisee(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="debloat_theme_")
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self._tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_auto_par_defaut(self):
        self.assertEqual(theme.stored_mode(), "auto")

    def test_aller_retour(self):
        theme.save_mode("dark")
        self.assertEqual(theme.stored_mode(), "dark")

    def test_fichier_illisible(self):
        path = theme._prefs_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{pas du json")
        self.assertEqual(theme.stored_mode(), "auto")


if __name__ == "__main__":
    unittest.main()
