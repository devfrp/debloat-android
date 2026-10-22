#!/usr/bin/env python3
"""Tests de la table de chaînes bilingue language.py (sans serveur X)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import language                     # noqa: E402
import bloat_db                     # noqa: E402


class LanguageTable(unittest.TestCase):
    def setUp(self):
        language.set_lang("fr")
        self.addCleanup(language.set_lang, "fr")

    def test_default_is_french(self):
        self.assertEqual(language.get_lang(), "fr")
        self.assertEqual(language.t("device.none"), "Aucun appareil")
        self.assertEqual(language.t("btn.scan"), "Scanner les applications")

    def test_english_switch(self):
        language.set_lang("en")
        self.assertEqual(language.get_lang(), "en")
        self.assertEqual(language.t("device.none"), "No device")
        self.assertEqual(language.t("btn.scan"), "Scan apps")
        self.assertEqual(language.t("btn.uninstall", n=3), "Uninstall selection (3)")
        self.assertEqual(language.t("status.loaded", n=254, sel=2),
                         "254 apps loaded — selection: 2 — "
                         "click a row to check/uncheck, hover = note, "
                         "double-click = details.")

    def test_format_keeps_working_in_french(self):
        self.assertEqual(language.t("btn.uninstall", n=7),
                         "Désinstaller la sélection (7)")
        self.assertIn("ÉCHEC", language.t("uninstall.fail_log", pkg="x.y", out="z"))

    def test_risk_text_french(self):
        self.assertEqual(language.risk_text("safe"), "sûre")
        self.assertEqual(language.risk_text("unknown"), "avancée (non listée)")

    def test_risk_text_english(self):
        language.set_lang("en")
        self.assertEqual(language.risk_text("safe"), "safe")
        self.assertEqual(language.risk_text("forbidden"), "protected (locked)")

    def test_risk_unknown_value_returned_verbatim(self):
        self.assertEqual(language.risk_text("nimporte"), "nimporte")

    def test_unknown_lang_falls_back_to_french(self):
        language.set_lang("de")
        self.assertEqual(language.get_lang(), "fr")
        self.assertEqual(language.t("device.none"), "Aucun appareil")

    def test_unknown_key_returns_key_as_is(self):
        self.assertEqual(language.t("cle.inexistante"), "cle.inexistante")

    def test_both_languages_define_the_same_keys(self):
        self.assertTrue(language.STRINGS)
        # chaque clé existe dans les deux langues
        for key, pair in language.STRINGS.items():
            self.assertIn("fr", pair, key)
            self.assertIn("en", pair, key)

    def test_risk_table_covers_every_risk(self):
        expected = {
            bloat_db.RISK_SAFE: ("sûre", "safe"),
            bloat_db.RISK_ADVANCED: ("avancée", "advanced"),
            bloat_db.RISK_UNKNOWN: ("avancée (non listée)", "advanced (unlisted)"),
            bloat_db.RISK_FORBIDDEN: ("protégée (verrouillée)", "protected (locked)"),
        }
        for risk, (fr, env) in expected.items():
            language.set_lang("fr")
            self.assertEqual(language.risk_text(risk), fr)
            language.set_lang("en")
            self.assertEqual(language.risk_text(risk), env)


if __name__ == "__main__":
    unittest.main()
