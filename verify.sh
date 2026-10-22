#!/usr/bin/env bash
# Vérification approfondie : compilation + suite de tests (GUI sous Xvfb quand dispo).
set -uo pipefail
cd "$(dirname "$0")"

FAILED=0
step() { echo; echo "== $*"; }

step "Compilation (py_compile)"
for f in adb.py backup.py bloat_db.py debloat_gui.py debloat_cli.py; do
  python3 -m py_compile "$f" || FAILED=1
done
echo "OK — tous les modules compilent."

step "Lint rapide (si pyflakes disponible)"
if python3 -m pyflakes --version >/dev/null 2>&1; then
  python3 -m pyflakes adb.py backup.py bloat_db.py debloat_gui.py debloat_cli.py tests/ || FAILED=1
else
  echo "(pyflakes absent — ignoré)"
fi

step "Fichiers de tests trouvés"
ls -1 tests/test_*.py

step "Tests unitaires"
python3 -m unittest discover -s tests -v 2>&1 || FAILED=1

if command -v xvfb-run >/dev/null 2>&1; then
  step "Tests GUI complets sous Xvfb (y compris stress)"
  xvfb-run -a python3 -m unittest discover -s tests -v 2>&1 || FAILED=1
else
  echo "(xvfb-run absent — les tests GUI ont été sautés au-dessus)"
fi

step "Résultat global"
if [ "$FAILED" -eq 0 ]; then
  echo "Vérification complète passée."
else
  echo "Échecs détectés — voir ci-dessus."
fi
exit "$FAILED"
