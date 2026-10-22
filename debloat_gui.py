#!/usr/bin/env python3
"""Debloat Android — interface graphique de débloat basée sur ADB (sans root).

Principes :
  - aucune modification sans la permission de l'utilisateur ;
  - tout ce qui est retiré (app système) est restaurable via les fichiers de backup ;
  - les composants système critiques (préfixe com.android.*, GMS, WebView…)
    sont protégés et volontairement non décochables.

Lancement :  python3 debloat_gui.py   (ou ./run.sh)
"""
from __future__ import annotations

import datetime
import json
import os
import queue
import threading
from collections import Counter
from dataclasses import dataclass

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import bloat_db
import backup
import language
from adb import Adb, AdbError, DeviceInfo

APP_TITLE = "Debloat Android"
APP_VERSION = "1.4.0"

RISK_ORDER = {
    bloat_db.RISK_SAFE: 0,
    bloat_db.RISK_ADVANCED: 1,
    bloat_db.RISK_UNKNOWN: 2,
    bloat_db.RISK_FORBIDDEN: 3,
}

# Deux modes seulement : « Sûr » (recommandées) et « Avancé » (prudence).
# Les paquets hors base s'affichent comme avancées non listées ; les composants
# protégés ne font pas partie des modes : masqués, retrouvables par la recherche.
VIEW_SAFE = "safe"
VIEW_ADV = "advanced"

CHECK_ON, CHECK_OFF, CHECK_LOCK = "[x]", "[ ]", "[!]"

_HELP = {}

_HELP["fr"] = f"""\
DEBLOAT ANDROID — guide d'utilisation

1) PRÉREQUIS
   • Installer l'outil ADB :
        Debian/Ubuntu : sudo apt install adb
        Fedora        : sudo dnf install android-tools
        Arch          : sudo pacman -S android-tools
        macOS         : brew install --cask android-platform-tools
        Windows       : platform-tools (https://developer.android.com/studio/releases/platform-tools)
   • Si adb est installé ailleurs, lancez l'app avec :  ADB_PATH=/chemin/adb python3 debloat_gui.py

2) ACTIVER LE MODE DÉBOGAGE SUR LE TÉLÉPHONE
   • Paramètres -> À propos du téléphone -> appuyer 7× sur « numéro de build ».
   • Options pour développeurs -> activer « Débogage USB ».
   • Brancher le câble USB, puis accepter la boîte de dialogue « Autoriser le
     débogage USB » sur le téléphone (cocher « Toujours autoriser »).

3) UTILISATION — DEUX MODES
   • «  Rafraîchir les appareils » : détecte le téléphone.
   • «  Scanner les applications » : classe les apps dans deux modes seulement :
        Sûr    = retrait recommandé, sans danger attendu (mode sélectionné après scan),
        Avancé = prudence — une fonctionnalité peut manquer après retrait. Les paquets
                 hors base s'y affichent comme « avancée (non listée) ».
      Les composants protégés (Play services, IMS, téléphonie…) n'appartiennent
      à aucun mode : ils sont masqués et toujours verrouillés au retrait. La
      recherche permet de les retrouver (ligne verrouillée).
   • Le survol d'une ligne affiche une note explicative en bas de fenêtre.
   • Tu coches toi-même chaque app à retirer : un clic sur la ligne, ou Espace
      sur la ligne sélectionnée (colonne « Cocher »). Le bouton « Cocher les
      sûres (mode) » est un raccourci optionnel.
   • « Désinstaller la sélection » applique le retrait :
        mode Sûr    -> une seule confirmation,
        mode Avancé -> deux confirmations,
      et l'app propose de sauvegarder les APK de la sélection sur le PC.
      Les apps utilisateur (Play Store) déclenchent en plus l'avertissement
      de suppression définitive.
   • « Rapport » : exporte le scan courant en fichier JSON archivable.

4) CE QUE L'APP FAIT TECHNIQUEMENT
   • App système  : adb shell pm uninstall --user 0 <paquet>
        -> retire l'app pour votre profil : l'APK reste sur le téléphone et tout
          peut être restauré. C'est la méthode standard des outils de débloat.
   • App utilisateur (Play Store) : pm uninstall <paquet>
        -> SUPPRESSION DÉFINITIVE, données perdues (réinstallez depuis une boutique).

5) RESTAURER
   • Chaque désinstallation est notée dans backups/<serial>.json.
   • « Gestionnaire de backups » -> choisir le fichier -> « Restaurer ce backup »
      exécute : adb shell cmd package install-existing <paquet>.
   • Un redémarrage du téléphone peut être utile après des restaurations de
      services système.

6) CONSEILS DE SÉCURITÉ
   • La première fois, désinstallez quelques apps à la fois et testez immédiatement.
   • Ne forcez jamais les composants protégés (Play services, WebView, clavier, lanceur…).
   • En cas de doute sur un paquet « avancée (non listée) », cherche
     « debloat <paquet> » sur le web avant de le cocher.
   • Une mise à jour OTA du constructeur réinstalle généralement tout.
   • Un backup illisible est automatiquement mis en quarantaine (*.corrupt-…),
      il n'est jamais écrasé : vérifiez le dossier backups/ si l'app le signale.

7) COMPAGNON EN LIGNE DE COMMANDE (sans interface graphique)
   • python3 debloat_cli.py devices            -> appareils détectés
   • python3 debloat_cli.py scan               -> scan + classification (risques)
   • python3 debloat_cli.py scan --json        -> même données, en JSON réexportable
   • python3 debloat_cli.py uninstall <pkg…>   -> garde-fous identiques à la GUI
        (--allow-unknown, --allow-user-apps, --yes, --dry-run)
   • python3 debloat_cli.py restore            -> réinstalle le backup le plus récent
        (--file backups/X.json, --yes, --dry-run)

───
Version {APP_VERSION} • Aucune donnée n'est envoyée sur Internet par cette app.
En cas de souci, la restauration depuis le gestionnaire de backups est votre ami.
"""

