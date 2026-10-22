#!/usr/bin/env python3
"""Debloat Android — compagnon CLI (sans interface graphique).

Mêmes règles que la GUI :
  - apps système seulement : `pm uninstall --user 0` (réversible),
  - composants protégés refusés,
  - apps utilisateur (suppression définitive) et paquets inconnus :
    opt-in explicite,
  - tout retrait réussi est consigné dans backups/<serial>.json.

Exemples :
    python3 debloat_cli.py devices
    python3 debloat_cli.py scan
    python3 debloat_cli.py scan --risk safe,advanced
    python3 debloat_cli.py scan --json
    python3 debloat_cli.py uninstall com.miui.msa.global --yes
    python3 debloat_cli.py uninstall --dry-run com.facebook.appmanager
    python3 debloat_cli.py restore --file backups/123ABC.json --yes
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from collections import Counter

import bloat_db
import backup
from adb import Adb, AdbError, DeviceInfo  # noqa: F401 — DeviceInfo exposé pour les tests

RISK_ORDER = {
    bloat_db.RISK_SAFE: 0,
    bloat_db.RISK_ADVANCED: 1,
    bloat_db.RISK_UNKNOWN: 2,
    bloat_db.RISK_FORBIDDEN: 3,
}



EXIT_OK, EXIT_ERR, EXIT_REFUSED = 0, 1, 2


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        answer = input(f"{prompt} [o/N] ")
    except EOFError:
        print("\n(interruption — abandon)")
        return False
    return answer.strip().lower() in ("o", "oui", "y", "yes")


def pick_adb(args) -> Adb:
    """Choisit la cible : --serial, sinon l'unique appareil ADB utilisable."""
    if args.serial:
        return Adb(args.serial)
    devices = Adb().list_devices()
    usable = [d for d in devices if d.state == "device"]
    if not usable:
        print("Aucun appareil ADB utilisable. Câble + débogage USB + autorisation.",
              file=sys.stderr)
        raise SystemExit(EXIT_ERR)
    for dev in devices:
        if dev.state != "device":
            print(f"{dev.serial} : état « {dev.state} » ignoré.", file=sys.stderr)
    if len(usable) > 1:
        print("Plusieurs appareils connectés — précise --serial parmi :", file=sys.stderr)
        for dev in usable:
            print(f"   {dev.serial}   {dev.model or '?'}", file=sys.stderr)
        raise SystemExit(EXIT_ERR)
    return Adb(usable[0].serial)


def _scan(adb: Adb) -> tuple[dict[str, dict], dict[str, str]]:
    """Scan complet. Renvoie ({pkg: {type, risk, label, note}}, props)."""
    props = adb.get_props()
    apps: dict[str, dict] = {}
    for pkg in adb.system_packages():
        risk, label, note = bloat_db.lookup(pkg)
        apps[pkg] = {"type": "system", "risk": risk, "label": label, "note": note}
    for pkg in adb.user_packages():
        if pkg in apps:
            continue
        apps[pkg] = {"type": "user", "risk": "user", "label": "", "note": ""}
    return apps, props


def _device_label(props: dict[str, str], serial: str) -> str:
    brand = props.get("ro.product.brand") or props.get("ro.product.manufacturer") or ""
    model = props.get("ro.product.model") or props.get("ro.product.marketname") or ""
    return " ".join((brand, model)).strip() or serial


def cmd_devices(_args) -> int:
    print("Appareils ADB :")
    for dev in Adb().list_devices():
        print(f"  {dev.serial:<28} {dev.state:<13} {dev.model or '?'}")
    return EXIT_OK


def cmd_scan(args) -> int:
    adb = pick_adb(args)
    apps, props = _scan(adb)
    ordered = sorted(apps, key=lambda p: (RISK_ORDER.get(apps[p]["risk"], 9), p))
    counts = Counter(apps[p]["risk"] for p in ordered)

    want_risks = {r.strip() for r in (args.risk or "").split(",") if r.strip()}
    query = (args.search or "").strip().lower()
    shown = [
        p for p in ordered
        if (not want_risks or apps[p]["risk"] in want_risks)
        and (not query or query in p.lower()
             or query in (apps[p]["label"] or "").lower())
    ]

    want_table = args.rule or (not args.json and not args.report)
    if want_table:
        print(f"Appareil : {_device_label(props, adb.serial)}"
              + (f"  —  filtre « {args.search} »" if query else ""))
        print(f"Total : {len(apps)} app(s) — "
              + " • ".join(f"{r} {counts[r]}" for r in
                           ("safe", "advanced", "unknown", "forbidden", "user")))
        print("-" * 78)
        for pkg in shown:
            info = apps[pkg]
            if info["type"] == "user":
                suffix = "  (app utilisateur)"
            elif info["label"]:
                suffix = f"  ({info['label']})"
            else:
                suffix = ""
            print(f"{pkg}{suffix}")
    if not shown and (args.search or want_risks):
        print("(aucune app correspondante)")

    payload = {
        "tool": "debloat-android CLI",
        "serial": adb.serial,
        "device": _device_label(props, adb.serial),
        "created": _now(),
        "counts": {
            "safe": counts["safe"],
            "advanced": counts["advanced"],
            "unknown": counts["unknown"],
            "forbidden": counts["forbidden"],
            "user": counts["user"],
        },
        "props": props,
        "apps": [{"package": p, **apps[p]} for p in ordered],
    }
    if args.json:
        print(json.dumps(payload, indent=1, ensure_ascii=False))
    if args.report:
        try:
            with open(args.report, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=1, ensure_ascii=False)
        except OSError as exc:
            print(f"Écriture du rapport impossible : {exc}", file=sys.stderr)
            return EXIT_ERR
        print(f"Rapport écrit : {args.report}")
    return EXIT_OK


