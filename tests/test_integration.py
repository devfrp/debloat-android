#!/usr/bin/env python3
"""Tests d'intégration : le CLI est exécuté en sous-processus réel contre un
faux binaire « adb » (script bash). On teste donc le vrai chemin
shutil.which -> subprocess.run -> parsing de adb.py, sans aucun mock Python."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAKE_ADB = r'''#!/usr/bin/env bash
# faux adb pour les tests d'intégration
# un vrai adb consomme ses propres options (-s <serial>) avant la commande :
if [ "$1" = "-s" ]; then shift 2; fi
case "$1" in
  devices)
    printf 'List of devices attached\n'
    printf '123ABC device product:fake model:Pixel_FAKE device:fake transport_id:1\n'
    ;;
  shell)
    case "$1 $2" in
      "shell getprop")
        printf '[ro.product.brand]: [Fake]\n'
        printf '[ro.product.model]: [Pixel FAKE]\n'
        printf '[ro.build.version.release]: [14]\n'
        ;;
      "shell pm")
        case "$3" in
          list)
            if [ "$5" = "-s" ]; then
              printf 'package:com.facebook.appmanager\npackage:com.netflix.mediaclient\npackage:com.android.chrome\n'
            else
              printf 'package:org.user.app\n'
            fi
            ;;
          path)
            echo "package:/data/app/$4/base.apk"
            ;;
          uninstall)
            echo "Success"
            ;;
        esac
        ;;
      "shell cmd")
        echo "Success"
        ;;
    esac
    ;;
  pull)
    mkdir -p "$3"
    printf 'apk-content' > "$3/$(basename "$2")"
    ;;
esac
'''


class CliSubprocess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="debloat_e2e_")
        cls.adb_path = os.path.join(cls._tmp.name, "fake-adb")
        with open(cls.adb_path, "w", encoding="utf-8") as fh:
            fh.write(FAKE_ADB)
        os.chmod(cls.adb_path, os.stat(cls.adb_path).st_mode | stat.S_IEXEC)
        os.makedirs(os.path.join(ROOT, "backups"), exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        # nettoyage du backup et des APK éventuellement créés par les tests
        base = os.path.join(ROOT, "backups", "123ABC")
        if os.path.isdir(base):
            import shutil
            shutil.rmtree(base, ignore_errors=True)
        p = os.path.join(ROOT, "backups", "123ABC.json")
        if os.path.exists(p):
            os.remove(p)
        cls._tmp.cleanup()

    def run_cli(self, *args: str, cwd: str | None = None) -> tuple[int, str, str]:
        env = dict(os.environ, ADB_PATH=self.adb_path)
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "debloat_cli.py"), *args],
            capture_output=True, text=True, env=env, cwd=cwd or ROOT, timeout=120)
        return proc.returncode, proc.stdout, proc.stderr

    def test_devices(self):
        code, out, err = self.run_cli("devices")
        self.assertEqual(code, 0, err)
        self.assertIn("123ABC", out)
        self.assertIn("device", out)

    def test_scan_real_parsing(self):
        code, out, err = self.run_cli("scan")
        self.assertEqual(code, 0, err)
        self.assertIn("com.facebook.appmanager", out)
        self.assertIn("safe 1", out)
        self.assertIn("forbidden 1", out)   # chrome (gms est hors image fake)
        self.assertIn("Pixel FAKE", out)

    def test_scan_json(self):
        code, out, _ = self.run_cli("scan", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["serial"], "123ABC")
        self.assertEqual(payload["device"], "Fake Pixel FAKE")
        apps = {a["package"]: a for a in payload["apps"]}
        self.assertEqual(apps["com.android.chrome"]["risk"], "forbidden")

    def test_uninstall_recovery_roundtrip(self):
        code, out, err = self.run_cli("uninstall", "com.facebook.appmanager", "--yes")
        self.assertEqual(code, 0, err)
        self.assertIn("OK  com.facebook.appmanager retiré", out)
        self.assertIn("retrait(s) réussi", out)
        path = os.path.join(ROOT, "backups", "123ABC.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["serial"], "123ABC")
        self.assertEqual(data["history"][0]["package"], "com.facebook.appmanager")

        code, out, _ = self.run_cli("restore", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("OK  com.facebook.appmanager restauré", out)

    def test_uninstall_forbidden_refused(self):
        code, _, err = self.run_cli("uninstall", "com.android.chrome")
        self.assertEqual(code, 2)
        self.assertIn("protégé", err)

    def test_uninstall_with_apk_backup(self):
        code, out, err = self.run_cli("uninstall", "com.facebook.appmanager",
                                      "--backup-apks", "--yes")
        self.assertEqual(code, 0, err + out)
        apk = os.path.join(ROOT, "backups", "123ABC", "apks",
                           "com.facebook.appmanager", "base.apk")
        self.assertTrue(os.path.exists(apk), out)
        with open(apk, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "apk-content")
        self.assertIn("APK sauvegardé : com.facebook.appmanager", out)
        self.assertIn("OK  com.facebook.appmanager retiré", out)

    def test_scan_from_other_cwd(self):
        code, out, _ = self.run_cli("scan", "--risk", "safe", cwd=self._tmp.name)
        self.assertEqual(code, 0)
        self.assertIn("com.facebook.appmanager", out)


if __name__ == "__main__":
    unittest.main()
