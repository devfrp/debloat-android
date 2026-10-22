#!/usr/bin/env python3
"""Fabriques partagées par les tests : fake ADB + patchers pour GUI/CLI."""
from __future__ import annotations

import unittest.mock as mock
from types import SimpleNamespace

from adb import AdbError


class FakeAdb:
    """adb simulé : appareil unique, scan, désinstallation, restauration.

    Les méthodes ont la même signature que adb.Adb ; chaque appel est
    consigné dans `self.calls` et `self.uninstalled` / `self.restored`,
    pour que les tests vérifient ce qui a réellement été exécuté.
    """

    def __init__(self,
                 serial: str = "123ABC",
                 state: str = "device",
                 model: str = "Pixel Test",
                 sys_pkgs: list[str] | None = None,
                 user_pkgs: list[str] | None = None,
                 uninstall_results: dict[str, tuple[bool, str]] | None = None,
                 raise_on_uninstall: str | None = None):
        self.serial = serial
        self.latest_serial = serial  # le dernier serial demandé (GUI)
        self.state = state
        self.model = model
        self.calls: list[tuple[str, str | None]] = []
        self.sys_pkgs = sys_pkgs if sys_pkgs is not None else []
        self.user_pkgs = user_pkgs if user_pkgs is not None else []
        self.uninstall_results = uninstall_results or {}
        self.raise_on_uninstall = raise_on_uninstall
        self.uninstalled: list[tuple[str, bool]] = []
        self.restored: list[str] = []
        self.props_out = (
            "[ro.product.brand]: [Google]\n"
            "[ro.product.manufacturer]: [google]\n"
            "[ro.product.model]: [Pixel Test]\n"
            "[ro.build.version.release]: [14]\n"
            "[ro.build.version.security_patch]: [2026-07-05]\n"
        )

    # ---------------------------------------------------------------- helpers
    def _record(self, name: str) -> None:
        self.calls.append((name, self.latest_serial if self.latest_serial else None))

    # ----------------------------------------------------------- API adb.Adb
    def list_devices(self):
        self.calls.append(("devices", None))
        return [SimpleNamespace(serial=self.serial, state=self.state, model=self.model)]

    def get_props(self):
        import re
        out = self.props_out
        pat = re.compile(r"^\[(.+?)\]\s*:\s*\[(.*)\]$", re.MULTILINE)
        return {m.group(1): m.group(2) for m in pat.finditer(out)}

    def system_packages(self):
        return sorted(self.sys_pkgs)

    def user_packages(self):
        return sorted(self.user_pkgs)

    def uninstall_for_user0(self, package: str):
        self.uninstalled.append((package, False))
        if self.raise_on_uninstall and package == self.raise_on_uninstall:
            raise AdbError("appareil débranché")
        return self.uninstall_results.get(package, (True, "Success"))

    def uninstall_user_app(self, package: str):
        self.uninstalled.append((package, True))
        return self.uninstall_results.get(package, (True, "Success"))

    def install_existing(self, package: str):
        self.restored.append(package)
        return (True, "Success")


def patch_adb(module_obj, fake: FakeAdb):
    """Patche **Adb** dans le module donné : toute construction renvoie `fake`."""
    def _factory(serial=None):
        fake.latest_serial = serial
        return fake
    return mock.patch.object(module_obj, "Adb", _factory)


def make_result(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Namespace ressemblant à subprocess.CompletedProcess."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