def cmd_uninstall(args) -> int:
    adb = pick_adb(args)
    apps, props = _scan(adb)
    device = _device_label(props, adb.serial)

    targets: list[str] = []
    for pkg in args.packages:
        if pkg not in apps:
            print(f"{pkg} n'est pas installé sur l'appareil.", file=sys.stderr)
            return EXIT_ERR
        targets.append(pkg)

    forbidden = [p for p in targets if apps[p]["risk"] == bloat_db.RISK_FORBIDDEN]
    unknown = [p for p in targets if apps[p]["type"] == "system"
               and apps[p]["risk"] == bloat_db.RISK_UNKNOWN]
    users = [p for p in targets if apps[p]["type"] == "user"]

    if forbidden:
        print("Refusé : composants système protégés", file=sys.stderr)
        for pkg in forbidden:
            print(f"   {pkg}   {bloat_db.lookup(pkg)[1]}", file=sys.stderr)
        return EXIT_REFUSED
    if unknown and not args.allow_unknown:
        print("Refusé : paquet(s) inconnu(s) de la base — relance avec --allow-unknown "
              "si tu sais ce que tu fais :", file=sys.stderr)
        for pkg in unknown:
            print(f"   {pkg}", file=sys.stderr)
        return EXIT_REFUSED
    if users and not args.allow_user_apps:
        print("Refusé : app(s) utilisateur — la suppression est DÉFINITIVE (données "
              "perdues). Relance avec --allow-user-apps si nécessaire :", file=sys.stderr)
        for pkg in users:
            print(f"   {pkg}", file=sys.stderr)
        return EXIT_REFUSED

    if args.dry_run:
        print(f"Simulation (--dry-run) sur {device} :")
        for pkg in targets:
            flavor = ("pm uninstall <pkg>" if apps[pkg]["type"] == "user"
                      else "pm uninstall --user 0 <pkg>")
            print(f"  adb -s {adb.serial} shell {flavor} {pkg}")
        return EXIT_OK

    counts = Counter(apps[p]["risk"] for p in targets)
    if not _confirm(
            f"Retirer {len(targets)} app(s) sur {device} "
            f"(sûres {counts['safe']} • avancées {counts['advanced']} • "
            f"inconnues {counts['unknown']} • utilisateur {counts['user']}) ?",
            args.yes):
        print("Abandon.")
        return EXIT_OK

    if args.backup_apks:
        _save_apks(adb, targets)

    failures = 0
    for pkg in targets:
        try:
            if apps[pkg]["type"] == "user":
                ok, out = adb.uninstall_user_app(pkg)
            else:
                ok, out = adb.uninstall_for_user0(pkg)
        except AdbError as exc:
            ok, out = False, str(exc)
        if ok:
            print(f"OK  {pkg} retiré.")
            path = backup.backup_path(adb.serial)
            good, message = backup.append_backup(path, adb.serial, device, pkg,
                                                 apps[pkg]["type"])
            if not good:
                print(message, file=sys.stderr)
            elif message:
                print(message, file=sys.stderr)
        else:
            failures += 1
            print(f"Échec  {pkg} : {out or 'échec'}")
    if failures:
        print(f"{len(targets) - failures} ok, {failures} échec(s).")
        return EXIT_ERR
    print(f"{len(targets)} retrait(s) réussi(s) — consigné(s) dans "
          f"backups/{backup.safe_filename(adb.serial)}.json")
    return EXIT_OK


def _save_apks(adb: Adb, targets: list[str]) -> None:
    """Copie les APK de la cible dans backups/<serial>/apks/<paquet>/ avant retrait."""
    try:
        root = backup.apks_dir(adb.serial)
    except OSError as exc:
        print(f"Impossible de créer le dossier des APK : {exc}", file=sys.stderr)
        return
    for pkg in targets:
        try:
            paths = adb.app_apk_paths(pkg)
        except AdbError as exc:
            print(f"APK non sauvegardé ({pkg}) : {exc}", file=sys.stderr)
            continue
        if not paths:
            print(f"APK introuvable sur l'appareil ({pkg}).", file=sys.stderr)
            continue
        dest = os.path.join(root, pkg)
        try:
            os.makedirs(dest, exist_ok=True)
        except OSError as exc:
            print(f"APK non sauvegardé ({pkg}) : {exc}", file=sys.stderr)
            continue
        pulled = 0
        for remote in paths:
            good, _out = adb.pull_apk(remote, dest)
            if good:
                pulled += 1
        if pulled:
            print(f"APK sauvegardé : {pkg} ({pulled} fichier(s) -> {dest})")
        else:
            print(f"Échec de la sauvegarde APK ({pkg}).", file=sys.stderr)


