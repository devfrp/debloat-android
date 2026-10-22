# debloat-android 🧹

Outils **sans root** pour débloat un téléphone Android via ADB : une **interface graphique** (Tkinter,
stdlib Python — zéro dépendance) et un **compagnon CLI**, avec les mêmes garde-fous.

- Détecte le téléphone branché en USB (débogage USB activé).
- Liste toutes les apps et les classe : bloat sûre, avancée, inconnue, composants protégés.
- Désinstalle les apps système pour ton profil utilisateur (`pm uninstall --user 0`)
  → **réversible** : chaque retrait est consigné dans un backup JSON et restaurable en un clic.
- Les apps utilisateur (Play Store) sont signalées à part : leur retrait est **définitif**, confirmation dédiée.
- Les composants critiques du système (Play services, WebView, claviers, lanceurs…) sont **bloqués volontairement**.

## Démarrage rapide

1. Installer ADB :

   | OS | Commande |
   |---|---|
   | Debian / Ubuntu | `sudo apt install adb` |
   | Fedora | `sudo dnf install android-tools` |
   | Arch | `sudo pacman -S android-tools` |
   | macOS | `brew install --cask android-platform-tools` |
   | Windows | [platform-tools](https://developer.android.com/studio/releases/platform-tools) (ajouter au PATH ou `set ADB_PATH=…`) |

   Si `adb` est ailleurs : `ADB_PATH=/chemin/vers/adb python3 debloat_gui.py`

2. Sur le téléphone : *Paramètres → À propos → 7 appuis sur « numéro de build » → Options pour développeurs → Débogage USB*.

3. Lancer :

   ```bash
   ./run.sh            # interface graphique : → 🔍 Scan → coche → 🗑️ Désinstaller
   ```

## Interface graphique

**🔄 Rafraîchir les appareils → 🔍 Scanner les applications → coche chaque app à retirer → 🗑️ Désinstaller la sélection.**

Rien n'est coché d'office : **c'est toi qui coche explicitement** chaque app (un clic sur la ligne,
ou Espace sur la ligne sélectionnée). Le bouton « ✅ Cocher les sûrs (vue) » reste un raccourci optionnel.

| Icône | Signification | Comportement |
|---|---|---|
| ✅ | bloat sûr (`safe`) | à cocher toi-même (aucune coche automatique) |
| 🟠 | avancé (`advanced`) | décochée, confirmation douce |
| ❔ | inconnu (hors base) | décochée, double confirmation |
| ⛔ | protégé | non décochable, par précaution : Play services, WebView, clavier, lanceur… |
| 📦 | app utilisateur | suppression définitive des données → confirmation distincte |

Autres fonctions : « 💾 Rapport » (export JSON du scan), « ⏪ Gestionnaire de backups »
(restauration), vues filtrées (bloat / protégé / système / utilisateur / tout), recherche,
journal détaillé, notes au survol et double-clic.

## Compagnon CLI

Mêmes garde-fous, sans fenêtre :

```bash
python3 debloat_cli.py devices                     # appareils détectés
python3 debloat_cli.py scan                        # scan + classification
python3 debloat_cli.py scan --risk safe,advanced   # filtre par risque
python3 debloat_cli.py scan --json                 # sortie JSON (stdout)
python3 debloat_cli.py uninstall com.miui.msa.global --yes
python3 debloat_cli.py uninstall com.paquet.???    # refusé : ❔ exige --allow-unknown
python3 debloat_cli.py restore --file backups/X.json --dry-run
```

Codes de sortie : `0` ok · `1` erreur/échec adb · `2` garde-fou (paquet protégé/inconnu/app
utilisateur sans opt-in). Option globale `--serial S` si plusieurs appareils.

## Restaurer

- GUI : **⏪ Gestionnaire de backups** → choisir le fichier → restaurer (rescan automatique ensuite).
- CLI : `python3 debloat_cli.py restore [--file backups/X.json] [--yes] [--dry-run]`.

Technique de restauration : `adb shell cmd package install-existing <paquet>` (apps système
uniquement — pour une app utilisateur, réinstalle depuis la boutique). Le retrait d'apps système
est réalisé sur *user 0* : l'APK reste sur le téléphone.

> Robustesse : écriture atomique (tmp + `os.replace`) ; un backup illisible est mis en **quarantaine**
> (`*.corrupt-<date>`) au lieu d'être écrasé — jamais de perte d'historique silencieuse.
> Un redémarrage du téléphone peut être utile après la restauration de services système.

## Base de bloat

`bloat_db.py` contient ~115 paquets connus (Samsung, Xiaomi/MIUI, Oppo/Realme/OnePlus, Huawei/Honor,
Google, Sony, LG, Tecno/Infinix…) + une liste noire de composants protégés par préfixe
(`com.android.*`, `android.*`, `com.google.android.trichromelibrary*`).

Pour enrichir la base, ajoute une ligne dans `BLOAT_DB` :

```python
"paquet.de.lapp": (bloat_db.A, "Nom lisible", "Qu'est-ce que ça fait / pourquoi le retirer."),
```

Un paquet absent de la base apparaît comme ❔ inconnu — rien n'est cassé pour autant, l'utilisateur décide.

## Vérification en profondeur

```bash
./verify.sh
```

- `adb.py` : parsing `devices -l` (multi-appareils, états, daemon), getprop, listes de paquets,
  formes de commandes exactes, timeouts, binaire absent.
- `backup.py` : atomicité, doublons, portabilité des serials Wi-Fi (`127.0.0.1:5555`),
  **quarantaine de fichier corrompu** (jamais écrasé).
- `bloat_db.py` : intégrité (noms/risques), aucun recouvrement base/interdits, préfixes.
- `debloat_cli.py` : garde-fous (⛔ refusé, ❔ opt-in, 📦 opt-in), dry-run, codes de sortie, backup.
- **GUI complète sous Xvfb** (auto-adopt, vues, coches, désinstallation, backup corrompu, restauration,
  export, réactions aux erreurs adb) avec fake ADB.
- **Intégration subprocess** : le vrai CLI exécuté contre un faux binaire `adb` — testing du vrai
  chemin `shutil.which → subprocess → parsing`, `-s <serial>` consommé par adb inclus.
- **Stress** : scan de 1500 apps → scan ≈ 1 s, refresh de la liste ≈ 0,02 s.

## Structure

```
debloat_gui.py   # interface Tkinter (vues, confirmations, backups, export, journal)
debloat_cli.py   # CLI compagnon (devices / scan / uninstall / restore)
adb.py           # wrapper ADB (devices, getprop, pm list/uninstall, install-existing)
bloat_db.py      # base de bloat connue + composants protégés
backup.py        # persistance backups/<serial>.json (atomicité, quarantaine)
tests/           # tests unitaires + GUI (Xvfb) + intégration subprocess
verify.sh        # exécute toute la vérification
run.sh           # lance la GUI (vérifie la présence d'adb)
backups/         # créés automatiquement : <serial>.json
```

## Avertissement

Utilise les outils à tes propres risques : le retrait « --user 0 » est réversible, mais si tu retires
une app dont dépend une autre app (ex. service de caméra, clavier), la fonctionnalité peut casser
jusqu'à restauration. Teste petit, une catégorie à la fois. Aucune donnée n'est envoyée sur Internet
par ce logiciel ; tout passe par ton câble USB. License : MIT.
