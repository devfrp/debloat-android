#!/usr/bin/env python3
"""Tests de la base de bloat : intégrité et cohérence."""
import unittest

import bloat_db

RISK_DB = {bloat_db.RISK_SAFE, bloat_db.RISK_ADVANCED}


class BloatDbIntegrity(unittest.TestCase):
    def test_db_not_empty(self):
        self.assertGreaterEqual(len(bloat_db.BLOAT_DB), 100)

    def test_entries_shape(self):
        for pkg, entry in bloat_db.BLOAT_DB.items():
            self.assertEqual(len(entry), 3, f"{pkg}: forme attendue (risk, name, note)")
            risk, name, note = entry
            self.assertIn(risk, RISK_DB, f"{pkg}: risque invalide {risk!r}")
            self.assertTrue(name.strip(), f"{pkg}: nom vide")
            self.assertEqual(name, name.strip(), f"{pkg}: espaces autour du nom")
            self.assertIsInstance(note, str)
            self.assertEqual(pkg, pkg.strip(), f"{pkg}: espaces autour de la clé")
            self.assertTrue(pkg.isascii(), f"{pkg}: clé non ASCII")

    def test_no_overlap_with_forbidden(self):
        overlap = set(bloat_db.BLOAT_DB) & set(bloat_db.FORBIDDEN)
        self.assertFalse(overlap, f"entrées à la fois bloat et interdites : {overlap}")

    def test_db_keys_not_protected_by_prefix(self):
        for pkg in bloat_db.BLOAT_DB:
            for prefix in bloat_db.FORBIDDEN_PREFIXES:
                self.assertFalse(
                    pkg.startswith(prefix),
                    f"{pkg} commence par le préfixe protégé {prefix!r}")

    def test_lookup_known(self):
        risk, name, note = bloat_db.lookup("com.facebook.appmanager")
        self.assertEqual(risk, bloat_db.RISK_SAFE)
        self.assertEqual(name, "Facebook App Manager")
        self.assertTrue(note)

    def test_lookup_advanced(self):
        risk, name, _ = bloat_db.lookup("com.netflix.mediaclient")
        self.assertEqual(risk, bloat_db.RISK_ADVANCED)
        self.assertEqual(name, "Netflix")

    def test_lookup_forbidden_exact(self):
        risk, _, _ = bloat_db.lookup("com.google.android.gms")
        self.assertEqual(risk, bloat_db.RISK_FORBIDDEN)

    def test_lookup_forbidden_by_prefix(self):
        # com.android.* et android.* : cœur d'Android
        for pkg in ("com.android.systemui", "com.android.chrome",
                    "com.android.providers.media", "android.autoinstallskey"):
            risk, _, note = bloat_db.lookup(pkg)
            self.assertEqual(risk, bloat_db.RISK_FORBIDDEN, pkg)
            self.assertTrue(note)

    def test_lookup_trichromelibrary_variants(self):
        for pkg in ("com.google.android.trichromelibrary",
                    "com.google.android.trichromelibrary_53160135"):
            risk, _, _ = bloat_db.lookup(pkg)
            self.assertEqual(risk, bloat_db.RISK_FORBIDDEN, pkg)

    def test_lookup_unknown(self):
        risk, label, note = bloat_db.lookup("org.paquet.totalement.inconnu")
        self.assertEqual(risk, bloat_db.RISK_UNKNOWN)
        self.assertEqual(label, "")
        self.assertEqual(note, "")

    def test_forbidden_entries_have_name(self):
        for pkg, (name, _note) in bloat_db.FORBIDDEN.items():
            self.assertTrue(name.strip(), f"{pkg}: nom interdit vide")

    def test_risk_constants_unique(self):
        risks = {"safe", "advanced", "forbidden", "unknown"}
        self.assertEqual({bloat_db.RISK_SAFE, bloat_db.RISK_ADVANCED,
                          bloat_db.RISK_FORBIDDEN, bloat_db.RISK_UNKNOWN}, risks)


if __name__ == "__main__":
    unittest.main()
