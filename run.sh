#!/usr/bin/env bash
# Lanceur — vérifie adb puis ouvre l'interface graphique.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v adb >/dev/null 2>&1; then
  echo "❌ adb n'est pas installé."
  echo
  echo "Installe-le avec :"
  echo "  Debian/Ubuntu : sudo apt install adb"
  echo "  Fedora        : sudo dnf install android-tools"
  echo "  Arch          : sudo pacman -S android-tools"
  echo "  macOS         : brew install --cask android-platform-tools"
  echo
  echo "Ou bien tape-le quelque part et exporte :"
  echo "  export ADB_PATH=/chemin/vers/adb"
  exit 1
fi

exec python3 debloat_gui.py