_HELP["en"] = f"""\
DEBLOAT ANDROID — user guide

1) REQUIREMENTS
   • Install the ADB tool:
        Debian/Ubuntu : sudo apt install adb
        Fedora        : sudo dnf install android-tools
        Arch          : sudo pacman -S android-tools
        macOS         : brew install --cask android-platform-tools
        Windows       : platform-tools (https://developer.android.com/studio/releases/platform-tools)
   • If adb lives elsewhere, start the app with:  ADB_PATH=/path/to/adb python3 debloat_gui.py

2) ENABLE DEBUGGING ON THE PHONE
   • Settings -> About phone -> tap 7× on "build number".
   • Developer options -> enable "USB debugging".
   • Plug the USB cable, then accept the "Allow USB debugging" dialog on the
     phone (check "Always allow").

3) USAGE — TWO MODES
   • "Refresh devices": detects the phone.
   • "Scan apps": sorts apps into two modes only:
        Safe     = removal recommended, expected to be harmless (mode selected after the scan),
        Advanced = extra care — a feature may be missing after removal. Packages
                   outside the database appear there as "advanced (unlisted)".
     Protected components (Play services, IMS, telephony…) belong to no
     mode: they are hidden and always locked from removal. The search
     field retrieves them (locked row).
   • Hovering a row shows an explanatory note at the bottom of the window.
   • You check each app to remove yourself: a click on the row, or Space
      on the selected row ("Check" column). The "Check safe ones (mode)"
      button is an optional shortcut.
   • "Uninstall selection" performs the removal:
        Safe mode     -> a single confirmation,
        Advanced mode -> two confirmations,
      and the app offers to save the selection's APKs on the PC.
      User apps (Play Store) additionally trigger the permanent-deletion
      warning.
   • "Report": exports the current scan as an archivable JSON file.

4) WHAT THE APP DOES TECHNICALLY
   • System app  : adb shell pm uninstall --user 0 <package>
        -> removes the app for your profile: the APK stays on the phone and
          everything can be restored. This is the standard debloat method.
   • User app (Play Store) : pm uninstall <package>
        -> PERMANENT DELETION, data lost (reinstall from a store).

5) RESTORE
   • Every uninstall is recorded in backups/<serial>.json.
   • "Backup manager" -> pick the file -> "Restore this backup"
      runs: adb shell cmd package install-existing <package>.
   • A phone reboot may help after restoring system services.

6) SAFETY TIPS
   • The first time, remove a few apps at a time and test right away.
   • Never force protected components (Play services, WebView, keyboard, launcher…).
   • If unsure about an "advanced (unlisted)" package, search
     "debloat <package>" on the web before checking it.
   • An OTA update from the vendor usually reinstalls everything.
   • An unreadable backup is automatically quarantined (*.corrupt-…);
      it is never overwritten: check the backups/ folder if the app warns about it.

7) COMMAND-LINE COMPANION (no GUI)
   • python3 debloat_cli.py devices            -> detected devices
   • python3 debloat_cli.py scan               -> scan + classification (risks)
   • python3 debloat_cli.py scan --json        -> same data, re-exportable as JSON
   • python3 debloat_cli.py uninstall <pkg…>   -> same guard rails as the GUI
        (--allow-unknown, --allow-user-apps, --yes, --dry-run)
   • python3 debloat_cli.py restore            -> reinstalls the newest backup
        (--file backups/X.json, --yes, --dry-run)

───
Version {APP_VERSION} • This app sends nothing over the Internet.
If anything goes wrong, restoring from the backup manager is your friend.
"""


def help_text() -> str:
    """Texte d'aide dans la langue choisie au démarrage."""
    return _HELP.get(language.get_lang()) or _HELP["fr"]


@dataclass
class PackageInfo:
    package: str
    ptype: str          # "system" | "user"
    risk: str           # safe | advanced | forbidden | unknown
    label: str = ""
    note: str = ""
    checked: bool = False

    def checkable(self) -> bool:
        return self.risk != bloat_db.RISK_FORBIDDEN


