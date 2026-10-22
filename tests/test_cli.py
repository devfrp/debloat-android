#!/usr/bin/env python3
"""Tests du CLI : garde-fous, codes de retour, intégration backup."""
import contextlib
import io
import json
import os
import tempfile
import unittest

import bloat_db
import backup
import debloat_cli
from tests.helpers import FakeAdb, patch_adb
def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)

FAKE_SYS = ["com.facebook.appmanager",      # safe
            "com.netflix.mediaclient",      # advanced
            "com.paquet.inconnu.x",         # unknown
            "com.google.android.gms",       # forbidden
            "com.android.chrome"]           # forbidden (préfixe)
FAKE_USER = ["org.perso.app"]


class CliHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="debloat_cli_")
        self.addCleanup(self._tmp.cleanup)
        self.old_backup_dir = backup.BACKUP_DIR
        backup.BACKUP_DIR = self._tmp.name
        self.addCleanup(setattr, backup, "BACKUP_DIR", self.old_backup_dir)
        self.fake = FakeAdb(serial="123ABC", sys_pkgs=list(FAKE_SYS),
                            user_pkgs=list(FAKE_USER))
        self._patch = patch_adb(debloat_cli, self.fake)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = debloat_cli.main(list(argv))
            except SystemExit as exc:   # les erreurs d'usage/pick_adb sortent ainsi
                code = 0 if exc.code is None else int(exc.code)
        return code, out.getvalue(), err.getvalue()

    def backup_path(self) -> str:
        return os.path.join(self._tmp.name, "123ABC.json")


class Devices(CliHarness):
    def test_devices_lists(self):
        code, out, _ = self.cli("devices")
        self.assertEqual(code, 0)
        self.assertIn("123ABC", out)
        self.assertIn("device", out)


class Scan(CliHarness):
    def test_scan_table_two_modes(self):
        code, out, _ = self.cli("scan")
        self.assertEqual(code, 0)
        # compteur deux-modes + masquage des protégées
        self.assertIn("sûr 1", out)
        self.assertIn("avancé 2", out)
        self.assertIn("dont 1 non répertoriée(s)", out)
        self.assertIn("utilisateur 1", out)
        self.assertIn("protégées masquées : 2", out)
        # la table : protégées absentes, tag de mode sur les lignes
        self.assertIn("[sûr] com.facebook.appmanager", out)
        self.assertIn("[avancé] com.netflix.mediaclient", out)
        self.assertIn("[avancé (non répertorié)] com.paquet.inconnu.x", out)
        self.assertIn("[utilisateur] org.perso.app", out)
        self.assertNotIn("com.google.android.gms", out)
        self.assertNotIn("com.android.chrome", out)

    def test_scan_filter_risk(self):
        code, out, _ = self.cli("scan", "--risk", "safe")
        self.assertEqual(code, 0)
        self.assertIn("com.facebook.appmanager", out)
        self.assertNotIn("com.netflix.mediaclient", out)

    def test_scan_filter_advanced_includes_unlisted(self):
        code, out, _ = self.cli("scan", "--risk", "advanced")
        self.assertEqual(code, 0)
        self.assertIn("com.netflix.mediaclient", out)
        self.assertIn("com.paquet.inconnu.x", out)
        self.assertNotIn("com.facebook.appmanager", out)

    def test_scan_forbidden_only_when_explicit(self):
        code, out, _ = self.cli("scan", "--risk", "forbidden")
        self.assertEqual(code, 0)
        self.assertIn("com.google.android.gms", out)
        self.assertIn("com.android.chrome", out)
        self.assertIn("protégé (verrouillé)", out)

    def test_scan_search(self):
        code, out, _ = self.cli("scan", "--search", "netflix")
        self.assertEqual(code, 0)
        self.assertIn("com.netflix.mediaclient", out)
        self.assertNotIn("com.facebook.appmanager", out)

    def test_scan_search_no_match(self):
        code, out, _ = self.cli("scan", "--search", "zzzzzz")
        self.assertEqual(code, 0)
        self.assertIn("aucune app correspondante", out.lower())

    def test_scan_json_payload(self):
        code, out, _ = self.cli("scan", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["serial"], "123ABC")
        self.assertEqual(payload["device"], "Google Pixel Test")
        apps = {a["package"]: a for a in payload["apps"]}
        self.assertEqual(apps["com.facebook.appmanager"]["risk"], "safe")
        self.assertEqual(apps["org.perso.app"]["type"], "user")
        self.assertEqual(set(apps["com.android.chrome"].keys()) -
                         {"package", "type", "risk", "label", "note"}, set())

    def test_scan_report_write(self):
        path = os.path.join(self._tmp.name, "rapport.json")
        code, _, _ = self.cli("scan", "--report", path)
        self.assertEqual(code, 0)
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        self.assertEqual(payload["counts"]["safe"], 1)


