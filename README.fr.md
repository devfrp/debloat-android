# debloat-android

Débloat un téléphone Android **sans root**, via ADB : une **interface graphique** (Tkinter,
stdlib Python — zéro dépendance) et un **compagnon CLI**, avec les mêmes garde-fous.
([English README](README.md))

- Détecte le téléphone branché en USB (débogage USB activé).
- Liste toutes les apps et les classe : bloat sûr, avancé, inconnu, composants protégés.
- Désinstalle les apps système pour ton profil utilisateur (`pm uninstall --user 0`)
  -> **réversible** : chaque retrait est consigné dans un backup JSON et restaurable en un clic.
- **Rien n'est coché d'office** après un scan : l'utilisateur coche explicitement chaque app
  qu'il veut retirer (clic sur la ligne, ou touche Espace sur la ligne sélectionnée).
- Les apps utilisateur (Play Store) sont à part : leur retrait est **définitif**
  (données perdues), confirmation dédiée.
- Les composants critiques du système (Play services, WebView, claviers, lanceurs…) sont
  **bloqués volontairement** : impossible de les cocher.
- Avant tout retrait, l'app **propose de sauvegarder les APK** de la sélection sur le PC
  (`backups/<serial>/apks/<paquet>/`, via `adb pull`).

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

2. Sur le téléphone : *Paramètres -> À propos -> 7 appuis sur « numéro de build » -> Options pour développeurs -> Débogage USB*.

3. Lancer :

   ```bash
   ./run.sh            # interface graphique : Rafraîchir -> Scan -> cocher -> Désinstaller
   ```

## Interface graphique

**Rafraîchir les appareils -> Scanner les applications -> cocher chaque app à retirer -> Désinstaller la sélection.**

| Colonne | Signification | Comportement |
|---|---|---|
| `sans danger` (sûr) | bloat classique, retrait considéré sûr | à cocher toi-même (aucune coche automatique) |
| `avancé` | une fonctionnalité peut disparaître | décochée, confirmation douce |
| `inconnu` (hors base) | pas dans la base | décochée, double confirmation |
| `protégé` | verrouillé (Play services, WebView, clavier…) | non cochable — verrouillé |
| app utilisateur (Play Store) | suppression définitive | confirmation distincte |

Autres fonctions : « Rapport » (export JSON du scan), « Gestionnaire de backups »
(restauration), vues filtrées (bloat / protégé / système / utilisateur / tout), recherche,
journal détaillé, notes au survol, double-clic pour les détails. Après chaque retrait, une
entrée est ajoutée automatiquement au journal JSON de restauration.

## Compagnon CLI

Mêmes garde-fous, sans fenêtre :

```bash
python3 debloat_cli.py devices                     # appareils détectés
python3 debloat_cli.py scan                        # scan + classification
python3 debloat_cli.py scan --risk safe,advanced   # filtre par risque
python3 debloat_cli.py scan --json                 # sortie JSON (stdout)
python3 debloat_cli.py uninstall com.miui.msa.global --yes
python3 debloat_cli.py uninstall com.miui.msa.global --backup-apks --yes   # + sauvegarde APK
python3 debloat_cli.py uninstall com.paquet.???    # refusé : exige --allow-unknown
python3 debloat_cli.py restore --file backups/X.json --dry-run
```

Codes de sortie : `0` ok, `1` erreur/échec adb, `2` garde-fou (paquet protégé/inconnu/app
utilisateur sans opt-in). Option globale `--serial S` si plusieurs appareils.

## Restaurer

- GUI : **Gestionnaire de backups** -> choisir le fichier -> restaurer (rescan automatique ensuite).
- CLI : `python3 debloat_cli.py restore [--file backups/X.json] [--yes] [--dry-run]`.

Restauration : `adb shell cmd package install-existing <paquet>` (apps système uniquement —
réinstalle une app utilisateur depuis une boutique). Les APK sauvegardés avant retrait restent
installables à la main si besoin.

> Robustesse : écriture atomique (tmp + `os.replace`) ; un backup illisible est mis en
> **quarantaine** (`*.corrupt-<date>`) au lieu d'être écrasé — jamais de perte d'historique
> silencieuse. Un redémarrage peut aider après restauration de services système.

## Base de bloat

`bloat_db.py` contient ~115 paquets connus (Samsung, Xiaomi/MIUI, Oppo/Realme/OnePlus,
Huawei/Honor, Google, Sony, LG, Tecno/Infinix…) + une liste noire de composants protégés
par préfixe (`com.android.*`, `android.*`, `com.google.android.trichromelibrary*`).

Pour enrichir la base, ajoute une ligne dans `BLOAT_DB` :

```python
"paquet.de.lapp": (bloat_db.A, "Nom lisible", "Conséquences du retrait / pourquoi le retirer."),
```

Un paquet absent de la base apparaît comme *inconnu* — rien n'est cassé pour autant :
l'utilisateur décide.

## Vérification en profondeur

```bash
./verify.sh
```

- `adb.py` : parsing `devices -l` (multi-appareils, états, daemon), getprop, listes de
  paquets, formes de commandes exactes, timeouts, binaire absent.
- `backup.py` : atomicité, doublons, portabilité des serials Wi-Fi (`127.0.0.1:5555`),
  **quarantaine de fichier corrompu** (jamais écrasé), arborescence des APK.
- `bloat_db.py` : intégrité (noms/risques), aucun recouvrement base/interdits, préfixes.
- `debloat_cli.py` : garde-fous (protégé refusé, inconnu opt-in, utilisateur opt-in),
  dry-run, codes de sortie, journal, `--backup-apks`.
- **GUI complète sous Xvfb** (auto-adopt, vues, coches, désinstallation, backup corrompu,
  restauration, export, proposition de sauvegarde APK, réactions aux erreurs adb) avec faux ADB.
- **Intégration subprocess** : le CLI exécuté pour de vrai contre un faux binaire `adb` —
  test du vrai chemin `shutil.which -> subprocess -> parsing`, `-s <serial>` consommé par adb inclus.
- **Stress** : scan de 1500 apps -> scan ~1 s, refresh ~0,02 s.

## Structure

```
debloat_gui.py   # interface Tkinter (vues, confirmations, sauvegarde APK, export, journal)
debloat_cli.py   # CLI compagnon (devices / scan / uninstall / restore)
adb.py           # wrapper ADB (devices, getprop, pm list/uninstall, install-existing, pull)
bloat_db.py      # base de bloat connue + composants protégés
backup.py        # persistance backups/<serial>.json (atomicité, quarantaine, dossier APK)
tests/           # tests unitaires + GUI (Xvfb) + intégration subprocess
verify.sh        # exécute toute la vérification
run.sh           # lance la GUI (vérifie la présence d'adb)
backups/         # créés automatiquement : <serial>.json et <serial>/apks/
```

## Avertissement

Utilise ce logiciel à tes propres risques : le retrait `--user 0` est réversible, mais si tu
retires une app dont une autre dépend (service de caméra, clavier…), la fonctionnalité peut
se comporter bizarrement jusqu'à restauration. Teste petit, une catégorie à la fois. Aucune
donnée n'est envoyée sur Internet ; tout passe par ton câble USB. Licence : MIT.
