#!/usr/bin/env python3
"""Tests du module backup : atomicité, quarantaine, portabilité du nom."""
import json
import os
import tempfile
import unittest

import backup as bkp
def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TempDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="debloat_test_")
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)


class SafeFilename(TempDir):
    def test_wifi_serial(self):
        # `:` interdit sous Windows / NTFS
        self.assertEqual(bkp.safe_filename("127.0.0.1:5555"), "127.0.0.1_5555")

    def test_odd_chars(self):
        got = bkp.safe_filename("a/b\\c d:e*f?g<>|")
        self.assertFalse(any(ch in got for ch in r"/\\ :*?<>|"))

    def test_empty_fallback(self):
        self.assertEqual(bkp.safe_filename("///"), "inconnu")
        self.assertEqual(bkp.safe_filename(""), "inconnu")

    def test_normal_serial_untouched(self):
        self.assertEqual(bkp.safe_filename("8021FAJD910"), "8021FAJD910")


class AppendBackup(TempDir):
    def test_fresh_append(self):
        path = bkp.backup_path("SER", self.dir)
        ok, msg = bkp.append_backup(path, "SER", "Pixel Test", "com.a.b", "system")
        self.assertTrue(ok, msg)
        self.assertEqual(msg, "")
        data = _load(path)
        self.assertEqual(data["serial"], "SER")
        self.assertEqual(data["device"], "Pixel Test")
        self.assertEqual(len(data["history"]), 1)
        self.assertEqual(data["history"][0]["package"], "com.a.b")
        self.assertEqual(data["history"][0]["type"], "system")

    def test_dedup_and_reorder(self):
        path = bkp.backup_path("SER", self.dir)
        for pkg in ("com.a.b", "com.c.d", "com.a.b"):
            ok, _ = bkp.append_backup(path, "SER", "Pixel", pkg, "system")
            self.assertTrue(ok)
        data = _load(path)
        self.assertEqual([h["package"] for h in data["history"]],
                         ["com.a.b", "com.c.d"])

    def test_mixed_types_kept(self):
        path = bkp.backup_path("SER", self.dir)
        bkp.append_backup(path, "SER", "d", "com.sys", "system")
        bkp.append_backup(path, "SER", "d", "org.user", "user")
        ok, _ = bkp.append_backup(path, "SER", "d", "com.sys", "system")
        self.assertTrue(ok)
        data = _load(path)
        types = {h["package"]: h["type"] for h in data["history"]}
        self.assertEqual(types, {"com.sys": "system", "org.user": "user"})

    def test_no_tmp_leftovers(self):
        path = bkp.backup_path("SER", self.dir)
        bkp.append_backup(path, "SER", "d", "com.x", "system")
        files = os.listdir(self.dir)
        self.assertNotIn("SER.json.tmp", files)

    def test_atomic_content_never_partial(self):
        # le tmp reste utilisable même si on nous coupe au milieu (par simulation)
        path = bkp.backup_path("SER", self.dir)
        bkp.append_backup(path, "SER", "d", "com.a", "system")
        before = _load(path)
        self.assertEqual(before["history"][0]["package"], "com.a")


class CorruptBackup(TempDir):
    def test_corrupt_is_quarantined_not_erased(self):
        path = bkp.backup_path("SER", self.dir)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{ pas du json ]")
        ok, msg = bkp.append_backup(path, "SER", "d", "com.new", "system")
        self.assertTrue(ok, msg)
        self.assertIn("quarantaine", msg)
        data = _load(path)
        self.assertEqual([h["package"] for h in data["history"]], ["com.new"])
        quarantined = [f for f in os.listdir(self.dir) if ".corrupt-" in f]
        self.assertEqual(len(quarantined), 1)
        with open(os.path.join(self.dir, quarantined[0]), encoding="utf-8") as fh:
            self.assertIn("pas du json", fh.read())

    def test_wrong_structure_is_quarantined(self):
        path = bkp.backup_path("SER", self.dir)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(["un", "tableau", "pas", "dict"], fh)
        ok, msg = bkp.append_backup(path, "SER", "d", "com.new", "system")
        self.assertTrue(ok, msg)
        self.assertIn("quarantaine", msg)
        data = _load(path)
        self.assertEqual(data["history"][0]["package"], "com.new")

    def test_missing_file_starts_clean(self):
        path = bkp.backup_path("SER", self.dir)
        ok, msg = bkp.append_backup(path, "SER", "d", "com.a", "system")
        self.assertTrue(ok)
        self.assertEqual(msg, "")


class ReadList(TempDir):
    def test_read_backup_ok(self):
        path = bkp.backup_path("SER", self.dir)
        bkp.append_backup(path, "SER", "d", "com.a", "system")
        data, err = bkp.read_backup(path)
        self.assertIsNone(err)
        self.assertEqual(bkp.entries(data)[0]["package"], "com.a")

    def test_read_backup_missing(self):
        data, err = bkp.read_backup(os.path.join(self.dir, "nope.json"))
        self.assertIsNone(data)
        self.assertTrue(err)

    def test_entries_filters_garbage(self):
        data = {"history": [{"package": "ok", "type": "system"},
                            {"type": "system"},  # pas de package
                            "invalide"]}          # pas un dict
        self.assertEqual([e["package"] for e in bkp.entries(data)], ["ok"])

    def test_list_recent_first(self):
        import time
        p1 = bkp.backup_path("A", self.dir)
        bkp.append_backup(p1, "A", "d", "com.a", "system")
        time.sleep(0.02)
        p2 = bkp.backup_path("B", self.dir)
        bkp.append_backup(p2, "B", "d", "com.b", "system")
        files = bkp.list_backup_files(self.dir)
        self.assertEqual(os.path.basename(files[0]), "B.json")


if __name__ == "__main__":
    unittest.main()
