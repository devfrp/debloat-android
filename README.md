# debloat-android

Debloat an Android phone **without root**, using ADB: a Tkinter **GUI** (pure Python
standard library — zero dependencies) and a **CLI companion**, with the same guardrails.

- Detects the phone plugged over USB (USB debugging enabled).
- Lists every app and classifies it: safe bloat, advanced, unknown, protected OS components.
- Removes system apps for your user profile (`pm uninstall --user 0`): the APK stays on
  the phone, so it is **reversible**. Every removal is recorded in a JSON backup file and
  can be restored in one click.
- **Nothing is pre-checked** after a scan: the user explicitly checks every app they want
  to remove (click a row, or press Space on the selected row).
- User apps (Play Store) are flagged separately: removing them is **permanent**
  (data loss), with its own confirmation dialog.
- Critical OS components (Play services, WebView, keyboards, launchers...) are
  **deliberately locked**: you cannot check them.
- Before any removal, the tool **offers to save the APKs** of the selection to disk
  (`backups/<serial>/apks/<package>/`), pulled over `adb pull`.

## Quick start

1. Install ADB:

   | OS | Command |
   |---|---|
   | Debian / Ubuntu | `sudo apt install adb` |
   | Fedora | `sudo dnf install android-tools` |
   | Arch | `sudo pacman -S android-tools` |
   | macOS | `brew install --cask android-platform-tools` |
   | Windows | [platform-tools](https://developer.android.com/studio/releases/platform-tools) (add to PATH, or `set ADB_PATH=...`) |

   If `adb` lives elsewhere: `ADB_PATH=/path/to/adb python3 debloat_gui.py`

2. On the phone: *Settings -> About -> tap "Build number" 7 times -> Developer options -> USB debugging*.

3. Run:

   ```bash
   ./run.sh            # GUI: Refresh -> Scan -> check -> Uninstall
   ```

## GUI workflow

**Refresh devices -> Scan apps -> check each app you want to remove -> Uninstall selection.**

| Column value | Meaning | Behavior |
|---|---|---|
| `sans danger` (safe) | classic bloat, removal considered safe | user must check it explicitly |
| `avancé` (advanced) | some functionality may disappear | unchecked, softer confirmation |
| `inconnu` (unknown) | not in the database | unchecked, double confirmation |
| `protégé` (protected) | locked OS component (Play services, WebView, keyboard, launcher...) | cannot be checked |
| user app (Play Store) | permanent removal | dedicated confirmation |

Other functions: "Rapport" (export the scan as JSON), "Gestionnaire de backups" (restore),
filtered views (bloat / protected / system / user / all), search, detailed log, notes on
hover, double-click for details. After each removal a JSON ledger entry is written
automatically, so restoration stays possible.

## CLI companion

Same guardrails, no window:

```bash
python3 debloat_cli.py devices                     # detected devices
python3 debloat_cli.py scan                        # scan + classification
python3 debloat_cli.py scan --risk safe,advanced   # filter by risk
python3 debloat_cli.py scan --json                 # JSON output (stdout)
python3 debloat_cli.py uninstall com.miui.msa.global --yes
python3 debloat_cli.py uninstall com.miui.msa.global --backup-apks --yes   # also pull APKs
python3 debloat_cli.py uninstall com.unknown.pkg   # refused: needs --allow-unknown
python3 debloat_cli.py restore --file backups/X.json --dry-run
```

Exit codes: `0` ok, `1` adb error / failure, `2` guardrail refusal (protected package,
unknown package or user app without explicit opt-in). Global option `--serial S` when
several devices are connected.

## Restoring

- GUI: **Gestionnaire de backups** -> pick the file -> restore (an automatic re-scan follows).
- CLI: `python3 debloat_cli.py restore [--file backups/X.json] [--yes] [--dry-run]`.

Restoration uses `adb shell cmd package install-existing <pkg>` (system apps only — reinstall
user apps from a store). APKs saved before removal can also be sideloaded manually if needed.

> Robustness: atomic writes (`tmp` + `os.replace`); an unreadable backup is
> **quarantined** (`*.corrupt-<date>`) instead of overwritten — history is never silently
> lost. A phone reboot can help after restoring OS services.

## Bloat database

`bloat_db.py` holds ~115 known packages (Samsung, Xiaomi/MIUI, Oppo/Realme/OnePlus,
Huawei/Honor, Google, Sony, LG, Tecno/Infinix...) plus a black list of protected
components matched by prefix (`com.android.*`, `android.*`, `com.google.android.trichromelibrary*`).

To extend the database, add one line to `BLOAT_DB`:

```python
"some.vendor.pkg": (bloat_db.A, "Readable name", "What it does / why it is removable."),
```

A package missing from the database shows up as *unknown* — nothing breaks, the user decides.

## In-depth verification

```bash
./verify.sh
```

- `adb.py`: `devices -l` parsing (multi-device, states, daemon noise), getprop, package
  lists, exact command shapes, timeouts, missing binary.
- `backup.py`: atomicity, dedup, portable Wi-Fi serials (`127.0.0.1:5555`),
  **quarantine of corrupted files** (never overwritten), APK folder layout.
- `bloat_db.py`: integrity (names/risks), no overlap between database and forbidden list, prefixes.
- `debloat_cli.py`: guardrails (protected refused, unknown opt-in, user opt-in), dry-run,
  exit codes, backup ledger, `--backup-apks`.
- **Full GUI tests under Xvfb** (auto-adoption, views, checking, uninstall, corrupted
  backup, restore, export, APK-backup proposal, adb error handling) against a fake ADB.
- **Subprocess integration**: the real CLI is executed against a fake `adb` binary —
  exercising the genuine `shutil.which -> subprocess -> parsing` chain, including
  `-s <serial>` being consumed by adb itself.
- **Stress**: 1500 apps -> scan about one second, list refresh about 0.02 s.

## Layout

```
debloat_gui.py   # Tkinter GUI (views, confirmations, APK backup, export, log)
debloat_cli.py   # CLI companion (devices / scan / uninstall / restore)
adb.py           # ADB wrapper (devices, getprop, pm list/uninstall, install-existing, pull)
bloat_db.py      # known-bloat database + protected components
backup.py        # backups/<serial>.json persistence (atomicity, quarantine, APK folder)
tests/           # unit + GUI (Xvfb) + subprocess integration tests
verify.sh        # runs the whole verification
run.sh           # launches the GUI (checks adb presence)
backups/         # created automatically: <serial>.json and <serial>/apks/
```

## Disclaimer

Use at your own risk: `--user 0` removal is reversible, but removing an app that another
one depends on (e.g. a camera service, a keyboard) can break that feature until restored.
Test small, one category at a time. This software sends nothing over the internet;
everything goes through your USB cable. License: MIT.