def cmd_restore(args) -> int:
    if args.file:
        path = args.file
    else:
        files = backup.list_backup_files()
        if not files:
            print("Aucun backup dans backups/ — rien à restaurer.", file=sys.stderr)
            return EXIT_ERR
        path = files[0]
        others = ", ".join(os.path.basename(f) for f in files[1:4])
        print(f"(backup le plus récent{'; autres : ' + others if others else ''})")
    data, err = backup.read_backup(path)
    if data is None:
        print(f"Lecture du backup impossible : {err}", file=sys.stderr)
        return EXIT_ERR
    serial = data.get("serial")
    entries = backup.entries(data)
    if not entries:
        print("Backup vide — rien à restaurer.")
        return EXIT_OK

    adb = pick_adb(args)
    if serial and args.serial and serial != args.serial:
        print(f"Le backup provient d'un autre appareil ({serial}), "
              f"cible : {args.serial}.", file=sys.stderr)

    if args.dry_run:
        print(f"Simulation (--dry-run) pour {path} :")
        for entry in entries:
            if entry.get("type") == "user":
                print(f"  (app utilisateur, ignorée) {entry['package']}")
            else:
                print(f"  adb -s {adb.serial} shell cmd package "
                      f"install-existing {entry['package']}")
        return EXIT_OK

    if not _confirm(f"Réinstaller {len(entries)} app(s) depuis {path} ?", args.yes):
        print("Abandon.")
        return EXIT_OK

    failures = 0
    skipped = 0
    for entry in entries:
        pkg = entry.get("package") or ""
        if entry.get("type") == "user":
            print(f"{pkg} : app utilisateur — réinstalle-la à la main.")
            skipped += 1
            continue
        try:
            ok, out = adb.install_existing(pkg)
        except AdbError as exc:
            ok, out = False, str(exc)
        if ok:
            print(f"OK  {pkg} restauré.")
        else:
            failures += 1
            print(f"Échec  {pkg} : {out or 'échec'}")
    done = len(entries) - skipped
    if skipped:
        print(f"({skipped} app(s) utilisateur ignorée(s))")
    if failures:
        print(f"{done - failures} ok, {failures} échec(s).")
        return EXIT_ERR
    print(f"{done} restauration(s) réussie(s) (redémarre le téléphone au besoin).")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debloat_cli.py",
        description="Debloat Android sans root, en ligne de commande.")
    parser.add_argument("--serial", help="serial ADB cible (défaut : appareil unique branché)")
    parser.add_argument("--version", action="version", version="debloat-android 1.1.0")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("devices", help="lister les appareils ADB").set_defaults(func=cmd_devices)

    p_scan = sub.add_parser("scan", help="scanner + classifier les apps")
    p_scan.add_argument("--search", help="chaîne contenue dans le paquet ou le libellé")
    p_scan.add_argument("--risk", help="risques affichés, ex : safe,advanced (défaut : tout)")
    p_scan.add_argument("--json", action="store_true", help="imprimer le scan en JSON")
    p_scan.add_argument("--report", metavar="FILE", help="écrire le scan en JSON dans FILE")
    p_scan.add_argument("--rule", action="store_true",
                        help="imprimer aussi le tableau (avec --json/--report)")
    p_scan.set_defaults(func=cmd_scan)

    p_un = sub.add_parser("uninstall", help="retirer des apps (avec garde-fous)")
    p_un.add_argument("packages", nargs="+", metavar="PACKAGE")
    p_un.add_argument("--allow-unknown", action="store_true",
                      help="autoriser les paquets non répertoriés dans la base")
    p_un.add_argument("--allow-user-apps", action="store_true",
                      help="autoriser la suppression définitive d'apps utilisateur")
    p_un.add_argument("--dry-run", action="store_true", help="afficher sans exécuter")
    p_un.add_argument("--backup-apks", action="store_true",
                      help="sauvegarder les APK de la sélection dans backups/<serial>/apks/ "
                           "avant le retrait (l utilisateur doit le demander explicitement)")
    p_un.add_argument("--yes", "-y", action="store_true", help="ne pas demander confirmation")
    p_un.set_defaults(func=cmd_uninstall)

    p_re = sub.add_parser("restore", help="réinstaller un backup")
    p_re.add_argument("--file", metavar="FILE", help="fichier backup (défaut : le plus récent)")
    p_re.add_argument("--dry-run", action="store_true", help="afficher sans exécuter")
    p_re.add_argument("--yes", "-y", action="store_true", help="ne pas demander confirmation")
    p_re.set_defaults(func=cmd_restore)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except AdbError as exc:
        print(exc, file=sys.stderr)
        return EXIT_ERR
    except KeyboardInterrupt:
        print("\ninterrompu", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
