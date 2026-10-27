#!/usr/bin/env python3
"""Table de chaînes bilingue (FR/EN) pour l'interface de Debloat Android.

Principe : le choix est fait une fois, au démarrage (boîte « Langue / Language »).
Ensuite `t(cle, **args)` renvoie la chaîne de la langue courante, mise en forme
via str.format pour les placeholders {xxx}.

La langue par défaut est le français (cas du CLI et des tests)."""
from __future__ import annotations

_RISK = {
    "safe": {
        "fr": "sûre",
        "en": "safe",
    },
    "advanced": {
        "fr": "avancée",
        "en": "advanced",
    },
    "unknown": {
        "fr": "avancée (non listée)",
        "en": "advanced (unlisted)",
    },
    "forbidden": {
        "fr": "protégée (verrouillée)",
        "en": "protected (locked)",
    },
}

LANGUAGES = ("fr", "en")
_current = "fr"

STRINGS = {
    # ------------------------------------------------------------ appareils
    "device.none": {
        "fr": "Aucun appareil",
        "en": "No device",
    },
    "device.searching": {
        "fr": "Recherche des appareils…",
        "en": "Searching for devices…",
    },
    "device.none.detected": {
        "fr": "Aucun appareil détecté",
        "en": "No device detected",
    },
    "device.none.log": {
        "fr": "Aucun appareil ADB. Vérifie : câble, « Débogage USB » dans les options pour développeurs, "
              "autorisation sur le téléphone (bouton Aide).",
        "en": "No ADB device. Check: cable, \"USB debugging\" in developer options, "
              "authorization on the phone (Help button).",
    },
    "device.state.warn": {
        "fr": "{serial} : état « {state} » — autorise le débogage USB sur le téléphone.",
        "en": "{serial}: state \"{state}\" — allow USB debugging on the phone.",
    },
    "device.unauthorized": {
        "fr": "Appareil détecté mais non autorisé",
        "en": "Device detected but not authorized",
    },
    "device.choose.title": {
        "fr": "Choisir un appareil",
        "en": "Choose a device",
    },
    "device.choose.lead": {
        "fr": "Plusieurs appareils sont détectés :",
        "en": "Several devices are detected:",
    },
    "device.selected.log": {
        "fr": "Appareil sélectionné : {dev} — scan des applications…",
        "en": "Selected device: {dev} — scanning apps…",
    },
    "common.continue_btn": {
        "fr": "Continuer",
        "en": "Continue",
    },
    # ------------------------------------------------------------ boutons
    "btn.help": {"fr": "Aide", "en": "Help"},
    "btn.theme": {"fr": "Apparence", "en": "Appearance"},
    "theme.auto": {"fr": "Comme le système", "en": "Like the system"},
    "theme.light": {"fr": "Claire", "en": "Light"},
    "theme.dark": {"fr": "Sombre", "en": "Dark"},
    "btn.scan": {"fr": "Scanner les applications", "en": "Scan apps"},
    "btn.refresh": {"fr": "Rafraîchir les appareils", "en": "Refresh devices"},
    "btn.uninstall": {
        "fr": "Désinstaller la sélection ({n})",
        "en": "Uninstall selection ({n})",
    },
    "btn.backups": {"fr": "Gestionnaire de backups", "en": "Backup manager"},
    "btn.report": {"fr": "Rapport", "en": "Report"},
    "btn.check_safe": {
        "fr": "Cocher les sûres (mode)",
        "en": "Check safe ones (mode)",
    },
    "btn.check_all": {
        "fr": "Tout cocher (mode)",
        "en": "Check all (mode)",
    },
    "btn.uncheck": {"fr": "Décocher tout", "en": "Clear checks"},
    "btn.restore_this": {
        "fr": "Restaurer ce backup",
        "en": "Restore this backup",
    },
    # ------------------------------------------------------------ panneau gauche
    "mode.header": {"fr": "Mode", "en": "Mode"},
    "mode.safe": {"fr": "Sûr — recommandées", "en": "Safe — recommended"},
    "mode.adv": {"fr": "Avancé — prudence", "en": "Advanced — extra care"},
    "lbl.counts": {
        "fr": "Sûres : {safe}\n"
              "Avancées : {adv} (dont {unlisted} non listées)\n"
              "Utilisateur : {user}\n"
              "Protégées (verrouillées) : {prot}",
        "en": "Safes: {safe}\n"
              "Advanced: {adv} (incl. {unlisted} unlisted)\n"
              "User: {user}\n"
              "Protected (locked): {prot}",
    },
    "hint.adv": {
        "fr": "Le mode « Avancé » demande\ndes confirmations supplémentaires.",
        "en": "The \"Advanced\" mode asks\nfor extra confirmations.",
    },
    "search.hint": {"fr": "Recherche :", "en": "Search:"},
    # ------------------------------------------------------------ tableau
    "col.check": {"fr": "Cocher", "en": "Check"},
    "col.package": {"fr": "Paquet", "en": "Package"},
    "col.app": {"fr": "Application", "en": "App"},
    "col.risk": {"fr": "Risque", "en": "Risk"},
    "col.type": {"fr": "Type", "en": "Type"},
    "type.system": {"fr": "système", "en": "system"},
    "type.user": {"fr": "utilisateur", "en": "user"},
    "risk.user": {"fr": "app utilisateur", "en": "user app"},
    "log.cluster": {"fr": "Journal", "en": "Log"},
    # ------------------------------------------------------------ tout-venant
    "welcome": {
        "fr": "Bienvenue ! Branche ton téléphone (débogage USB activé), puis clique "
              "« Rafraîchir les appareils ».\n"
              "Rien n'est coché d'office : coche chaque app que tu veux retirer, "
              "puis « Désinstaller la sélection ».",
        "en": "Welcome! Plug your phone (USB debugging on), then click "
              "\"Refresh devices\".\n"
              "Nothing is pre-checked: check every app you want to remove, "
              "then \"Uninstall selection\".",
    },
    "status.no_device": {
        "fr": "Connecte un téléphone (débogage USB activé), puis « Rafraîchir les appareils ».",
        "en": "Connect a phone (USB debugging on), then \"Refresh devices\".",
    },
    "status.loaded": {
        "fr": "{n} apps chargées — sélection : {sel} — "
              "un clic sur une ligne coche/décoche, survol = note, double-clic = détails.",
        "en": "{n} apps loaded — selection: {sel} — "
              "click a row to check/uncheck, hover = note, double-click = details.",
    },
    "status.scan_done": {
        "fr": "Scan fini — {total} apps. "
              "Coche chaque app à retirer (clic sur la ligne), puis « Désinstaller ».",
        "en": "Scan done — {total} apps. "
              "Check every app to remove (click its row), then \"Uninstall\".",
    },
    "status.saving_apks": {
        "fr": "Sauvegarde des APK de la sélection…",
        "en": "Saving the selection's APKs…",
    },
    "status.uninstalling": {
        "fr": "Désinstallation de {n} app(s)…",
        "en": "Uninstalling {n} app(s)…",
    },
    "close.busy": {
        "fr": "Une opération est en cours — quitter quand même ?",
        "en": "An operation is running — quit anyway?",
    },
    # ------------------------------------------------------------ scan
    "status.scanning": {
        "fr": "Scan des applications en cours…",
        "en": "Scanning apps…",
    },
    "scan.err": {
        "fr": "Scan échoué : {err}",
        "en": "Scan failed: {err}",
    },
    "scan.empty": {
        "fr": "Réponse vide — l'appareil a peut-être été débranché.",
        "en": "Empty response — the device may have been unplugged.",
    },
    "note.user_app": {
        "fr": "App installée après l'achat (Play Store…). Sa désinstallation est définitive.",
        "en": "App installed after purchase (Play Store…). Its removal is permanent.",
    },
    "scan.log.total": {
        "fr": "Scan : {total} apps au total — {nsys} système, {nuser} utilisateur",
        "en": "Scan: {total} apps in total — {nsys} system, {nuser} user",
    },
    "scan.log.modes": {
        "fr": "   mode Sûr : {safe} • mode Avancé : {adv} "
              "(dont {unlisted} non listée(s)) — protégées masquées : {prot}",
        "en": "   Safe mode: {safe} • Advanced mode: {adv} "
              "(incl. {unlisted} unlisted) — protected hidden: {prot}",
    },
    "toggle.refused": {
        "fr": "Refusé : {pkg} est un composant protégé ({label}) — "
              "l'app bloque volontairement sa désinstallation.",
        "en": "Refused: {pkg} is a protected component ({label}) — "
              "this app deliberately blocks its removal.",
    },
    "select.log.done": {
        "fr": "{n} app(s) cochée(s) (mode « {mode} »).",
        "en": "{n} app(s) checked (mode \"{mode}\").",
    },
    "select.log.unlisted": {
        "fr": "La sélection contient des paquets non répertoriés — vérifie un par un.",
        "en": "The selection contains unlisted packages — check them one by one.",
    },
    "select.log.nothing": {
        "fr": "Rien de nouveau à cocher dans le mode courant.",
        "en": "Nothing new to check in the current mode.",
    },
    # ------------------------------------------------------------ détails
    "details.risk_header": {
        "fr": "Risque : {risk}",
        "en": "Risk: {risk}",
    },
    "details.package": {"fr": "Paquet : {pkg}", "en": "Package: {pkg}"},
    "details.type": {
        "fr": "Type : {type}",
        "en": "Type: {type}",
    },
    "details.type.system": {"fr": "app système", "en": "system app"},
    "details.type.user": {
        "fr": "app utilisateur (Play Store…)",
        "en": "user app (Play Store…)",
    },
    "details.protected_extra": {
        "fr": "Composant protégé — l'app bloque volontairement sa désinstallation.\n\n",
        "en": "Protected component — this app deliberately blocks its removal.\n\n",
    },
    "details.no_note": {
        "fr": "Pas de note particulière. En cas de doute, cherche « debloat {pkg} » sur le web.",
        "en": "No specific note. If in doubt, search \"debloat {pkg}\" online.",
    },
    "details.app_head": {"fr": "Application", "en": "Application"},
    "hover.risk_user": {"fr": "app utilisateur", "en": "user app"},
    # ------------------------------------------------------------ confirmations
    "confirm.none_checked": {
        "fr": "Aucune app cochée.",
        "en": "No app checked.",
    },
    "confirm.safe.title": {
        "fr": "Mode Sûr — confirmation",
        "en": "Safe mode — confirmation",
    },
    "confirm.safe.body": {
        "fr": "Retirer {n} app(s) « sûres » ?\n\n{preview}\n\n"
              "Les apps système restent restaurables (gestionnaire de backups).\n"
              "Continuer ?",
        "en": "Remove {n} \"safe\" app(s)?\n\n{preview}\n\n"
              "System apps stay restorable (backup manager).\nContinue?",
    },
    "confirm.adv.title1": {
        "fr": "Mode Avancé — confirmation 1/2",
        "en": "Advanced mode — confirmation 1/2",
    },
    "confirm.adv.body1": {
        "fr": "MODE AVANCÉ — tu vas retirer {n} app(s) :\n\n"
              " • {safe} sûre(s)\n"
              " • {adv} avancée(s) (dont {unlisted} non listée(s))\n"
              " • {user} utilisateur(s) — SUPPRESSION DÉFINITIVE\n\n"
              "{preview}\n\n"
              "Une fonctionnalité peut manquer après le retrait (cloud, notes,\n"
              "caméra, réseau…). Les apps système restent restaurables ;\n"
              "les apps utilisateur, non.\n\n"
              "Continuer ?",
        "en": "ADVANCED MODE — you are about to remove {n} app(s):\n\n"
              " • {safe} safe\n"
              " • {adv} advanced (incl. {unlisted} unlisted)\n"
              " • {user} user — PERMANENT DELETION\n\n"
              "{preview}\n\n"
              "A feature may be missing after removal (cloud, notes, camera,\n"
              "network…). System apps stay restorable; user apps do not.\n\n"
              "Continue?",
    },
    "confirm.adv.title2": {
        "fr": "Mode Avancé — confirmation 2/2",
        "en": "Advanced mode — confirmation 2/2",
    },
    "confirm.adv.body2": {
        "fr": "Dernière vérification avant de retirer.\n\n"
              "Relis les lignes au-dessus : ce retrait est-il vraiment voulu ?\n\n"
              "Confirmer définitivement ?",
        "en": "Last check before removing.\n\n"
              "Re-read the lines above: is this removal truly wanted?\n\n"
              "Confirm for good?",
    },
    "confirm.user.title": {
        "fr": "Apps utilisateur — SUPPRESSION DÉFINITIVE",
        "en": "User apps — PERMANENT DELETION",
    },
    "confirm.user.body": {
        "fr": "{n} app(s) utilisateur seront définitivement supprimées\n"
              "(données perdues — réinstallables seulement via une boutique).\n\n"
              "Confirmer ?",
        "en": "{n} user app(s) will be permanently deleted\n"
              "(data lost — reinstallable only from a store).\n\nConfirm?",
    },
    "confirm.backup.title": {
        "fr": "Sauvegarde avant retrait",
        "en": "Backup before removal",
    },
    "confirm.backup.body": {
        "fr": "Sauvegarder les APK de la sélection sur le PC avant de les retirer ?\n\n"
              "Destination : backups/<serial>/apks/<paquet>/\n\n"
              "Le journal de restauration (backups/<serial>.json) est, lui,\n"
              "créé automatiquement de toute façon.",
        "en": "Save the selection's APKs to the PC before removing them?\n\n"
              "Destination: backups/<serial>/apks/<package>/\n\n"
              "The restore ledger (backups/<serial>.json) is, itself,\n"
              "created automatically anyway.",
    },
    # ------------------------------------------------------------ déroulé retrait
    "uninstall.flavor.user": {"fr": "app utilisateur", "en": "user app"},
    "uninstall.flavor.system": {"fr": "profil 0", "en": "user profile 0"},
    "uninstall.ok_log": {
        "fr": "OK  {pkg} retiré ({flavor}).",
        "en": "OK  {pkg} removed ({flavor}).",
    },
    "uninstall.fail_log": {
        "fr": "ÉCHEC  {pkg} : {out}",
        "en": "FAILED  {pkg}: {out}",
    },
    "fallback.failure": {"fr": "échec", "en": "failure"},
    "more.items": {
        "fr": "… et {n} autre(s)",
        "en": "… and {n} more",
    },
    "protected.fallback": {
        "fr": "vital pour le système",
        "en": "vital to the system",
    },
    "uninstall.done.ok": {
        "fr": "Terminé : {n} désinstallation(s) réussie(s). "
              "Les apps système restent restaurables via le gestionnaire de backups.",
        "en": "Done: {n} removal(s) succeeded. "
              "System apps stay restorable via the backup manager.",
    },
    "uninstall.done.zero": {
        "fr": "Terminé : aucune désinstallation réussie — détail dans le journal.",
        "en": "Done: no removal succeeded — see the log for details.",
    },
    "save_apks.mkdir_fail": {
        "fr": "Impossible de créer le dossier des APK : {err}",
        "en": "Cannot create the APK folder: {err}",
    },
    "save_apks.not_pulled": {
        "fr": "APK non sauvegardé ({pkg}) : {err}",
        "en": "APK not saved ({pkg}): {err}",
    },
    "save_apks.missing": {
        "fr": "APK introuvable sur l'appareil ({pkg}).",
        "en": "APK not found on the device ({pkg}).",
    },
    "save_apks.saved": {
        "fr": "APK sauvegardé : {pkg} ({n} fichier(s) -> {dest})",
        "en": "APK saved: {pkg} ({n} file(s) -> {dest})",
    },
    "save_apks.all_failed": {
        "fr": "Échec de la sauvegarde APK ({pkg}).",
        "en": "APK saving failed ({pkg}).",
    },
    "backup.updated_log": {
        "fr": "Backup mis à jour : {path}",
        "en": "Ledger updated: {path}",
    },
    # ------------------------------------------------------------ restauration
    "backups.none.title": {
        "fr": "Gestionnaire de backups",
        "en": "Backup manager",
    },
    "backups.none.body": {
        "fr": "Aucun backup pour le moment.\nUn fichier backups/<serial>.json est créé\n"
              "automatiquement à la première désinstallation.",
        "en": "No backup yet.\nA backups/<serial>.json file is created\n"
              "automatically at the first removal.",
    },
    "backups.win.title": {
        "fr": "Gestionnaire de backups — restauration",
        "en": "Backup manager — restore",
    },
    "backups.files_label": {
        "fr": "Fichiers de backup :",
        "en": "Backup files:",
    },
    "backups.read_fail": {
        "fr": "Impossible de lire ce backup : {err}",
        "en": "Cannot read this backup: {err}",
    },
    "backups.detail.device": {"fr": "Appareil : {dev}", "en": "Device: {dev}"},
    "backups.detail.serial": {"fr": "Serial  : {srl}", "en": "Serial  : {srl}"},
    "backups.detail.type_sys": {"fr": "sys", "en": "sys"},
    "backups.detail.type_user": {"fr": "user", "en": "user"},
    "restore.confirm.title": {"fr": "Restaurer", "en": "Restore"},
    "restore.confirm.body": {
        "fr": "Réinstaller TOUTES les apps système de ce backup sur le téléphone\n"
              "(les apps utilisateur doivent être réinstallées à la main) ?",
        "en": "Reinstall ALL system apps from this backup on the phone\n"
              "(user apps must be reinstalled manually)?",
    },
    "restore.read_fail": {
        "fr": "Lecture du backup impossible : {err}",
        "en": "Cannot read the backup: {err}",
    },
    "restore.start_log": {
        "fr": "Restauration de {name} sur {serial}…",
        "en": "Restoring {name} on {serial}…",
    },
    "restore.skip_user": {
        "fr": "{pkg} : app utilisateur — réinstalle-la à la main (Play Store ou APK).",
        "en": "{pkg}: user app — reinstall it manually (Play Store or APK).",
    },
    "restore.ok_log": {
        "fr": "OK  {pkg} restauré.",
        "en": "OK  {pkg} restored.",
    },
    "restore.fail_log": {
        "fr": "ÉCHEC  {pkg} : {out}",
        "en": "FAILED  {pkg}: {out}",
    },
    "restore.done_log": {
        "fr": "Restauration terminée.",
        "en": "Restore finished.",
    },
    "restore.rescan_log": {
        "fr": "Nouveau scan pour mettre la liste à jour…",
        "en": "New scan to refresh the list…",
    },
    # ------------------------------------------------------------ export
    "export.none.title": {
        "fr": "Exporter le rapport",
        "en": "Export the report",
    },
    "export.none.body": {
        "fr": "Aucun scan à exporter.\nConnecte un appareil et fais « Scanner les applications ».",
        "en": "No scan to export.\nConnect a device and run \"Scan apps\".",
    },
    "export.dialog.title": {
        "fr": "Exporter le rapport de scan",
        "en": "Export the scan report",
    },
    "export.filetypes.json": {"fr": "JSON", "en": "JSON"},
    "export.filetypes.all": {"fr": "Tous les fichiers", "en": "All files"},
    "export.write_fail": {
        "fr": "Écriture du rapport impossible : {err}",
        "en": "Cannot write the report: {err}",
    },
    "export.ok_log": {
        "fr": "Rapport exporté : {path}",
        "en": "Report exported: {path}",
    },
    "help.title": {
        "fr": "Aide — Debloat Android",
        "en": "Help — Debloat Android",
    },
}


def set_lang(code: str) -> None:
    """Fixe la langue courante (« fr » décrochée par défaut ; « en » disponible)."""
    global _current
    _current = code if code in LANGUAGES else "fr"


def get_lang() -> str:
    return _current


def t(key: str, **fmt) -> str:
    """Chaîne traduite de la clé, mise en forme avec str.format si des args sont passés."""
    entry = STRINGS.get(key)
    text = entry[_current] if entry else key
    if fmt:
        try:
            return text.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def risk_text(risk: str) -> str:
    return _RISK.get(risk, {}).get(_current, risk)
