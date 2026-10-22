#!/usr/bin/env python3
"""Tests GUI en profondeur sous X (xvfb-run) : scan, filtres, coches,
désinstallation, backups (y compris corrompus), restauration, export, stress."""
import json
import os
import sys
import tempfile
import time
import unittest
import unittest.mock as mock

import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bloat_db                     # noqa: E402
import backup as backup_mod         # noqa: E402
import debloat_gui                  # noqa: E402
from tests.helpers import FakeAdb, patch_adb  # noqa: E402
def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)

FAKE_SYS = ["com.facebook.appmanager",      # safe
            "com.netflix.mediaclient",      # advanced
            "com.paquet.inconnu.x",         # unknown
            "com.google.android.gms",       # forbidden
            "com.android.chrome"]           # forbidden (préfixe com.android.*)
FAKE_USER = ["org.perso.app"]


def _display_ok() -> bool:
    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except tk.TclError:
        return False


@unittest.skipUnless(_display_ok(), "aucun serveur X — relance avec xvfb-run")
class GuiBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._root = tk.Tk()
        cls._root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls._root.destroy()
        except tk.TclError:
            pass

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="debloat_gui_")
        self.addCleanup(self._tmp.cleanup)
        bak_dir = self._tmp.name
        old = backup_mod.BACKUP_DIR
        backup_mod.BACKUP_DIR = bak_dir
        self.addCleanup(setattr, backup_mod, "BACKUP_DIR", old)

        self.fake = FakeAdb(serial="123ABC",
                            sys_pkgs=list(FAKE_SYS),
                            user_pkgs=list(FAKE_USER))
        patcher = patch_adb(debloat_gui, self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.app = debloat_gui.DebloatApp(self._root)
        self.addCleanup(self.app.stop_polling)
        self.pump(40)

    def pump(self, n=10, delay=0.01):
        for _ in range(n):
            self._root.update()
            time.sleep(delay)

    def log_text(self) -> str:
        return self.app.txt_log.get("1.0", "end")


class ScanAndViews(GuiBase):
    def test_auto_adopt_and_scan(self):
        self.assertEqual(self.app.serial, "123ABC")
        self.assertEqual(set(self.app.packages), set(FAKE_SYS + FAKE_USER))
        info = self.app.packages["com.facebook.appmanager"]
        self.assertEqual(info.risk, bloat_db.RISK_SAFE)
        # aucune coche automatique : c'est l'utilisateur qui coche explicitement
        self.assertFalse(info.checked)
        self.assertFalse(any(i.checked for i in self.app.packages.values()))
        self.assertFalse(self.app.packages["com.netflix.mediaclient"].checked)
        self.assertFalse(self.app.packages["com.google.android.gms"].checkable())
        header = self.app.lbl_dev.cget("text")
        self.assertIn("Pixel Test", header)
        self.assertIn("Android 14", header)

    def test_bloat_view_only_safe_and_advanced(self):
        iids = self.app._iids()
        self.assertEqual(set(iids),
                         {"com.facebook.appmanager", "com.netflix.mediaclient"})

    def test_protected_view_shows_forbidden_rows_locked(self):
        self.app.view.set("protected")
        self.app.refresh_tree()
        rows = self.app.tree.get_children("")
        self.assertEqual(set(rows),
                         {"com.google.android.gms", "com.android.chrome"})
        # aucun élément de la vue protégée n'est décochable
        for iid in rows:
            self.assertFalse(self.app.packages[iid].checkable())
            self.assertEqual(self.app.tree.item(iid, "values")[0], "[!]")

    def test_user_view(self):
        self.app.view.set("user")
        self.app.refresh_tree()
        self.assertEqual(set(self.app.tree.get_children("")), {"org.perso.app"})

    def test_all_view_counts_everything(self):
        self.app.view.set("all")
        self.app.refresh_tree()
        self.assertEqual(len(self.app.tree.get_children("")), len(self.app.packages))

    def test_search_filter(self):
        self.app.view.set("all")
        self.app.search.set("netflix")
        self.pump(5)
        self.assertEqual(self.app._iids(), ["com.netflix.mediaclient"])
        self.app.search.set("")
        self.pump(5)
        self.assertEqual(len(self.app._iids()), len(self.app.packages))

    def test_counts_label_updated(self):
        text = self.app.lbl_counts.cget("text")
        self.assertIn("Sûrs : 1", text)
        self.assertIn("Avancés : 1", text)
        self.assertIn("Protégés : 2", text)
        self.assertIn("Apps utilisateur : 1", text)


class CheckboxFlow(GuiBase):
    def test_toggle_via_click_updates_tree_and_actionbar(self):
        pkg = "com.netflix.mediaclient"
        self.app.view.set("bloat")
        self.app.refresh_tree()
        # simule le clic : la méthode prend (x, y) ; on passe par l'identifiant
        # déjà résolu -> on appelle le cœur du toggle
        info = self.app.packages[pkg]
        info.checked = True
        self.app.refresh_tree()
        vals = list(self.app.tree.item(pkg, "values"))
        self.assertEqual(vals[0], "[x]")
        self.assertIn("(1)", self.app.btn_uninstall.cget("text"))
        self.assertEqual(str(self.app.btn_uninstall.cget("state")), "normal")

    def test_forbidden_log_on_toggle_attempt(self):
        pkg = "com.google.android.gms"
        self.app.view.set("protected")
        self.app.refresh_tree()
        evt = mock.Mock()
        evt.x, evt.y = 10, 10
        with mock.patch.object(self.app.tree, "identify_row", return_value=pkg), \
                mock.patch.object(self.app.tree, "identify_region", return_value="cell"):
            self.app._on_tree_click(evt)
        self.assertFalse(self.app.packages[pkg].checked)
        self.assertIn("composant protégé", self.log_text())

    def test_space_toggles_selected_row(self):
        pkg = "com.netflix.mediaclient"
        self.app.view.set("bloat")
        self.app.refresh_tree()
        self.app.tree.selection_set(pkg)
        self.assertFalse(self.app.packages[pkg].checked)
        self.app._on_space(mock.Mock())
        self.assertTrue(self.app.packages[pkg].checked)
        self.assertIn("(1)", self.app.btn_uninstall.cget("text"))
        self.app._on_space(mock.Mock())
        self.assertFalse(self.app.packages[pkg].checked)

    def test_select_all_safe_only(self):
        self.app.view.set("bloat")
        self.app.refresh_tree()
        self.app.select_all(True)
        checked = {p for p, i in self.app.packages.items()
                   if i.checked and i.ptype == "system"}
        self.assertEqual(checked, {"com.facebook.appmanager"})

    def test_select_all_includes_advanced_only_in_view(self):
        self.app.view.set("bloat")
        self.app.refresh_tree()
        self.app.select_all(False)
        checked = {p for p, i in self.app.packages.items()
                   if i.checked and i.ptype == "system"}
        self.assertEqual(checked, {"com.facebook.appmanager", "com.netflix.mediaclient"})

    def test_select_all_in_system_view_warns_unknown(self):
        self.app.view.set("system")
        self.app.refresh_tree()
        self.app.select_all(False)
        self.assertIn("paquets inconnus", self.log_text())
        checked_unknown = self.app.packages["com.paquet.inconnu.x"]
        self.assertTrue(checked_unknown.checked)

    def test_clear_checks(self):
        self.app.select_all(False)
        self.app.clear_checks()
        self.assertFalse(any(i.checked for i in self.app.packages.values()))

    def test_busy_disables_action_buttons(self):
        self.app._set_busy(True)
        self.assertEqual(str(self.app.btn_uninstall.cget("state")), "disabled")
        self.assertEqual(str(self.app.btn_scan.cget("state")), "disabled")
        self.app._set_busy(False)
        self.assertEqual(str(self.app.btn_backups.cget("state")), "normal")


class DetailsDialog(GuiBase):
    def test_double_click_showinfo_payloads(self):
        pkg = "com.facebook.appmanager"
        with mock.patch.object(self.app.tree, "identify_row", return_value=pkg), \
                mock.patch.object(debloat_gui.messagebox, "showinfo",
                                  side_effect=None) as showinfo:
            self.app._on_tree_double(mock.Mock())
        showinfo.assert_called_once()
        args, _kw = showinfo.call_args
        title, message = args[0], args[1]
        self.assertEqual(title, "Facebook App Manager")
        self.assertIn("app système", message)
        self.assertIn("sans danger", message)


class Uninstall(GuiBase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(debloat_gui.messagebox, "askyesno", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_uninstall_updates_state_and_backup(self):
        self.app.packages["com.facebook.appmanager"].checked = True
        self.app.packages["com.netflix.mediaclient"].checked = True
        self.app.uninstall_selected()
        self.pump(40)
        executed = [pkg for pkg, _user in self.fake.uninstalled]
        self.assertEqual(set(executed),
                         {"com.facebook.appmanager", "com.netflix.mediaclient"})
        self.assertNotIn("com.facebook.appmanager", self.app.packages)
        self.assertNotIn("com.netflix.mediaclient", self.app.packages)
        path = backup_mod.backup_path("123ABC", self._tmp.name)
        data = _load(path)
        hist = {h["package"]: h["type"] for h in data["history"]}
        self.assertEqual(hist, {"com.facebook.appmanager": "system",
                                "com.netflix.mediaclient": "system"})
        self.assertIn("(0)", self.app.btn_uninstall.cget("text"))

    def test_failure_keeps_package(self):
        self.fake.uninstall_results["com.facebook.appmanager"] = (False, "Failure [x]")
        self.app.packages["com.facebook.appmanager"].checked = True
        self.app.uninstall_selected()
        self.pump(40)
        self.assertIn("com.facebook.appmanager", self.app.packages)
        self.assertIn("ÉCHEC  com.facebook.appmanager", self.log_text())
        self.assertFalse(os.path.exists(backup_mod.backup_path("123ABC", self._tmp.name)))

    def test_adb_error_handled(self):
        self.fake.raise_on_uninstall = "com.facebook.appmanager"
        self.app.packages["com.facebook.appmanager"].checked = True
        self.app.uninstall_selected()
        self.pump(40)
        self.assertIn("appareil débranché", self.log_text())
        self.assertIn("com.facebook.appmanager", self.app.packages)

    def test_user_app_uninstall_definitive(self):
        self.app.packages["org.perso.app"].checked = True
        self.app.uninstall_selected()
        self.pump(40)
        self.assertIn(("org.perso.app", True), self.fake.uninstalled)
        path = backup_mod.backup_path("123ABC", self._tmp.name)
        data = _load(path)
        hist = {h["package"]: h["type"] for h in data["history"]}
        self.assertEqual(hist["org.perso.app"], "user")

    def test_apk_backup_proposal_accepted(self):
        pkg = "com.facebook.appmanager"
        self.app.packages[pkg].checked = True
        with mock.patch.object(debloat_gui.messagebox, "askyesno",
                               side_effect=[True, True]):
            self.app.uninstall_selected()
        self.pump(60)
        apk = os.path.join(self._tmp.name, "123ABC", "apks", pkg, "base.apk")
        self.assertTrue(os.path.exists(apk), self.log_text())
        self.assertIn("APK sauvegardé", self.log_text())
        self.assertIn(f"OK  {pkg} retiré", self.log_text())
        self.assertIn(pkg, self.fake.pulled[0][0])

    def test_apk_backup_proposal_declined(self):
        pkg = "com.facebook.appmanager"
        self.app.packages[pkg].checked = True
        with mock.patch.object(debloat_gui.messagebox, "askyesno",
                               side_effect=[True, False]):
            self.app.uninstall_selected()
        self.pump(50)
        self.assertFalse(os.path.exists(os.path.join(self._tmp.name, "123ABC", "apks")))
        self.assertIn(f"OK  {pkg} retiré", self.log_text())

    def test_apk_backup_failure_still_uninstalls(self):
        self.fake.fail_pull = True
        pkg = "com.facebook.appmanager"
        self.app.packages[pkg].checked = True
        with mock.patch.object(debloat_gui.messagebox, "askyesno",
                               side_effect=[True, True]):
            self.app.uninstall_selected()
        self.pump(50)
        self.assertIn("Échec de la sauvegarde APK", self.log_text())
        self.assertIn(f"OK  {pkg} retiré", self.log_text())


class BackupRobustness(GuiBase):
    def test_corrupt_backup_quarantined(self):
        path = backup_mod.backup_path("123ABC", self._tmp.name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{{ corrupted json ¤")
        with mock.patch.object(debloat_gui.messagebox, "askyesno", return_value=True):
            self.app.packages["com.facebook.appmanager"].checked = True
            self.app.uninstall_selected()
            self.pump(40)
        self.assertIn("quarantaine", self.log_text())
        quarantined = [f for f in os.listdir(self._tmp.name) if ".corrupt-" in f]
        self.assertEqual(len(quarantined), 1)
        data = _load(path)
        self.assertEqual(data["history"][0]["package"], "com.facebook.appmanager")

    def test_restore_from_backup_reinstalls_and_rescans(self):
        path = backup_mod.backup_path("123ABC", self._tmp.name)
        backup_mod.append_backup(path, "123ABC", "Pixel Test",
                                 "com.facebook.appmanager", "system")
        backup_mod.append_backup(path, "123ABC", "Pixel Test", "org.perso.app", "user")
        # retire l'app de la mémoire (comme si elle venait d'être désinstallée)
        self.app.packages.pop("com.facebook.appmanager", None)
        self.app._spawn(self.app._th_restore, path)
        self.pump(60)
        self.assertEqual(self.fake.restored, ["com.facebook.appmanager"])
        # le re-scan automatique a réinjecté l'app dans la liste
        self.assertIn("com.facebook.appmanager", self.app.packages)
        self.assertIn("app utilisateur", self.log_text())
        self.assertIn("Nouveau scan", self.log_text())

    def test_restore_other_device_does_not_rescan(self):
        path = backup_mod.backup_path("OTHER", self._tmp.name)
        backup_mod.append_backup(path, "OTHER", "Autre", "com.zzz", "system")
        before_pkgs = dict(self.app.packages)
        self.app._spawn(self.app._th_restore, path)
        self.pump(60)
        self.assertIn("com.zzz", self.fake.restored)
        self.assertNotIn("Nouveau scan", self.log_text())
        self.assertEqual(self.app.packages, before_pkgs)


class ExportReport(GuiBase):
    def test_export_writes_valid_json(self):
        path = os.path.join(self._tmp.name, "rapport.json")
        with mock.patch.object(debloat_gui.filedialog, "asksaveasfilename",
                               return_value=path):
            self.app.export_report()
        self.pump(5)
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        self.assertEqual(payload["serial"], "123ABC")
        apps = {a["package"]: a for a in payload["apps"]}
        self.assertEqual(apps["com.facebook.appmanager"]["risk"], bloat_db.RISK_SAFE)
        self.assertEqual(apps["com.android.chrome"]["risk"], bloat_db.RISK_FORBIDDEN)
        self.assertEqual(payload["counts"]["system"]["safe"], 1)
        self.assertEqual(apps["com.facebook.appmanager"]["selected"], False)

    def test_export_cancelled(self):
        with mock.patch.object(debloat_gui.filedialog, "asksaveasfilename",
                               return_value=""):
            self.app.export_report()
        files = os.listdir(self._tmp.name)
        self.assertFalse([f for f in files if f.endswith(".json")])


class Stress(GuiBase):
    def test_scan_1500_apps_stays_usable(self):
        import collections
        many = [f"com.vendor.app{i}" for i in range(1500)]
        self.fake.sys_pkgs = many + list(FAKE_SYS)
        self.fake.user_pkgs = []
        t0 = time.perf_counter()
        self.app.scan_packages()
        self.pump(200, delay=0.005)
        elapsed_scan = time.perf_counter() - t0
        self.assertEqual(len(self.app.packages), 1500 + len(FAKE_SYS))
        self.assertEqual(self.app.packages["com.vendor.app42"].risk,
                         bloat_db.RISK_UNKNOWN)

        self.app.view.set("all")
        t1 = time.perf_counter()
        self.app.refresh_tree()
        elapsed_refresh = time.perf_counter() - t1
        self.assertEqual(len(self.app.tree.get_children("")), 1500 + len(FAKE_SYS))
        t2 = time.perf_counter()
        self.app.search.set("vendor")
        self.pump(10, delay=0.005)
        iids = self.app._iids()
        elapsed_search = time.perf_counter() - t2
        self.assertEqual(len(iids), 1500)
        # Bornes très lâches : mesure de pente, pas de benchmark
        self.assertLess(elapsed_scan, 10.0,
                        f"scan trop lent : {elapsed_scan:.2f}s")
        self.assertLess(elapsed_refresh, 5.0,
                        f"refresh trop lent : {elapsed_refresh:.2f}s")
        self.assertLess(elapsed_search, 5.0,
                        f"recherche trop lente : {elapsed_search:.2f}s")
        print(f"[stress] scan={elapsed_scan:.2f}s refresh={elapsed_refresh:.2f}s "
              f"search={elapsed_search:.2f}s — {len(iids)} lignes")


if __name__ == "__main__":
    unittest.main()
