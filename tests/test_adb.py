#!/usr/bin/env python3
"""Tests du wrapper ADB via mock de subprocess.run."""
import os
import subprocess
import unittest
import unittest.mock as mock

from adb import Adb, AdbError


class SimpleResult:
    def __init__(self, returncode: int, stdout: str, stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_with(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Patch subprocess.run pour renvoyer un résultat factice."""
    return mock.patch.object(subprocess, "run",
                             return_value=SimpleResult(returncode, stdout, stderr))


class Devices(unittest.TestCase):
    DEVICES_OUT = (
        "* daemon not running; starting now at tcp:5037\n"
        "* daemon started successfully\n"
        "List of devices attached\n"
        "123ABC                device usb:1-1 product:raven model:Pixel_6_Pro device:raven\n"
        "emulator-5554         offline\n"
        "127.0.0.1:5555        unauthorized\n"
    )

    def test_parse_devices(self):
        with run_with(self.DEVICES_OUT):
            devices = Adb().list_devices()
        by_serial = {d.serial: d for d in devices}
        self.assertEqual(set(by_serial), {"123ABC", "emulator-5554", "127.0.0.1:5555"})
        self.assertEqual(by_serial["123ABC"].state, "device")
        self.assertEqual(by_serial["emulator-5554"].state, "offline")
        self.assertEqual(by_serial["127.0.0.1:5555"].state, "unauthorized")
        self.assertEqual(by_serial["123ABC"].model, "Pixel 6 Pro")

    def test_parse_devices_dash_rows_skipped(self):
        out = "\n".join([self.DEVICES_OUT, "-" * 30, "weirdlinegarbage"])
        with run_with(out):
            devices = Adb().list_devices()
        self.assertEqual({d.serial for d in devices},
                         {"123ABC", "emulator-5554", "127.0.0.1:5555"})

    def test_devices_check_failure_raises(self):
        with run_with("error: no devices found", returncode=1):
            with self.assertRaises(AdbError):
                Adb().list_devices()


class Props(unittest.TestCase):
    def test_get_props(self):
        out = ("[ro.product.brand]: [Google]\n"
               "[ro.build.version.release]: [14]\n"
               "[ro.build.version.security_patch]: [2026-07-05]\n")
        with run_with(out):
            props = Adb().get_props()
        self.assertEqual(props["ro.product.brand"], "Google")
        self.assertEqual(props["ro.build.version.release"], "14")

    def test_get_props_value_with_brackets(self):
        out = "[ro.foo]: [a]b]\n[ro.bar]: [x]\n"
        with run_with(out):
            props = Adb().get_props()
        self.assertEqual(props["ro.foo"], "a]b")
        self.assertEqual(props["ro.bar"], "x")


class Packages(unittest.TestCase):
    def test_system_packages(self):
        with run_with("package:com.a.b\npackage:com.c.d\npackage:com.a.b\n"):
            pkgs = Adb().system_packages()
        self.assertEqual(pkgs, ["com.a.b", "com.c.d"])

    def test_user_packages(self):
        with run_with("package:org.user.app\n"):
            self.assertEqual(Adb().user_packages(), ["org.user.app"])

    def test_empty(self):
        with run_with(""):
            self.assertEqual(Adb().system_packages(), [])


class Operations(unittest.TestCase):
    def test_uninstall_for_user0_command_shape(self):
        with run_with("Success") as m_run:
            ok, _ = Adb("SER").uninstall_for_user0("com.x.y")
        self.assertTrue(ok)
        cmd = m_run.call_args.args[0]
        self.assertEqual(cmd[:5], ["adb", "-s", "SER", "shell", "pm"])
        self.assertIn("--user", cmd)
        self.assertEqual(cmd[-1], "com.x.y")

    def test_uninstall_user_app_command_shape(self):
        with run_with("Success") as m_run:
            ok, _ = Adb("SER").uninstall_user_app("org.user.app")
        self.assertTrue(ok)
        cmd = m_run.call_args.args[0]
        self.assertNotIn("--user", cmd)
        self.assertEqual(cmd[-1], "org.user.app")

    def test_install_existing_command(self):
        with run_with("Success") as m_run:
            ok, _ = Adb("SER").install_existing("com.z")
        self.assertTrue(ok)
        cmd = m_run.call_args.args[0]
        self.assertEqual(cmd[-2:], ["install-existing", "com.z"])
        self.assertIn("cmd", cmd)
        self.assertIn("package", cmd)

    def test_ok_variants(self):
        self.assertTrue(Adb._ok("Success"))
        self.assertTrue(Adb._ok("success"))
        self.assertTrue(Adb._ok("com.x installed for user 0"))
        self.assertFalse(Adb._ok("Failure [DELETE_FAILED_INTERNAL_ERROR]"))
        self.assertFalse(Adb._ok(""))

    def test_check_rc_mismatch(self):
        with run_with(stderr="error: device offline", returncode=1):
            with self.assertRaises(AdbError):
                Adb().run("shell", "getprop", check=True)


class AdbFailures(unittest.TestCase):
    def test_missing_binary(self):
        fake_env = dict(os.environ, ADB_PATH="/no/such/path/adb")
        with mock.patch.dict(os.environ, fake_env, clear=False):
            with self.assertRaises(AdbError):
                Adb().list_devices()

    def test_timeout(self):
        with mock.patch.object(subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("adb", 5)):
            with self.assertRaises(AdbError):
                Adb().get_props()


if __name__ == "__main__":
    unittest.main()
