#!/usr/bin/env python3
"""Thème de l'interface : la palette Cobalt du site (devfrp.github.io/debloat-android).

Papier clair, encre bleu-gris, filets fins, boutons en touches (face claire sur un
bord plus sombre), un seul signal cobalt ; le journal reste sur graphite, comme le
code sur le site. Les polices du site sont utilisées si elles sont installées,
sinon une police système proche prend le relais.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        # Papier et encre
        "PAPER": "#f8fbfe", "PAPER2": "#eff3f8", "PAPER3": "#e3e8ef",
        "INK": "#111825", "INK_MUTED": "#5d646e", "INK_FAINT": "#9aa1ab",
        "RULE": "#dadee4", "RULE2": "#c2c8cf",
        # Le signal cobalt
        "ACCENT": "#0462d3", "ACCENT_DEEP": "#0040bb", "ACCENT_EDGE": "#003d98",
        "ACCENT_WASH": "#e3f0ff", "ACCENT_INK": "#f8fbfe",
        # Touches
        "KEY_FACE": "#fcfdff", "KEY_EDGE": "#b7bec8",
        # Statuts sur papier
        "SUCCESS": "#21763c", "ERROR": "#be2323",
        # Graphite (journal, détails des backups)
        "GRAPHITE": "#121823", "GRAPHITE_INK": "#e3e8ee", "GRAPHITE_MUTED": "#939ca9",
        "LOG_OK": "#7fcf95", "LOG_WARN": "#75b4ff", "LOG_ERR": "#f2555a",
    },
    # Re-dérivé du clair, jamais inversé : les surfaces s'éclaircissent avec
    # l'élévation, l'accent gagne en clarté et perd un peu de saturation.
    "dark": {
        "PAPER": "#171e29", "PAPER2": "#10161f", "PAPER3": "#212935",
        "INK": "#e6ecf2", "INK_MUTED": "#9199a4", "INK_FAINT": "#626a75",
        "RULE": "#29313d", "RULE2": "#3a4350",
        "ACCENT": "#498beb", "ACCENT_DEEP": "#85bbfd", "ACCENT_EDGE": "#1f53aa",
        "ACCENT_WASH": "#172a45", "ACCENT_INK": "#070b12",
        "KEY_FACE": "#1d2531", "KEY_EDGE": "#0a0e14",
        "SUCCESS": "#62bb78", "ERROR": "#ef675c",
        "GRAPHITE": "#0a0e15", "GRAPHITE_INK": "#e3e8ee", "GRAPHITE_MUTED": "#939ca9",
        "LOG_OK": "#7fcf95", "LOG_WARN": "#75b4ff", "LOG_ERR": "#f2555a",
    },
}
MODES = ("auto", "light", "dark")
MODE = "light"
PAPER = PAPER2 = PAPER3 = INK = INK_MUTED = INK_FAINT = RULE = RULE2 = ""
ACCENT = ACCENT_DEEP = ACCENT_EDGE = ACCENT_WASH = ACCENT_INK = KEY_FACE = KEY_EDGE = ""
SUCCESS = ERROR = GRAPHITE = GRAPHITE_INK = GRAPHITE_MUTED = LOG_OK = LOG_WARN = LOG_ERR = ""
globals().update(PALETTES["light"])


def system_prefers_dark() -> bool:
    """Le système demande-t-il un thème sombre ? Faux en cas de doute."""
    try:
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        if sys.platform == "darwin":
            out = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                 capture_output=True, text=True, timeout=2)
            return out.stdout.strip().lower() == "dark"
        if "dark" in os.environ.get("GTK_THEME", "").lower():
            return True
        out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                             capture_output=True, text=True, timeout=2)
        return "dark" in out.stdout.lower()
    except (OSError, subprocess.SubprocessError, ValueError):
        return False


def _prefs_path() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "debloat-android", "settings.json")


def stored_mode() -> str:
    """Apparence choisie (« auto » par défaut, ou si le fichier est illisible)."""
    try:
        with open(_prefs_path(), encoding="utf-8") as fh:
            mode = json.load(fh).get("theme", "auto")
    except (OSError, ValueError, AttributeError):
        return "auto"
    return mode if mode in MODES else "auto"


def save_mode(mode: str) -> None:
    path = _prefs_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"theme": mode}, fh)
        os.replace(tmp, path)
    except OSError:
        pass  # préférence d'affichage : ne jamais bloquer l'application pour ça


def resolve(mode: str) -> str:
    if mode == "auto":
        return "dark" if system_prefers_dark() else "light"
    return mode if mode in PALETTES else "light"


DISPLAY = ("Familjen Grotesk", "Segoe UI Semibold", "SF Pro Display", "Helvetica Neue",
           "DejaVu Sans", "Helvetica")
BODY = ("IBM Plex Sans", "Segoe UI", "SF Pro Text", "Helvetica Neue", "DejaVu Sans",
        "Helvetica")
MONO = ("JetBrains Mono", "Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono",
        "Courier New")

_fonts: dict[str, str] = {}


def _pick(root: tk.Misc, candidates: tuple[str, ...]) -> str:
    try:
        available = {f.lower() for f in tkfont.families(root)}
    except tk.TclError:
        available = set()
    for name in candidates:
        if name.lower() in available:
            return name
    return candidates[-1]


def font(kind: str, size: int, weight: str = "normal") -> tuple:
    """Police du thème (« display », « body » ou « mono ») ; à appeler après apply()."""
    return (_fonts.get(kind, ""), size, weight)


def apply(root: tk.Tk, mode: str | None = None) -> str:
    """Applique le thème (« auto », « light » ou « dark » ; par défaut l'apparence
    enregistrée) à toute l'application ; renvoie le mode effectif."""
    global MODE
    MODE = resolve(stored_mode() if mode is None else mode)
    globals().update(PALETTES[MODE])
    _fonts["display"] = _pick(root, DISPLAY)
    _fonts["body"] = _pick(root, BODY)
    _fonts["mono"] = _pick(root, MONO)
    body = font("body", 10)
    display = font("display", 10, "bold")

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=PAPER2, foreground=INK, font=body,
                    bordercolor=RULE2, lightcolor=PAPER, darkcolor=RULE,
                    troughcolor=PAPER3, focuscolor=ACCENT,
                    selectbackground=ACCENT, selectforeground=ACCENT_INK,
                    insertcolor=INK)
    style.configure("TFrame", background=PAPER2)
    style.configure("TLabel", background=PAPER2, foreground=INK)
    style.configure("Muted.TLabel", foreground=INK_MUTED)
    style.configure("Hint.TLabel", foreground=ACCENT_DEEP)
    style.configure("Device.TLabel", font=font("display", 12, "bold"))
    style.configure("Header.TLabel", font=display)
    style.configure("Status.TLabel", background=PAPER, foreground=INK_MUTED,
                    bordercolor=RULE, relief="solid", borderwidth=1, padding=(8, 3))

    # Touches : face claire, bord inférieur plus sombre (darkcolor de clam)
    style.configure("TButton", background=KEY_FACE, foreground=INK, bordercolor=RULE2,
                    lightcolor=KEY_FACE, darkcolor=KEY_EDGE, padding=(12, 6),
                    font=font("display", 10), focusthickness=1)
    style.map("TButton",
              background=[("disabled", PAPER2), ("pressed", PAPER3), ("active", PAPER)],
              foreground=[("disabled", INK_FAINT), ("active", ACCENT_DEEP)],
              darkcolor=[("disabled", RULE), ("pressed", PAPER3)],
              lightcolor=[("pressed", PAPER3)],
              bordercolor=[("focus", ACCENT)])
    style.configure("Accent.TButton", background=ACCENT, foreground=ACCENT_INK,
                    bordercolor=ACCENT_EDGE, lightcolor=ACCENT, darkcolor=ACCENT_EDGE,
                    font=font("display", 10, "bold"))
    style.map("Accent.TButton",
              background=[("disabled", PAPER3), ("pressed", ACCENT_EDGE), ("active", ACCENT_DEEP)],
              foreground=[("disabled", INK_FAINT), ("active", ACCENT_INK)],
              darkcolor=[("disabled", RULE), ("pressed", ACCENT_EDGE)],
              lightcolor=[("disabled", PAPER3), ("pressed", ACCENT_EDGE), ("active", ACCENT_DEEP)],
              bordercolor=[("disabled", RULE)])

    style.configure("TRadiobutton", background=PAPER2, foreground=INK,
                    indicatorbackground=KEY_FACE, indicatorforeground=ACCENT,
                    indicatormargin=(0, 0, 6, 0), padding=(0, 3))
    style.map("TRadiobutton",
              background=[("active", PAPER2)],
              foreground=[("active", ACCENT_DEEP)],
              indicatorbackground=[("selected", ACCENT), ("active", ACCENT_WASH)])

    style.configure("TEntry", fieldbackground=KEY_FACE, foreground=INK, bordercolor=INK_MUTED,
                    lightcolor=KEY_FACE, darkcolor=KEY_FACE, padding=(6, 4))
    style.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])

    style.configure("Treeview", background=PAPER, fieldbackground=PAPER, foreground=INK,
                    bordercolor=RULE, lightcolor=PAPER, darkcolor=PAPER, rowheight=24,
                    font=font("mono", 9))
    style.map("Treeview", background=[("selected", ACCENT_WASH)],
              foreground=[("selected", ACCENT_DEEP)])
    style.configure("Treeview.Heading", background=PAPER3, foreground=INK_MUTED,
                    bordercolor=RULE2, lightcolor=PAPER3, darkcolor=PAPER3, relief="flat",
                    font=font("display", 10), padding=(6, 5))
    style.map("Treeview.Heading", background=[("active", PAPER2)],
              foreground=[("active", ACCENT_DEEP)])

    style.configure("TProgressbar", background=ACCENT, troughcolor=PAPER3, bordercolor=RULE,
                    lightcolor=ACCENT, darkcolor=ACCENT_DEEP, thickness=6)
    style.configure("TLabelframe", background=PAPER2, bordercolor=RULE)
    style.configure("TLabelframe.Label", background=PAPER2, foreground=INK_MUTED, font=display)
    for orient in ("Vertical", "Horizontal"):
        style.configure(f"{orient}.TScrollbar", background=PAPER3, troughcolor=PAPER2,
                        bordercolor=PAPER2, lightcolor=PAPER3, darkcolor=PAPER3,
                        arrowcolor=INK_MUTED)
        style.map(f"{orient}.TScrollbar", background=[("active", RULE2)])

    # Widgets tk classiques : fenêtres secondaires, listes, textes
    root.configure(background=PAPER2)
    root.option_add("*Toplevel.background", PAPER2)
    root.option_add("*Listbox.background", PAPER)
    root.option_add("*Listbox.foreground", INK)
    root.option_add("*Listbox.selectBackground", ACCENT_WASH)
    root.option_add("*Listbox.selectForeground", ACCENT_DEEP)
    root.option_add("*Listbox.highlightColor", ACCENT)
    root.option_add("*Listbox.highlightBackground", RULE)
    root.option_add("*Listbox.relief", "flat")
    root.option_add("*Text.background", PAPER)
    root.option_add("*Text.foreground", INK)
    root.option_add("*Text.relief", "flat")
    root.option_add("*Text.highlightThickness", 0)
    root.option_add("*Text.selectBackground", ACCENT)
    root.option_add("*Text.selectForeground", ACCENT_INK)
    root.option_add("*Menu.background", PAPER)
    root.option_add("*Menu.activeBackground", ACCENT)
    root.option_add("*Menu.activeForeground", ACCENT_INK)
    return MODE


def graphite_text(widget: tk.Text) -> None:
    """Un tk.Text sur graphite, en mono (journal, détail d'un backup)."""
    widget.configure(background=GRAPHITE, foreground=GRAPHITE_INK, insertbackground=GRAPHITE_INK,
                     selectbackground=ACCENT, selectforeground=ACCENT_INK,
                     font=font("mono", 9), relief="flat", highlightthickness=0,
                     padx=8, pady=6)