class DebloatApp:
    """Fenêtre principale de l'application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title(APP_TITLE)
        root.geometry("1180x760")
        root.minsize(980, 620)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.q: "queue.Queue[tuple]" = queue.Queue()
        self.serial: str | None = None
        self.dev_label = ""
        self.last_props: dict[str, str] = {}
        self.packages: dict[str, PackageInfo] = {}
        self.view = tk.StringVar(value=VIEW_SAFE)
        self.search = tk.StringVar()
        self.busy = False
        self._bkl = threading.Lock()
        self._closed = False
        self._after_id: str | None = None

        self._build_ui()
        self._after_id = self.root.after(120, self._poll)
        self._set_default_status()
        self.log(language.t("welcome"))
        self.refresh_devices()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = self.root

        # ---------------------------------------------------------- header
        head = ttk.Frame(root)
        head.pack(fill="x", padx=10, pady=(10, 4))
        self.lbl_dev = ttk.Label(head, text=language.t("device.none"), font=("", 11, "bold"))
        self.lbl_dev.pack(side="left")
        self.btn_help = ttk.Button(head, text=language.t("btn.help"), command=self.show_help)
        self.btn_help.pack(side="right")
        self.btn_scan = ttk.Button(head, text=language.t("btn.scan"),
                                   command=self.scan_packages, state="disabled")
        self.btn_scan.pack(side="right", padx=6)
        self.btn_refresh = ttk.Button(head, text=language.t("btn.refresh"),
                                      command=self.refresh_devices)
        self.btn_refresh.pack(side="right", padx=6)

        # ------------------------------------------------------------ body
        body = ttk.Frame(root)
        body.pack(fill="both", expand=True, padx=10, pady=4)

        left = ttk.Frame(body, width=235)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text=language.t("mode.header"), font=("", 10, "bold")).pack(anchor="w", pady=(0, 2))
        for value, text in (
            (VIEW_SAFE, language.t("mode.safe")),
            (VIEW_ADV, language.t("mode.adv")),
        ):
            ttk.Radiobutton(left, text=text, value=value, variable=self.view,
                            command=self.refresh_tree).pack(anchor="w", pady=1)
        self.lbl_counts = ttk.Label(left, text="", foreground="#55606e", justify="left")
        self.lbl_counts.pack(anchor="w", pady=(8, 4))

        self.btn_sel_safe = ttk.Button(left, text=language.t("btn.check_safe"),
                                       command=lambda: self.select_all(True))
        self.btn_sel_all = ttk.Button(left, text=language.t("btn.check_all"),
                                      command=lambda: self.select_all(False))
        self.btn_unsel = ttk.Button(left, text=language.t("btn.uncheck"), command=self.clear_checks)
        self.btn_sel_safe.pack(fill="x", pady=(6, 2))
        self.btn_sel_all.pack(fill="x", pady=2)
        self.btn_unsel.pack(fill="x", pady=2)
        ttk.Label(left, text=language.t("hint.adv"),
                  foreground="#a25c00", justify="left").pack(anchor="w", pady=(10, 0))

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        srow = ttk.Frame(right)
        srow.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Label(srow, text=language.t("search.hint")).pack(side="left")
        ttk.Entry(srow, textvariable=self.search).pack(side="left", fill="x", expand=True, padx=6)
        self.search.trace_add("write", lambda *_: self.refresh_tree())

        cols = ("check", "package", "app", "risk", "type")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", selectmode="browse")
        for col, width, anchor, key in (
            ("check", 64, "center", "col.check"),
            ("package", 390, "w", "col.package"),
            ("app", 210, "w", "col.app"),
            ("risk", 130, "w", "col.risk"),
            ("type", 90, "w", "col.type"),
        ):
            self.tree.heading(col, text=language.t(key))
            self.tree.column(col, width=width, anchor=anchor,
                             stretch=col in ("package", "app"))
        ysb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(right, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        for tag, color in (
            ("risk_safe", "#157a26"),
            ("risk_advanced", "#b36b00"),
            ("risk_unknown", "#55606e"),
            ("risk_forbidden", "#b00020"),
            ("risk_user", "#55606e"),
        ):
            self.tree.tag_configure(tag, foreground=color)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        self.tree.grid(row=1, column=0, sticky="nsew")
        ysb.grid(row=1, column=1, sticky="ns")
        xsb.grid(row=2, column=0, sticky="ew")

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<space>", self._on_space)
        self.tree.bind("<Double-1>", self._on_tree_double)
        self.tree.bind("<Motion>", self._on_tree_hover)
        self.tree.bind("<Leave>", lambda _e: self._set_default_status())

        # ------------------------------------------------- actions + logs
        actions = ttk.Frame(root)
        actions.pack(fill="x", padx=10, pady=4)
        self.progress = ttk.Progressbar(actions, mode="determinate", length=280)
        self.progress.pack(side="left")
        self.btn_uninstall = ttk.Button(actions, text=language.t("btn.uninstall", n=0),
                                        command=self.uninstall_selected, state="disabled")
        self.btn_uninstall.pack(side="right")
        self.btn_backups = ttk.Button(actions, text=language.t("btn.backups"),
                                      command=self.open_backups)
        self.btn_backups.pack(side="right", padx=6)
        self.btn_export = ttk.Button(actions, text=language.t("btn.report"), command=self.export_report)
        self.btn_export.pack(side="right", padx=6)

        log_frame = ttk.LabelFrame(root, text=language.t("log.cluster"))
        log_frame.pack(fill="x", padx=10, pady=(4, 4))
        self.txt_log = tk.Text(log_frame, height=9, state="disabled", wrap="none",
                               bg="#15181d", fg="#d7dde5",
                               font=("Courier New", 9))
        ysb_log = ttk.Scrollbar(log_frame, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=ysb_log.set)
        for tag, color in (("ok", "#5fbf6f"), ("warn", "#e0a340"), ("err", "#ef6a70")):
            self.txt_log.tag_configure(tag, foreground=color)
        self.txt_log.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        ysb_log.pack(side="right", fill="y", pady=6)

        self.lbl_status = ttk.Label(root, text="", anchor="w", relief="sunken")
        self.lbl_status.pack(fill="x", padx=10, pady=(0, 8))

        self._update_counts()
        self._update_actionbar()

    # --------------------------------------------------------------- log/util

    def log(self, text: str, tag: str | None = None) -> None:
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"[{stamp}] {text}\n", tag or ())
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _set_default_status(self) -> None:
        if not self.serial:
            self.lbl_status.config(text=language.t("status.no_device"))
            return
        if self.busy:
            return
        n = sum(1 for info in self.packages.values() if info.checked)
        self.lbl_status.config(
            text=language.t("status.loaded", n=len(self.packages), sel=n))

    def _spawn(self, fn, *args) -> None:
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _set_busy(self, flag: bool) -> None:
        self.busy = flag
        buttons = (self.btn_refresh, self.btn_scan, self.btn_backups,
                   self.btn_export, self.btn_uninstall, self.btn_sel_safe,
                   self.btn_sel_all, self.btn_unsel)
        if flag:
            for b in buttons:
                b.config(state="disabled")
        else:
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)
            for b in buttons:
                b.config(state="normal")
            self._update_counts()
            self._update_actionbar()
            self._set_default_status()

    def _poll(self) -> None:
        if self._closed:
            return
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self.log(msg[1], msg[2] if len(msg) > 2 else None)
                elif kind == "status":
                    self.lbl_status.config(text=msg[1])
                elif kind == "devices":
                    self._handle_devices(msg[1])
                elif kind == "scan_ok":
                    self._apply_scan(msg[1], msg[2])
                elif kind == "scan_err":
                    self._set_busy(False)
                    self.log(msg[1], "err")
                elif kind == "removed":
                    self.packages.pop(msg[1], None)
                    if self.tree.exists(msg[1]):
                        self.tree.delete(msg[1])
                    self._update_counts()
                    self._update_actionbar()
                    self._set_default_status()
                elif kind == "prog_step":
                    self.progress.step(1)
                elif kind == "prog_max":
                    self.progress.config(mode="determinate", maximum=msg[1], value=0)
                elif kind == "uninstall_done":
                    self._set_busy(False)
                    if msg[1]:
                        self.log(language.t("uninstall.done.ok", n=msg[1]), "ok")
                    else:
                        self.log(language.t("uninstall.done.zero"), "warn")
                elif kind == "restore_done":
                    self._set_busy(False)
                    self.log(language.t("restore.done_log"), "ok")
                    if msg[1] == self.serial:
                        self.log(language.t("restore.rescan_log"))
                        self.scan_packages()
        except queue.Empty:
            pass
        if not self._closed:
            self._after_id = self.root.after(100, self._poll)

    def stop_polling(self) -> None:
        """Arrête proprement la boucle after — utilisé par les tests et la fermeture."""
        self._closed = True
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass

    def _on_close(self) -> None:
        self.stop_polling()
        if self.busy:
            if not messagebox.askyesno(APP_TITLE,
                                       language.t("close.busy")):
                return
        self.root.destroy()

    # ---------------------------------------------------------- appareils

    def refresh_devices(self) -> None:
        if self.busy:
            return
        self.btn_refresh.config(state="disabled")
        self.lbl_dev.config(text=language.t("device.searching"))
        self._spawn(self._th_refresh_devices)

    def _th_refresh_devices(self) -> None:
        try:
            devices = Adb().list_devices()
        except AdbError as exc:
            self.q.put(("log", str(exc), "err"))
            devices = []
        self.q.put(("devices", devices))

    def _handle_devices(self, devices: list[DeviceInfo]) -> None:
        self.btn_refresh.config(state="normal" if not self.busy else "disabled")
        if not devices:
            self.lbl_dev.config(text=language.t("device.none.detected"))
            self.log(language.t("device.none.log"), "warn")
            self._set_default_status()
            return
        for dev in devices:
            if dev.state != "device":
                self.log(language.t("device.state.warn", serial=dev.serial, state=dev.state), "warn")
        usable = [d for d in devices if d.state == "device"]
        if not usable:
            self.lbl_dev.config(text=language.t("device.unauthorized"))
            return
        serial = usable[0].serial if len(usable) == 1 else self._ask_device(usable)
        if serial:
            self._adopt_device(serial, usable)

    def _ask_device(self, devices: list[DeviceInfo]) -> str | None:
        win = tk.Toplevel(self.root)
        win.title(language.t("device.choose.title"))
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text=language.t("device.choose.lead")).pack(padx=12, pady=(12, 6))
        lb = tk.Listbox(win, width=64, height=min(8, len(devices)))
        for dev in devices:
            lb.insert("end", f"{dev.serial} — {dev.model or '?'}")
        lb.pack(padx=12, pady=4)
        lb.selection_set(0)
        result: dict[str, str | None] = {"serial": None}

        def _ok(*_args) -> None:
            sel = lb.curselection()
            if sel:
                result["serial"] = devices[sel[0]].serial
            win.destroy()

        lb.bind("<Double-1>", _ok)
        ttk.Button(win, text=language.t("common.continue_btn"), command=_ok).pack(pady=(4, 12))
        win.wait_window()
        return result["serial"]

    def _adopt_device(self, serial: str, devices: list[DeviceInfo]) -> None:
        dev = next((d for d in devices if d.serial == serial), None)
        self.serial = serial
        self.dev_label = (dev.model if dev and dev.model else "") or serial
        self.lbl_dev.config(text=f"{self.dev_label} ({serial})")
        self.log(language.t("device.selected.log", dev=self.dev_label), "ok")
        self.scan_packages()

    # -------------------------------------------------------------- scan

    def scan_packages(self) -> None:
        if not self.serial or self.busy:
            return
        self._set_busy(True)
        self.progress.config(mode="indeterminate")
        self.progress.start(12)
        self.q.put(("status", language.t("status.scanning")))
        self._spawn(self._th_scan, self.serial)

    def _th_scan(self, serial: str) -> None:
        adb = Adb(serial)
        try:
            props = adb.get_props()
            sys_pkgs = adb.system_packages()
            usr_pkgs = adb.user_packages()
        except AdbError as exc:
            self.q.put(("scan_err", language.t("scan.err", err=exc)))
            return
        if not sys_pkgs and not usr_pkgs:
            self.q.put(("scan_err", language.t("scan.empty")))
            return
        pkgs: dict[str, PackageInfo] = {}
        for pkg in sys_pkgs:
            risk, label, note = bloat_db.lookup(pkg)
            # Rien n'est précoché : l'utilisateur coche explicitement chaque app
            # qu'il veut retirer (le bouton « Cocher les sûrs » reste un raccourci optionnel).
            pkgs[pkg] = PackageInfo(pkg, "system", risk, label, note, checked=False)
        for pkg in usr_pkgs:
            if pkg in pkgs:
                continue
            pkgs[pkg] = PackageInfo(
                pkg, "user", bloat_db.RISK_UNKNOWN, "",
                language.t("note.user_app"))
        self.q.put(("scan_ok", props, pkgs))

    def _apply_scan(self, props: dict[str, str], pkgs: dict[str, PackageInfo]) -> None:
        self._set_busy(False)
        self.packages = pkgs
        self.last_props = props
        brand = props.get("ro.product.brand") or props.get("ro.product.manufacturer") or ""
        model = props.get("ro.product.model") or props.get("ro.product.marketname") or "?"
        release = props.get("ro.build.version.release") or "?"
        patch = props.get("ro.build.version.security_patch") or "?"
        self.dev_label = f"{brand} {model}".strip() or self.serial
        self.lbl_dev.config(
            text=f"{self.dev_label} ({self.serial}) — Android {release} • patch {patch}")

        counts = Counter((info.ptype, info.risk) for info in self.packages.values())
        n_system = sum(counts[("system", r)] for r in RISK_ORDER)
        self.log(language.t("scan.log.total", total=len(pkgs), nsys=n_system,
                            nuser=counts[("user", bloat_db.RISK_UNKNOWN)]), "ok")
        self.log(language.t(
            "scan.log.modes",
            safe=counts[("system", bloat_db.RISK_SAFE)],
            adv=counts[("system", bloat_db.RISK_ADVANCED)]
                + counts[("system", bloat_db.RISK_UNKNOWN)],
            unlisted=counts[("system", bloat_db.RISK_UNKNOWN)],
            prot=counts[("system", bloat_db.RISK_FORBIDDEN)]))
        self.view.set(VIEW_SAFE)
        self.refresh_tree()
        self.q.put(("status", language.t("status.scan_done", total=len(pkgs))))

    # ------------------------------------------------------------- tree

    def _iids(self) -> list[str]:
        query = self.search.get().strip().lower()
        view = self.view.get()

        def sort_key(pkg: str):
            info = self.packages[pkg]
            return (RISK_ORDER.get(info.risk, 9), info.label.lower() or pkg.lower(), pkg)

        def matches(info: PackageInfo, pkg: str) -> bool:
            return (not query or query in pkg.lower()
                    or query in info.label.lower())

        out = []
        for pkg in sorted(self.packages, key=sort_key):
            info = self.packages[pkg]
            if matches(info, pkg):
                if info.ptype == "system" and info.risk == bloat_db.RISK_FORBIDDEN:
                    # Protégés masqués hors des modes : révélés seulement si la
                    # recherche nomme explicitement le paquet (ligne verrouillée).
                    if query:
                        out.append(pkg)
                elif view == VIEW_SAFE:
                    if info.ptype == "system" and info.risk == bloat_db.RISK_SAFE:
                        out.append(pkg)
                elif view == VIEW_ADV:
                    # Mode Avancé : avancées reconnues, non listées et apps utilisateur.
                    if info.ptype == "user" or info.risk in (
                            bloat_db.RISK_ADVANCED, bloat_db.RISK_UNKNOWN):
                        out.append(pkg)
        return out

    def refresh_tree(self) -> None:
        tree = self.tree
        current = tree.get_children()
        if current:
            tree.delete(*current)
        for pkg in self._iids():
            info = self.packages[pkg]
            if info.risk == bloat_db.RISK_FORBIDDEN:
                icon = CHECK_LOCK
            else:
                icon = CHECK_ON if info.checked else CHECK_OFF
            if info.ptype == "system":
                risk_txt = language.risk_text(info.risk)
                tag = f"risk_{info.risk}"
                type_txt = language.t("type.system")
            else:
                risk_txt = language.t("hover.risk_user")
                tag = "risk_user"
                type_txt = language.t("type.user")
            tree.insert("", "end", iid=pkg, values=(icon, info.package, info.label,
                                                    risk_txt, type_txt), tags=(tag,))
        self._update_counts()
        self._update_actionbar()
        self._set_default_status()

    def _toggle_iid(self, iid: str) -> None:
        info = self.packages.get(iid)
        if info is None:
            return
        if not info.checkable():
            self.log(language.t("toggle.refused",
                                pkg=info.package,
                                label=info.label or language.t("protected.fallback")), "warn")
            return
        if self.busy:
            return
        info.checked = not info.checked
        vals = list(self.tree.item(iid, "values"))
        vals[0] = CHECK_ON if info.checked else CHECK_OFF
        self.tree.item(iid, values=vals)
        self._update_actionbar()
        self._set_default_status()

    def _on_tree_click(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) not in ("cell", "tree"):
            return
        self._toggle_iid(self.tree.identify_row(event.y))

    def _on_space(self, _event) -> None:
        # Espace : coche/décoche la ligne sélectionnée au clavier
        selection = self.tree.selection()
        if selection:
            self._toggle_iid(selection[0])
            return "break"

    def _on_tree_double(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        info = self.packages.get(iid)
        if info is None:
            return
        head = info.label or language.t("details.app_head")
        msg = (language.t("details.package", pkg=info.package) + "\n"
               + language.t("details.type", type=language.t(
                   "details.type.system" if info.ptype == "system"
                   else "details.type.user")) + "\n"
               + language.t("details.risk_header",
                            risk=language.risk_text(info.risk)) + "\n\n")
        if info.risk == bloat_db.RISK_FORBIDDEN:
            msg += language.t("details.protected_extra")
        msg += info.note or language.t("details.no_note", pkg=info.package)
        messagebox.showinfo(head, msg, parent=self.root)

    def _on_tree_hover(self, event) -> None:
        if self.busy:
            return
        iid = self.tree.identify_row(event.y)
        info = self.packages.get(iid)
        if info:
            risk = (language.risk_text(info.risk)
                    if info.ptype == "system" else language.t("hover.risk_user"))
            text = f"{info.package} — {info.label or '?'} [{risk}]"
            if info.note:
                text += f" — {info.note}"
            self.lbl_status.config(text=text)

    def select_all(self, only_safe: bool) -> None:
        if self.busy:
            return
        changed = 0
        touched_unlisted = False
        for pkg in self.tree.get_children(""):
            info = self.packages.get(pkg)
            if info is None or not info.checkable():
                continue
            if only_safe and info.risk != bloat_db.RISK_SAFE:
                continue
            if not info.checked:
                info.checked = True
                changed += 1
                if info.risk == bloat_db.RISK_UNKNOWN:
                    touched_unlisted = True
        if changed:
            self.refresh_tree()
            self.log(language.t("select.log.done", n=changed, mode=self.view.get()))
            if touched_unlisted:
                self.log(language.t("select.log.unlisted"), "warn")
        else:
            self.log(language.t("select.log.nothing"))

    def clear_checks(self) -> None:
        if self.busy:
            return
        for info in self.packages.values():
            info.checked = False
        self.refresh_tree()

    # -------------------------------------------------------- désinstallation

    def _update_counts(self) -> None:
        c = Counter((info.ptype, info.risk) for info in self.packages.values())
        self.lbl_counts.config(
            text=language.t("lbl.counts",
                            safe=c[("system", bloat_db.RISK_SAFE)],
                            adv=c[("system", bloat_db.RISK_ADVANCED)],
                            unlisted=c[("system", bloat_db.RISK_UNKNOWN)],
                            user=c[("user", bloat_db.RISK_UNKNOWN)],
                            prot=c[("system", bloat_db.RISK_FORBIDDEN)]))

    def _update_actionbar(self) -> None:
        n = sum(1 for info in self.packages.values() if info.checked)
        self.btn_uninstall.config(
            text=language.t("btn.uninstall", n=n),
            state="disabled" if (self.busy or n == 0) else "normal")

    def uninstall_selected(self) -> None:
        if self.busy:
            return
        targets = [pkg for pkg, info in sorted(self.packages.items())
                   if info.checked and info.checkable()]
        if not targets:
            messagebox.showinfo(APP_TITLE, language.t("confirm.none_checked"), parent=self.root)
            return
        if not self._confirm_uninstall(targets):
            return
        backup_apks = self._propose_apk_backup(targets)
        self._set_busy(True)
        self.progress.config(mode="determinate", maximum=len(targets), value=0)
        self.q.put(("status", language.t("status.uninstalling", n=len(targets))))
        self._spawn(self._th_uninstall, targets, backup_apks)

    def _propose_apk_backup(self, targets: list[str]) -> bool:
        """Avant tout retrait : propose de copier les APK de la sélection sur le PC."""
        if not self.serial:
            return False
        return messagebox.askyesno(
            language.t("confirm.backup.title"),
            language.t("confirm.backup.body"),
            parent=self.root)

    def _confirm_uninstall(self, targets: list[str]) -> bool:
        """Deux modes de confirmation : Sûr = 1 dialogue, Avancé = 2 dialogues.
        Les apps utilisateur gardent leur avertissement de suppression définitive."""
        n_safe = n_adv = n_unlisted = n_user = 0
        for pkg in targets:
            info = self.packages[pkg]
            if info.ptype == "user":
                n_user += 1
            elif info.risk == bloat_db.RISK_SAFE:
                n_safe += 1
            else:
                n_adv += 1
                if info.risk == bloat_db.RISK_UNKNOWN:
                    n_unlisted += 1
        preview = "\n".join(f"  • {self.packages[p].package}" for p in targets[:12])
        if len(targets) > 12:
            preview += "\n  " + language.t("more.items", n=len(targets) - 12)

        if n_adv == 0 and n_user == 0:
            text = language.t("confirm.safe.body", n=len(targets), preview=preview)
            return messagebox.askyesno(language.t("confirm.safe.title"), text,
                                       parent=self.root)

        if n_adv == 0 and n_user:
            # Sélection uniquement utilisateur : le garde-fou de suppression
            # définitive suffit (pas de mode Avancé impliqué).
            return messagebox.askyesno(
                language.t("confirm.user.title"),
                language.t("confirm.user.body", n=n_user),
                parent=self.root, icon="warning")

        text = language.t("confirm.adv.body1", n=len(targets), safe=n_safe,
                          adv=n_adv, unlisted=n_unlisted, user=n_user,
                          preview=preview)
        if not messagebox.askyesno(language.t("confirm.adv.title1"), text,
                                   parent=self.root, icon="warning"):
            return False
        if not messagebox.askyesno(
                language.t("confirm.adv.title2"),
                language.t("confirm.adv.body2"),
                parent=self.root, icon="warning"):
            return False
        if n_user and not messagebox.askyesno(
                language.t("confirm.user.title"),
                language.t("confirm.user.body", n=n_user),
                parent=self.root, icon="warning"):
            return False
        return True

    def _th_uninstall(self, targets: list[str], backup_apks: bool = False) -> None:
        adb = Adb(self.serial)
        ok_count = 0
        if backup_apks:
            self._save_apks(adb, targets)
        for pkg in targets:
            info = self.packages.get(pkg)
            if info is None:
                continue
            try:
                if info.ptype == "user":
                    ok, out = adb.uninstall_user_app(pkg)
                    flavor = language.t("uninstall.flavor.user")
                else:
                    ok, out = adb.uninstall_for_user0(pkg)
                    flavor = language.t("uninstall.flavor.system")
            except AdbError as exc:
                ok, out = False, str(exc)
            if ok:
                ok_count += 1
                self.q.put(("log", language.t("uninstall.ok_log", pkg=pkg,
                                              flavor=flavor), "ok"))
                self.q.put(("removed", pkg))
                self._backup_pkg(pkg, info.ptype)
            else:
                self.q.put(("log", language.t("uninstall.fail_log",
                                              pkg=pkg,
                                              out=out or language.t("fallback.failure")),
                            "err"))
            self.q.put(("prog_step",))
        self.q.put(("uninstall_done", ok_count))

    def _save_apks(self, adb: Adb, targets: list[str]) -> None:
        """Copie les APK de la sélection vers backups/<serial>/apks/<paquet>/."""
        self.q.put(("status", language.t("status.saving_apks")))
        try:
            root = backup.apks_dir(self.serial)
        except OSError as exc:
            self.q.put(("log", language.t("save_apks.mkdir_fail", err=exc), "err"))
            return
        for pkg in targets:
            info = self.packages.get(pkg)
            if info is None:
                continue
            try:
                paths = adb.app_apk_paths(pkg)
            except AdbError as exc:
                self.q.put(("log", language.t("save_apks.not_pulled",
                                              pkg=pkg, err=exc), "warn"))
                continue
            if not paths:
                self.q.put(("log", language.t("save_apks.missing", pkg=pkg), "warn"))
                continue
            dest = os.path.join(root, pkg)
            try:
                os.makedirs(dest, exist_ok=True)
            except OSError as exc:
                self.q.put(("log", language.t("save_apks.not_pulled",
                                              pkg=pkg, err=exc), "warn"))
                continue
            pulled = 0
            for remote in paths:
                good, _out = adb.pull_apk(remote, dest)
                if good:
                    pulled += 1
            if pulled:
                self.q.put(("log", language.t("save_apks.saved", pkg=pkg,
                                              n=pulled, dest=dest), "ok"))
            else:
                self.q.put(("log", language.t("save_apks.all_failed", pkg=pkg), "err"))
        self.q.put(("status", language.t("status.uninstalling", n=len(targets))))

    def _backup_pkg(self, pkg: str, ptype: str) -> None:
        if not self.serial:
            return
        with self._bkl:
            path = backup.backup_path(self.serial)
            ok, message = backup.append_backup(path, self.serial, self.dev_label,
                                               pkg, ptype)
        if not ok:
            self.q.put(("log", message, "err"))
            return
        self.q.put(("log", language.t("backup.updated_log", path=path)))
        if message:
            self.q.put(("log", message, "warn"))

    # ------------------------------------------------------------- restore

    def open_backups(self) -> None:
        if self.busy:
            return
        os.makedirs(backup.BACKUP_DIR, exist_ok=True)
        files = backup.list_backup_files()
        if not files:
            messagebox.showinfo(
                language.t("backups.none.title"),
                language.t("backups.none.body"), parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title(language.t("backups.win.title"))
        win.geometry("760x470")
        win.transient(self.root)
        ttk.Label(win, text=language.t("backups.files_label")).pack(anchor="w", padx=10, pady=(10, 2))
        lb_files = tk.Listbox(win, height=5)
        for path in files:
            lb_files.insert("end", os.path.basename(path))
        lb_files.pack(fill="x", padx=10, pady=2)
        lb_files.selection_set(0)
        txt = tk.Text(win, height=16, state="disabled", wrap="none",
                      bg="#15181d", fg="#d7dde5", font=("Courier New", 9))
        ysb = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=ysb.set)

        def _show_details(_event=None) -> None:
            sel = lb_files.curselection()
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            if sel:
                path = files[sel[0]]
                try:
                    with open(path, encoding="utf-8") as fh:
                        data = json.load(fh)
                except (OSError, json.JSONDecodeError) as exc:
                    txt.insert("end", language.t("backups.read_fail", err=exc) + "\n")
                else:
                    txt.insert("end", language.t("backups.detail.device",
                                                 dev=data.get("device") or "?") + "\n")
                    txt.insert("end", language.t("backups.detail.serial",
                                                 srl=data.get("serial") or "?") + "\n\n")
                    for h in data.get("history", []):
                        txt.insert("end", f"{h.get('date', '?')}  "
                                          f"{'sys ' if h.get('type') == 'system' else 'user'}  "
                                          f"{h.get('package')}\n")
                        txt.see("end")
            txt.configure(state="disabled")

        def _restore() -> None:
            sel = lb_files.curselection()
            if not sel:
                return
            path = files[sel[0]]
            if not messagebox.askyesno(
                    language.t("restore.confirm.title"),
                    language.t("restore.confirm.body"),
                    parent=win):
                return
            win.destroy()
            self._set_busy(True)
            self.progress.config(mode="determinate", value=0)
            self._spawn(self._th_restore, path)

        lb_files.bind("<<ListboxSelect>>", _show_details)
        ttk.Button(win, text=language.t("btn.restore_this"), command=_restore).pack(pady=8)
        txt.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(6, 10))
        ysb.pack(side="right", fill="y", pady=(6, 10), padx=(0, 10))
        _show_details()

    def _th_restore(self, path: str) -> None:
        data, err = backup.read_backup(path)
        if data is None:
            self.q.put(("log", language.t("restore.read_fail", err=err), "err"))
            self.q.put(("restore_done", self.serial))
            return
        serial = data.get("serial") or self.serial
        adb = Adb(serial)
        self.q.put(("log", language.t("restore.start_log",
                                      name=os.path.basename(path), serial=serial), "ok"))
        self.q.put(("prog_max", len(backup.entries(data))))
        for entry in backup.entries(data):
            pkg = entry.get("package") or ""
            if entry.get("type") == "user":
                self.q.put(("log", language.t("restore.skip_user", pkg=pkg), "warn"))
                continue
            try:
                ok, out = adb.install_existing(pkg)
            except AdbError as exc:
                ok, out = False, str(exc)
            if ok:
                self.q.put(("log", language.t("restore.ok_log", pkg=pkg), "ok"))
            else:
                self.q.put(("log", language.t("restore.fail_log",
                                              pkg=pkg,
                                              out=out or language.t("fallback.failure")),
                            "err"))
            self.q.put(("prog_step",))
        self.q.put(("restore_done", serial))

    # ----------------------------------------------------------------- export

    def export_report(self) -> None:
        if not self.serial or not self.packages:
            messagebox.showinfo(
                language.t("export.none.title"),
                language.t("export.none.body"),
                parent=self.root)
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = (f"scan_{backup.safe_filename(self.serial)}_{stamp}.json")
        path = filedialog.asksaveasfilename(
            title=language.t("export.dialog.title"),
            initialfile=default_name,
            defaultextension=".json",
            filetypes=[(language.t("export.filetypes.json"), "*.json"),
                       (language.t("export.filetypes.all"), "*")],
            parent=self.root)
        if not path:
            return
        c = Counter((info.ptype, info.risk) for info in self.packages.values())
        payload = {
            "tool": f"{APP_TITLE} v{APP_VERSION}",
            "device": self.dev_label,
            "serial": self.serial,
            "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "counts": {
                "system": {r: c[("system", r)] for r in RISK_ORDER},
                "user": c[("user", bloat_db.RISK_UNKNOWN)],
            },
            "props": self.last_props,
            "apps": [
                {
                    "package": info.package,
                    "type": info.ptype,
                    "risk": info.risk,
                    "label": info.label,
                    "note": info.note,
                    "selected": info.checked,
                }
                for info in sorted(self.packages.values(),
                                   key=lambda i: (RISK_ORDER.get(i.risk, 9), i.package))
            ],
        }
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=1, ensure_ascii=False)
        except OSError as exc:
            self.log(language.t("export.write_fail", err=exc), "err")
            return
        self.log(language.t("export.ok_log", path=path), "ok")

    # ----------------------------------------------------------------- aide

    def show_help(self) -> None:
        win = tk.Toplevel(self.root)
        win.title(language.t("help.title"))
        win.geometry("700x540")
        win.transient(self.root)
        txt = tk.Text(win, wrap="word", padx=14, pady=10, font=("TkDefaultFont", 10))
        ysb = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=ysb.set)
        txt.insert("1.0", help_text())
        txt.configure(state="disabled")
        txt.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")


def ask_language(root: "tk.Tk") -> str:
    """Mini-fenêtre de choix de langue, avant la construction de l'interface.

    Deux boutons : « Français » et « English ». Fermer la fenêtre (croix)
    revient à rester en français (défaut).
    """
    win = tk.Toplevel(root)
    win.title("Langue / Language")
    win.geometry("400x180")
    win.resizable(False, False)
    win.transient(root)
    chosen: dict[str, str] = {"lang": ""}

    def _pick(code: str) -> None:
        chosen["lang"] = code
        win.destroy()

    ttk.Label(win, text="Choisis ta langue / Choose your language:",
              font=("", 11, "bold")).pack(pady=(20, 12))
    row = ttk.Frame(win)
    row.pack()
    ttk.Button(row, text="Français", width=16,
               command=lambda: _pick("fr")).pack(side="left", padx=8)
    ttk.Button(row, text="English", width=16,
               command=lambda: _pick("en")).pack(side="left", padx=8)
    win.protocol("WM_DELETE_WINDOW", lambda: _pick("fr"))
    root.wait_window(win)
    return chosen["lang"] or "fr"


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    language.set_lang(ask_language(root))
    root.deiconify()
    DebloatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
