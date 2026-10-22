#!/usr/bin/env python3
"""Wrapper ADB léger utilisé par Debloat Android.

Sans root : tout passe par
  - `pm uninstall --user 0 <pkg>`          (app système, réversible)
  - `pm uninstall <pkg>`                   (app utilisateur, définitif)
  - `cmd package install-existing <pkg>`   (restauration d'une app système)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass


class AdbError(Exception):
    """Binaire adb manquant, appareil absent, timeout ou réponse inattendue."""


@dataclass
class DeviceInfo:
    serial: str
    state: str          # device | unauthorized | offline | …
    model: str = ""

    def describe(self) -> str:
        return f"{self.model or 'appareil inconnu'} ({self.serial})"


_PROP_RE = re.compile(r"^\[(.+?)\]\s*:\s*\[(.*)\]$", re.MULTILINE)
_STATES = {
    "device", "offline", "unauthorized", "recovery",
    "bootloader", "sideload", "disconnecting",
}


def _adb_binary() -> str:
    return os.environ.get("ADB_PATH") or shutil.which("adb") or "adb"


def _parse_packages(out: str) -> list[str]:
    pks = {
        line[len("package:"):].strip()
        for line in out.splitlines()
        if line.startswith("package:")
    }
    return sorted(pk for pk in pks if pk)


class Adb:
    """Un appel = un sous-processus adb. Aucun état global."""

    def __init__(self, serial: str | None = None):
        self.serial = serial
        self.bin = _adb_binary()

    # ------------------------------------------------------------------ base

    def _cmd(self, *args: str) -> list[str]:
        cmd = [self.bin]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd + list(args)

    def run(self, *args: str, timeout: float = 30, check: bool = False) -> str:
        rc, out, err = self._run_full(*args, timeout=timeout)
        text = out if out else err
        if check and rc != 0:
            raise AdbError(text or f"code de sortie {rc}")
        return text

    def _run_full(self, *args: str, timeout: float = 30) -> tuple[int, str, str]:
        """stdout, stderr et code de sortie d'un appel adb."""
        extra: dict = {}
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            extra["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.run(
                self._cmd(*args),
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout, **extra,
            )
        except FileNotFoundError as exc:
            raise AdbError(
                "adb introuvable. Installe-le (ex : sudo apt install adb) "
                "ou définis la variable ADB_PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb {' '.join(args[:3])} … : délai dépassé ({timeout} s).") from exc
        return proc.returncode, (proc.stdout or ""), (proc.stderr or "")

    # --------------------------------------------------------------- lecture

    def list_devices(self) -> list[DeviceInfo]:
        out = self.run("devices", "-l", check=True)
        devices: list[DeviceInfo] = []
        for line in out.splitlines():
            line = line.strip()
            if (not line or line.startswith("*")
                    or line.lower().startswith("list of devices")):
                continue
            parts = line.split()
            if len(parts) < 2 or parts[1] not in _STATES:
                continue
            model = ""
            for tok in parts:
                if tok.startswith("model:"):
                    model = tok.split(":", 1)[1].replace("_", " ")
                    break
            devices.append(DeviceInfo(serial=parts[0], state=parts[1], model=model))
        return devices

    def get_props(self) -> dict[str, str]:
        out = self.run("shell", "getprop")
        return {m.group(1): m.group(2) for m in _PROP_RE.finditer(out)}

    def system_packages(self) -> list[str]:
        out = self.run("shell", "pm", "list", "packages", "-s", check=True)
        return _parse_packages(out)

    def user_packages(self) -> list[str]:
        out = self.run("shell", "pm", "list", "packages", "-3", check=True)
        return _parse_packages(out)

    # ------------------------------------------------------------ operations

    def uninstall_for_user0(self, package: str) -> tuple[bool, str]:
        """Désinstalle une app système pour le profil courant (réversible)."""
        out = self.run("shell", "pm", "uninstall", "--user", "0", package, timeout=60)
        return self._ok(out), out

    def uninstall_user_app(self, package: str) -> tuple[bool, str]:
        """Désinstalle définitivement une app utilisateur (données perdues)."""
        out = self.run("shell", "pm", "uninstall", package, timeout=60)
        return self._ok(out), out

    def install_existing(self, package: str) -> tuple[bool, str]:
        """Réinstalle une app système précédemment retirée par --user 0."""
        out = self.run("shell", "cmd", "package", "install-existing", package, timeout=60)
        return self._ok(out), out

    def app_apk_paths(self, package: str) -> list[str]:
        """Chemins des APK de l'app (plusieurs pour une app « split »)."""
        out = self.run("shell", "pm", "path", package)
        return [line[len("package:"):].strip()
                for line in out.splitlines()
                if line.startswith("package:")
                and len(line) > len("package:")]

    def pull_apk(self, remote: str, dest_dir: str) -> tuple[bool, str]:
        """Copie un APK du téléphone vers dest_dir (sans root, fichiers lisibles)."""
        try:
            rc, out, err = self._run_full("pull", remote, dest_dir, timeout=180)
        except AdbError as exc:
            return False, str(exc)
        return rc == 0, ((out or err) or "").strip()

    @staticmethod
    def _ok(out: str) -> bool:
        low = out.lower()
        return "success" in low or "installed for user" in low
