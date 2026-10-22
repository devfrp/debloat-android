#!/usr/bin/env python3
"""Persistance des désinstallations : backups/<serial>.json — partagé GUI/CLI.

Format :
{
  "serial":  "…",
  "device":  "Pixel 6a (8021F4JD)",
  "created": "2026-10-22 14:33:21",
  "history": [{"package": "com.x.y", "type": "system|user", "date": "…"}, …]
}

Robustesse :
  - ecriture atomique (tmp + os.replace) : jamais de JSON à moitié écrit ;
  - un backup illisible est mis en quarantaine (renommé *.corrupt-<date>)
    au lieu d'être écrasé : l'historique reste récupérable à la main.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import re

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_filename(name: str) -> str:
    """Nom de fichier portable : neutralise : / \\ espaces… (serial Wi-Fi 127.0.0.1:5555)."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("._-")
    return cleaned or "inconnu"


def backup_path(serial: str, directory: str | None = None) -> str:
    directory = directory if directory is not None else BACKUP_DIR
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{safe_filename(serial)}.json")


def list_backup_files(directory: str | None = None) -> list[str]:
    directory = directory if directory is not None else BACKUP_DIR
    files = sorted(glob.glob(os.path.join(directory, "*.json")),
                   key=os.path.getmtime, reverse=True)
    return files


def read_backup(path: str) -> tuple[dict | None, str | None]:
    """Lit un backup. Renvoie (données, None) ou (None, message d'erreur)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(data, dict) or not isinstance(data.get("history", []), list):
        return None, "structure de fichier inattendue"
    return data, None


def entries(data: dict) -> list[dict]:
    hist = data.get("history", [])
    return [h for h in hist if isinstance(h, dict) and h.get("package")]


def _quarantine(path: str) -> str:
    dest = f"{path}.corrupt-{datetime.datetime.now():%Y%m%d-%H%M%S}"
    os.replace(path, dest)
    return dest


def append_backup(path: str, serial: str, device: str,
                  package: str, ptype: str) -> tuple[bool, str]:
    """Ajoute un retrait (sans doublon) et écrit le fichier en atomique.

    Renvoie (ok, message) : message vide si ok, warning sinon.
    """
    warnings: list[str] = []
    data: dict = {"serial": serial, "device": device,
                  "created": _now(), "history": []}
    if os.path.exists(path):
        loaded, err = read_backup(path)
        if loaded is None:
            try:
                quarantined = _quarantine(path)
            except OSError as exc:
                return False, f"backup illisible et quarantaine impossible : {exc}"
            warnings.append(f"⚠️ backup précédent illisible → quarantaine : "
                            f"{os.path.basename(quarantined)}. Historique démarré à zéro.")
        else:
            data = loaded
            data.setdefault("serial", serial)
            data.setdefault("device", device)
            data.setdefault("created", _now())
            if not isinstance(data.get("history"), list):
                data["history"] = []

    history = data.setdefault("history", [])
    if not any(h.get("package") == package for h in history):
        history.append({"package": package, "type": ptype, "date": _now()})

    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as exc:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return False, f"écriture du backup impossible : {exc}"
    return True, " ".join(warnings)