class UninstallGuards(CliHarness):
    def test_refuses_forbidden(self):
        code, _, err = self.cli("uninstall", "com.google.android.gms")
        self.assertEqual(code, debloat_cli.EXIT_REFUSED)
        self.assertIn("protégé", err)
        self.assertEqual(self.fake.uninstalled, [])

    def test_refuses_forbidden_by_prefix(self):
        code, _, err = self.cli("uninstall", "com.android.chrome")
        self.assertEqual(code, debloat_cli.EXIT_REFUSED)
        self.assertIn("protégé", err)

    def test_refuses_unknown_without_flag(self):
        code, _, err = self.cli("uninstall", "com.paquet.inconnu.x")
        self.assertEqual(code, debloat_cli.EXIT_REFUSED)
        self.assertIn("--allow-unknown", err)
        self.assertEqual(self.fake.uninstalled, [])

    def test_allow_unknown_with_yes(self):
        code, out, _ = self.cli("uninstall", "com.paquet.inconnu.x",
                                "--allow-unknown", "--yes")
        self.assertEqual(code, 0)
        self.assertEqual([p for p, _u in self.fake.uninstalled],
                         ["com.paquet.inconnu.x"])
        data = _load(self.backup_path())
        self.assertEqual(data["history"][0]["package"], "com.paquet.inconnu.x")

    def test_refuses_user_app_without_flag(self):
        code, _, err = self.cli("uninstall", "org.perso.app")
        self.assertEqual(code, debloat_cli.EXIT_REFUSED)
        self.assertIn("--allow-user-apps", err)

    def test_user_app_uninstalls_definitive_cmd(self):
        code, _, _ = self.cli("uninstall", "org.perso.app",
                              "--allow-user-apps", "--yes")
        self.assertEqual(code, 0)
        self.assertIn(("org.perso.app", True), self.fake.uninstalled)
        data = _load(self.backup_path())
        self.assertEqual(data["history"][0]["type"], "user")

    def test_backup_apks_flag_saves_apk(self):
        code, out, _ = self.cli("uninstall", "com.facebook.appmanager",
                                "--backup-apks", "--yes")
        self.assertEqual(code, 0, out)
        apk = os.path.join(self._tmp.name, "123ABC", "apks",
                           "com.facebook.appmanager", "base.apk")
        self.assertTrue(os.path.exists(apk), out)
        self.assertIn("APK sauvegardé", out)
        self.assertIn("com.facebook.appmanager retiré", out)

    def test_without_flag_no_apk_saved(self):
        code, _, _ = self.cli("uninstall", "com.facebook.appmanager", "--yes")
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(os.path.join(self._tmp.name, "123ABC", "apks")))
        self.assertEqual(self.fake.pulled, [])

    def test_missing_package(self):
        code, _, err = self.cli("uninstall", "org.truc.rien")
        self.assertEqual(code, debloat_cli.EXIT_ERR)
        self.assertIn("n'est pas installé", err)

    def test_dry_run_does_nothing(self):
        code, out, _ = self.cli("uninstall", "com.facebook.appmanager", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("pm uninstall --user 0 <pkg> com.facebook.appmanager", out)
        self.assertEqual(self.fake.uninstalled, [])
        self.assertFalse(os.path.exists(self.backup_path()))

    def test_failure_returns_err(self):
        self.fake.uninstall_results["com.facebook.appmanager"] = (False,
                                                                  "Failure [x]")
        code, out, _ = self.cli("uninstall", "com.facebook.appmanager", "--yes")
        self.assertEqual(code, debloat_cli.EXIT_ERR)
        self.assertIn("Échec  com.facebook.appmanager", out)
        self.assertFalse(os.path.exists(self.backup_path()))
        self.assertEqual(self.fake.uninstalled, [("com.facebook.appmanager", False)])

    def test_no_device_returns_err(self):
        # aucun appareil branché : pick_adb doit renvoyer EXIT_ERR
        import unittest.mock as _
        with _.patch.object(FakeAdb, "list_devices") as m:
            m.return_value = []
            code, _, err = self.cli("uninstall", "com.facebook.appmanager")
        self.assertEqual(code, debloat_cli.EXIT_ERR)
        self.assertIn("Aucun appareil", err)


class Restore(CliHarness):
    def test_restore_default_recent_file(self):
        path = backup.backup_path("123ABC", self._tmp.name)
        backup.append_backup(path, "123ABC", "Pixel", "com.facebook.appmanager", "system")
        code, out, _ = self.cli("restore", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("restauré", out)
        self.assertEqual(self.fake.restored, ["com.facebook.appmanager"])

    def test_restore_skips_user_entries(self):
        path = backup.backup_path("123ABC", self._tmp.name)
        backup.append_backup(path, "123ABC", "Pixel", "com.sys", "system")
        backup.append_backup(path, "123ABC", "Pixel", "org.user", "user")
        code, out, _ = self.cli("restore", "--yes")
        self.assertEqual(code, 0)
        self.assertEqual(self.fake.restored, ["com.sys"])
        self.assertIn("app utilisateur", out)

    def test_restore_dry_run(self):
        path = backup.backup_path("123ABC", self._tmp.name)
        backup.append_backup(path, "123ABC", "Pixel", "com.sys", "system")
        code, out, _ = self.cli("restore", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("install-existing com.sys", out)
        self.assertEqual(self.fake.restored, [])

    def test_restore_no_backup(self):
        code, _, err = self.cli("restore", "--yes")
        self.assertEqual(code, debloat_cli.EXIT_ERR)
        self.assertIn("Aucun backup", err)

    def test_restore_corrupt_file(self):
        path = os.path.join(self._tmp.name, "123ABC.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{{ pas du json .")
        code, _, err = self.cli("restore", "--file", path, "--yes")
        self.assertEqual(code, debloat_cli.EXIT_ERR)
        self.assertIn("Lecture du backup impossible", err)


if __name__ == "__main__":
    unittest.main()
