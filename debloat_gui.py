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
from adb import Adb, AdbError, DeviceInfo

APP_TITLE = "Debloat Android"
APP_VERSION = "1.3.0"

RISK_ORDER = {
    bloat_db.RISK_SAFE: 0,
    bloat_db.RISK_ADVANCED: 1,
    bloat_db.RISK_UNKNOWN: 2,
    bloat_db.RISK_FORBIDDEN: 3,
}

# Deux modes seulement : « Sûr » (recommandées) et « Avancé » (prudence).
# Les paquets hors base s'affichent comme avancées non listées ; les composants
# protégés ne font pas partie des modes : masqués, retrouvables par la recherche.
RISK_TEXT = {
    bloat_db.RISK_SAFE: "sûre",
    bloat_db.RISK_ADVANCED: "avancée",
    bloat_db.RISK_UNKNOWN: "avancée (non listée)",
    bloat_db.RISK_FORBIDDEN: "protégée (verrouillée)",
}

VIEW_SAFE = "safe"
VIEW_ADV = "advanced"

CHECK_ON, CHECK_OFF, CHECK_LOCK = "[x]", "[ ]", "[!]"

HELP_TEXT = f"""\
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
        self.log("Bienvenue ! Branche ton téléphone (debogage USB active), puis clique « Rafraîchir les appareils ».\n"
                 "Rien n'est coché d'office : coche chaque app que tu veux retirer, puis « Désinstaller la sélection ».")
        self.refresh_devices()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = self.root

        # ---------------------------------------------------------- header
        head = ttk.Frame(root)
        head.pack(fill="x", padx=10, pady=(10, 4))
        self.lbl_dev = ttk.Label(head, text="Aucun appareil", font=("", 11, "bold"))
        self.lbl_dev.pack(side="left")
        self.btn_help = ttk.Button(head, text="Aide", command=self.show_help)
        self.btn_help.pack(side="right")
        self.btn_scan = ttk.Button(head, text="Scanner les applications",
                                   command=self.scan_packages, state="disabled")
        self.btn_scan.pack(side="right", padx=6)
        self.btn_refresh = ttk.Button(head, text="Rafraîchir les appareils",
                                      command=self.refresh_devices)
        self.btn_refresh.pack(side="right", padx=6)

        # ------------------------------------------------------------ body
        body = ttk.Frame(root)
        body.pack(fill="both", expand=True, padx=10, pady=4)

        left = ttk.Frame(body, width=235)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="Mode", font=("", 10, "bold")).pack(anchor="w", pady=(0, 2))
        for value, text in (
            (VIEW_SAFE, "Sûr — recommandées"),
            (VIEW_ADV, "Avancé — prudence"),
        ):
            ttk.Radiobutton(left, text=text, value=value, variable=self.view,
                            command=self.refresh_tree).pack(anchor="w", pady=1)
        self.lbl_counts = ttk.Label(left, text="", foreground="#55606e", justify="left")
        self.lbl_counts.pack(anchor="w", pady=(8, 4))

        self.btn_sel_safe = ttk.Button(left, text="Cocher les sûres (mode)",
                                       command=lambda: self.select_all(True))
        self.btn_sel_all = ttk.Button(left, text="Tout cocher (mode)",
                                      command=lambda: self.select_all(False))
        self.btn_unsel = ttk.Button(left, text="Décocher tout", command=self.clear_checks)
        self.btn_sel_safe.pack(fill="x", pady=(6, 2))
        self.btn_sel_all.pack(fill="x", pady=2)
        self.btn_unsel.pack(fill="x", pady=2)
        ttk.Label(left, text="Le mode « Avancé » demande\ndes confirmations supplémentaires.",
                  foreground="#a25c00", justify="left").pack(anchor="w", pady=(10, 0))

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        srow = ttk.Frame(right)
        srow.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Label(srow, text="Recherche :").pack(side="left")
        ttk.Entry(srow, textvariable=self.search).pack(side="left", fill="x", expand=True, padx=6)
        self.search.trace_add("write", lambda *_: self.refresh_tree())

        cols = ("check", "package", "app", "risk", "type")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", selectmode="browse")
        for col, text, width, anchor in (
            ("check", "Cocher", 64, "center"),
            ("package", "Paquet", 390, "w"),
            ("app", "Application", 210, "w"),
            ("risk", "Risque", 130, "w"),
            ("type", "Type", 90, "w"),
        ):
            self.tree.heading(col, text=text)
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
        self.btn_uninstall = ttk.Button(actions, text="Désinstaller la sélection (0)",
                                        command=self.uninstall_selected, state="disabled")
        self.btn_uninstall.pack(side="right")
        self.btn_backups = ttk.Button(actions, text="Gestionnaire de backups",
                                      command=self.open_backups)
        self.btn_backups.pack(side="right", padx=6)
        self.btn_export = ttk.Button(actions, text="Rapport", command=self.export_report)
        self.btn_export.pack(side="right", padx=6)

        log_frame = ttk.LabelFrame(root, text="Journal")
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
            self.lbl_status.config(text="Connecte un téléphone (débogage USB activé), puis « Rafraîchir les appareils ».")
            return
        if self.busy:
            return
        n = sum(1 for info in self.packages.values() if info.checked)
        self.lbl_status.config(
            text=f"{len(self.packages)} apps chargées — sélection : {n} — "
                 "un clic sur une ligne coche/décoche, survol = note, double-clic = détails.")

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
                        self.log(f"Terminé : {msg[1]} désinstallation(s) réussie(s). "
                                 "Les apps système restent restaurables via le gestionnaire de backups.", "ok")
                    else:
                        self.log("Terminé : aucune désinstallation réussie — détail dans le journal.", "warn")
                elif kind == "restore_done":
                    self._set_busy(False)
                    self.log("Restauration terminée.", "ok")
                    if msg[1] == self.serial:
                        self.log("Nouveau scan pour mettre la liste à jour…")
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
                                       "Une opération est en cours — quitter quand même ?"):
                return
        self.root.destroy()

    # ---------------------------------------------------------- appareils

    def refresh_devices(self) -> None:
        if self.busy:
            return
        self.btn_refresh.config(state="disabled")
        self.lbl_dev.config(text="Recherche des appareils…")
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
            self.lbl_dev.config(text="Aucun appareil détecté")
            self.log("Aucun appareil ADB. Vérifie : câble, « Débogage USB » dans les options pour développeurs, "
                     "autorisation sur le téléphone (bouton Aide).", "warn")
            self._set_default_status()
            return
        for dev in devices:
            if dev.state != "device":
                self.log(f"{dev.serial} : état « {dev.state} » — autorise le débogage USB sur le téléphone.", "warn")
        usable = [d for d in devices if d.state == "device"]
        if not usable:
            self.lbl_dev.config(text="Appareil détecté mais non autorisé")
            return
        serial = usable[0].serial if len(usable) == 1 else self._ask_device(usable)
        if serial:
            self._adopt_device(serial, usable)

    def _ask_device(self, devices: list[DeviceInfo]) -> str | None:
        win = tk.Toplevel(self.root)
        win.title("Choisir un appareil")
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="Plusieurs appareils sont détectés :").pack(padx=12, pady=(12, 6))
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
        ttk.Button(win, text="Continuer", command=_ok).pack(pady=(4, 12))
        win.wait_window()
        return result["serial"]

    def _adopt_device(self, serial: str, devices: list[DeviceInfo]) -> None:
        dev = next((d for d in devices if d.serial == serial), None)
        self.serial = serial
        self.dev_label = (dev.model if dev and dev.model else "") or serial
        self.lbl_dev.config(text=f"{self.dev_label} ({serial})")
        self.log(f"Appareil sélectionné : {self.dev_label} — scan des applications... ", "ok")
        self.scan_packages()

    # -------------------------------------------------------------- scan

    def scan_packages(self) -> None:
        if not self.serial or self.busy:
            return
        self._set_busy(True)
        self.progress.config(mode="indeterminate")
        self.progress.start(12)
        self.q.put(("status", "Scan des applications en cours…"))
        self._spawn(self._th_scan, self.serial)

    def _th_scan(self, serial: str) -> None:
        adb = Adb(serial)
        try:
            props = adb.get_props()
            sys_pkgs = adb.system_packages()
            usr_pkgs = adb.user_packages()
        except AdbError as exc:
            self.q.put(("scan_err", f"Scan échoué : {exc}"))
            return
        if not sys_pkgs and not usr_pkgs:
            self.q.put(("scan_err", "Réponse vide — l'appareil a peut-être été débranché."))
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
                "App installée après l'achat (Play Store…). Sa désinstallation est définitive.")
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
        self.log(f"Scan : {len(pkgs)} apps au total — {n_system} système, "
                 f"{counts[('user', bloat_db.RISK_UNKNOWN)]} utilisateur", "ok")
        self.log(f"   mode Sûr : {counts[('system', bloat_db.RISK_SAFE)]} • "
                 f"mode Avancé : {counts[('system', bloat_db.RISK_ADVANCED)] + counts[('system', bloat_db.RISK_UNKNOWN)]} "
                 f"(dont {counts[('system', bloat_db.RISK_UNKNOWN)]} non listée(s)) — "
                 f"protégées masquées : {counts[('system', bloat_db.RISK_FORBIDDEN)]}")
        self.view.set(VIEW_SAFE)
        self.refresh_tree()
        self.q.put(("status", f"Scan fini — {len(pkgs)} apps. "
                            "Coche chaque app à retirer (clic sur la ligne), puis « Désinstaller »."))

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
                risk_txt = RISK_TEXT.get(info.risk, info.risk)
                tag = f"risk_{info.risk}"
                type_txt = "système"
            else:
                risk_txt = "app utilisateur"
                tag = "risk_user"
                type_txt = "utilisateur"
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
            self.log(f"Refusé : {info.package} est un composant protégé ({info.label or 'vital pour le système'}) — "
                     "l'app bloque volontairement sa désinstallation.", "warn")
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
        head = info.label or "Application"
        msg = (f"Paquet : {info.package}\n"
               f"Type : {'app système' if info.ptype == 'system' else 'app utilisateur (Play Store…)'}\n"
               f"Risque : {RISK_TEXT.get(info.risk, info.risk)}\n\n")
        if info.risk == bloat_db.RISK_FORBIDDEN:
            msg += "Composant protégé — l'app bloque volontairement sa désinstallation.\n\n"
        msg += info.note or "Pas de note particulière. En cas de doute, cherche « debloat " \
                            + info.package + " » sur le web."
        messagebox.showinfo(head, msg, parent=self.root)

    def _on_tree_hover(self, event) -> None:
        if self.busy:
            return
        iid = self.tree.identify_row(event.y)
        info = self.packages.get(iid)
        if info:
            risk = (RISK_TEXT.get(info.risk, info.risk)
                    if info.ptype == "system" else "app utilisateur")
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
            self.log(f"{changed} app(s) cochée(s) (mode « {self.view.get()} »).")
            if touched_unlisted:
                self.log("La sélection contient des paquets non répertoriés — "
                         "vérifie un par un.", "warn")
        else:
            self.log("Rien de nouveau à cocher dans le mode courant.")

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
            text=(f"Sûres : {c[('system', bloat_db.RISK_SAFE)]}\n"
                  f"Avancées : {c[('system', bloat_db.RISK_ADVANCED)]} "
                  f"(dont {c[('system', bloat_db.RISK_UNKNOWN)]} non listées)\n"
                  f"Utilisateur : {c[('user', bloat_db.RISK_UNKNOWN)]}\n"
                  f"Protégées (verrouillées) : {c[('system', bloat_db.RISK_FORBIDDEN)]}"))

    def _update_actionbar(self) -> None:
        n = sum(1 for info in self.packages.values() if info.checked)
        self.btn_uninstall.config(
            text=f"Désinstaller la sélection ({n})",
            state="disabled" if (self.busy or n == 0) else "normal")

    def uninstall_selected(self) -> None:
        if self.busy:
            return
        targets = [pkg for pkg, info in sorted(self.packages.items())
                   if info.checked and info.checkable()]
        if not targets:
            messagebox.showinfo(APP_TITLE, "Aucune app cochée.", parent=self.root)
            return
        if not self._confirm_uninstall(targets):
            return
        backup_apks = self._propose_apk_backup(targets)
        self._set_busy(True)
        self.progress.config(mode="determinate", maximum=len(targets), value=0)
        self.q.put(("status", f"Désinstallation de {len(targets)} app(s)…"))
        self._spawn(self._th_uninstall, targets, backup_apks)

    def _propose_apk_backup(self, targets: list[str]) -> bool:
        """Avant tout retrait : propose de copier les APK de la sélection sur le PC."""
        if not self.serial:
            return False
        return messagebox.askyesno(
            "Sauvegarde avant retrait",
            "Sauvegarder les APK de la sélection sur le PC avant de les retirer ?\n\n"
            "Destination : backups/<serial>/apks/<paquet>/\n\n"
            "Le journal de restauration (backups/<serial>.json) est, lui,\n"
            "créé automatiquement de toute façon.",
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
            preview += f"\n  … et {len(targets) - 12} autre(s)"

        if n_adv == 0 and n_user == 0:
            text = (f"Retirer {len(targets)} app(s) « sûres » ?\n\n"
                    f"{preview}\n\n"
                    "Les apps système restent restaurables (gestionnaire de backups).\n"
                    "Continuer ?")
            return messagebox.askyesno("Mode Sûr — confirmation", text, parent=self.root)

        if n_adv == 0 and n_user:
            # Sélection uniquement utilisateur : le garde-fou de suppression
            # définitive suffit (pas de mode Avancé impliqué).
            return messagebox.askyesno(
                "Apps utilisateur — SUPPRESSION DÉFINITIVE",
                f"{n_user} app(s) utilisateur seront définitivement supprimées\n"
                "(données perdues — réinstallables seulement via une boutique).\n\n"
                "Confirmer ?", parent=self.root, icon="warning")

        text = (f"MODE AVANCÉ — tu vas retirer {len(targets)} app(s) :\n\n"
                f" • {n_safe} sûre(s)\n"
                f" • {n_adv} avancée(s) (dont {n_unlisted} non listée(s))\n"
                f" • {n_user} utilisateur(s) — SUPPRESSION DÉFINITIVE\n\n"
                f"{preview}\n\n"
                "Une fonctionnalité peut manquer après le retrait (cloud, notes,\n"
                "caméra, réseau…). Les apps système restent restaurables ;\n"
                "les apps utilisateur, non.\n\n"
                "Continuer ?")
        if not messagebox.askyesno("Mode Avancé — confirmation 1/2", text,
                                   parent=self.root, icon="warning"):
            return False
        if not messagebox.askyesno(
                "Mode Avancé — confirmation 2/2",
                "Dernière vérification avant de retirer.\n\n"
                "Relis les lignes au-dessus : ce retrait est-il vraiment voulu ?\n\n"
                "Confirmer définitivement ?",
                parent=self.root, icon="warning"):
            return False
        if n_user and not messagebox.askyesno(
                "Apps utilisateur — SUPPRESSION DÉFINITIVE",
                f"{n_user} app(s) utilisateur seront définitivement supprimées\n"
                "(données perdues — réinstallables seulement via une boutique).\n\n"
                "Confirmer ?", parent=self.root, icon="warning"):
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
                    flavor = "app utilisateur"
                else:
                    ok, out = adb.uninstall_for_user0(pkg)
                    flavor = "profil 0"
            except AdbError as exc:
                ok, out = False, str(exc)
            if ok:
                ok_count += 1
                self.q.put(("log", f"OK  {pkg} retiré ({flavor}).", "ok"))
                self.q.put(("removed", pkg))
                self._backup_pkg(pkg, info.ptype)
            else:
                self.q.put(("log", f"ÉCHEC  {pkg} : {out or 'échec'}", "err"))
            self.q.put(("prog_step",))
        self.q.put(("uninstall_done", ok_count))

    def _save_apks(self, adb: Adb, targets: list[str]) -> None:
        """Copie les APK de la sélection vers backups/<serial>/apks/<paquet>/."""
        self.q.put(("status", "Sauvegarde des APK de la sélection…"))
        try:
            root = backup.apks_dir(self.serial)
        except OSError as exc:
            self.q.put(("log", f"Impossible de créer le dossier des APK : {exc}", "err"))
            return
        for pkg in targets:
            info = self.packages.get(pkg)
            if info is None:
                continue
            try:
                paths = adb.app_apk_paths(pkg)
            except AdbError as exc:
                self.q.put(("log", f"APK non sauvegardé ({pkg}) : {exc}", "warn"))
                continue
            if not paths:
                self.q.put(("log", f"APK introuvable sur l'appareil ({pkg}).", "warn"))
                continue
            dest = os.path.join(root, pkg)
            try:
                os.makedirs(dest, exist_ok=True)
            except OSError as exc:
                self.q.put(("log", f"APK non sauvegardé ({pkg}) : {exc}", "warn"))
                continue
            pulled = 0
            for remote in paths:
                good, _out = adb.pull_apk(remote, dest)
                if good:
                    pulled += 1
            if pulled:
                self.q.put(("log", f"APK sauvegardé : {pkg} ({pulled} fichier(s) -> {dest})", "ok"))
            else:
                self.q.put(("log", f"Échec de la sauvegarde APK ({pkg}).", "err"))
        self.q.put(("status", f"Désinstallation de {len(targets)} app(s)…"))

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
        self.q.put(("log", f"Backup mis à jour : {path}"))
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
                "Gestionnaire de backups",
                "Aucun backup pour le moment.\nUn fichier backups/<serial>.json est créé\n"
                "automatiquement à la première désinstallation.", parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title("Gestionnaire de backups — restauration")
        win.geometry("760x470")
        win.transient(self.root)
        ttk.Label(win, text="Fichiers de backup :").pack(anchor="w", padx=10, pady=(10, 2))
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
                    txt.insert("end", f"Impossible de lire ce backup : {exc}\n")
                else:
                    txt.insert("end", f"Appareil : {data.get('device') or '?'}\n")
                    txt.insert("end", f"Serial  : {data.get('serial') or '?'}\n\n")
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
                    "Restaurer",
                    "Réinstaller TOUTES les apps système de ce backup sur le téléphone\n"
                    "(les apps utilisateur doivent être réinstallées à la main) ?",
                    parent=win):
                return
            win.destroy()
            self._set_busy(True)
            self.progress.config(mode="determinate", value=0)
            self._spawn(self._th_restore, path)

        lb_files.bind("<<ListboxSelect>>", _show_details)
        ttk.Button(win, text="Restaurer ce backup", command=_restore).pack(pady=8)
        txt.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(6, 10))
        ysb.pack(side="right", fill="y", pady=(6, 10), padx=(0, 10))
        _show_details()

    def _th_restore(self, path: str) -> None:
        data, err = backup.read_backup(path)
        if data is None:
            self.q.put(("log", f"Lecture du backup impossible : {err}", "err"))
            self.q.put(("restore_done", self.serial))
            return
        serial = data.get("serial") or self.serial
        adb = Adb(serial)
        self.q.put(("log", f"Restauration de {os.path.basename(path)} sur {serial}…", "ok"))
        self.q.put(("prog_max", len(backup.entries(data))))
        for entry in backup.entries(data):
            pkg = entry.get("package") or ""
            if entry.get("type") == "user":
                self.q.put(("log", f"{pkg} : app utilisateur — réinstalle-la à la main "
                                   "(Play Store ou APK).", "warn"))
                continue
            try:
                ok, out = adb.install_existing(pkg)
            except AdbError as exc:
                ok, out = False, str(exc)
            if ok:
                self.q.put(("log", f"OK  {pkg} restauré.", "ok"))
            else:
                self.q.put(("log", f"ÉCHEC  {pkg} : {out or 'échec'}", "err"))
            self.q.put(("prog_step",))
        self.q.put(("restore_done", serial))

    # ----------------------------------------------------------------- export

    def export_report(self) -> None:
        if not self.serial or not self.packages:
            messagebox.showinfo(
                "Exporter le rapport",
                "Aucun scan à exporter.\nConnecte un appareil et fais « Scanner les applications ».",
                parent=self.root)
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = (f"scan_{backup.safe_filename(self.serial)}_{stamp}.json")
        path = filedialog.asksaveasfilename(
            title="Exporter le rapport de scan",
            initialfile=default_name,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Tous les fichiers", "*")],
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
            self.log(f"Écriture du rapport impossible : {exc}", "err")
            return
        self.log(f"Rapport exporté : {path}", "ok")

    # ----------------------------------------------------------------- aide

    def show_help(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Aide — Debloat Android")
        win.geometry("700x540")
        win.transient(self.root)
        txt = tk.Text(win, wrap="word", padx=14, pady=10, font=("TkDefaultFont", 10))
        ysb = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=ysb.set)
        txt.insert("1.0", HELP_TEXT)
        txt.configure(state="disabled")
        txt.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    DebloatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
