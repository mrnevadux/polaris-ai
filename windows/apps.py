"""Ouverture / fermeture d'applications. Liste blanche + raccourcis du menu Démarrer."""
import difflib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from core.textutil import normalize

ARTICLES = {"le", "la", "les", "l", "un", "une", "mon", "ma", "mes", "du", "de", "des", "d", "au", "aux", "application", "appli", "logiciel", "programme"}
PROTECTED = {"system", "svchost", "csrss", "winlogon", "dwm", "services", "lsass", "smss", "explorer",
             "wininit", "registry", "python", "pythonw", "polaris", "taskhostw", "sihost", "fontdrvhost"}


@dataclass
class AppSpec:
    label: str
    target: str
    procs: tuple
    aliases: tuple
    close_classes: tuple = ()


KNOWN = [
    AppSpec("le Bloc-notes", "notepad.exe", ("notepad.exe",), ("bloc notes", "notepad", "blocnotes")),
    AppSpec("la Calculatrice", "calc.exe", ("calculatorapp.exe", "calculator.exe", "calc.exe", "win32calc.exe"),
            ("calculatrice", "calculette", "calc", "calculator")),
    AppSpec("l'Explorateur de fichiers", "explorer.exe", ("explorer.exe",),
            ("explorateur", "explorateur de fichiers", "explorateur windows", "explorer"), ("CabinetWClass",)),
    AppSpec("Paint", "mspaint.exe", ("mspaint.exe", "paintstudio.view.exe"), ("paint", "mspaint")),
    AppSpec("le Gestionnaire des tâches", "taskmgr.exe", ("taskmgr.exe",), ("gestionnaire des taches", "task manager", "taskmgr")),
    AppSpec("l'Outil Capture d'écran", "ms-screenclip:", ("screenclippinghost.exe", "snippingtool.exe"),
            ("capture d ecran", "outil capture", "capture", "snipping tool")),
    AppSpec("Microsoft Edge", "msedge", ("msedge.exe",), ("edge", "microsoft edge", "msedge")),
    AppSpec("Google Chrome", "chrome", ("chrome.exe",), ("chrome", "google chrome")),
    AppSpec("Firefox", "firefox", ("firefox.exe",), ("firefox",)),
    AppSpec("Word", "winword", ("winword.exe",), ("word", "microsoft word")),
    AppSpec("Excel", "excel", ("excel.exe",), ("excel", "microsoft excel")),
    AppSpec("PowerPoint", "powerpnt", ("powerpnt.exe",), ("powerpoint", "microsoft powerpoint")),
]


def strip_articles(n: str) -> str:
    toks = n.split()
    while toks and toks[0] in ARTICLES:
        toks.pop(0)
    return " ".join(toks)


def resolve_known(name: str):
    n = strip_articles(normalize(name))
    if not n:
        return None
    padded = f" {n} "
    for spec in KNOWN:
        for a in spec.aliases:
            if n == a or f" {a} " in padded:
                return spec
    return None


# ---------- raccourcis Menu Démarrer ----------
_shortcuts = None
_store_apps = None
BAD_WORDS = ("uninstall", "desinstall", "readme", "documentation", "help", "aide", "license", "licence")


def _scan_shortcuts():
    global _shortcuts
    if _shortcuts is None:
        roots = [Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
                 Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]
        found = []
        for r in roots:
            if r.is_dir():
                for p in r.rglob("*.lnk"):
                    n = normalize(p.stem)
                    if not any(b in n for b in BAD_WORDS):
                        found.append((n, p))
        _shortcuts = found
    return _shortcuts


def _scan_store_apps():
    """Applications du Menu Démarrer (y compris Microsoft Store) via Get-StartApps, une seule fois."""
    global _store_apps
    if _store_apps is None:
        _store_apps = []
        if sys.platform == "win32":
            try:
                cmd = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"
                out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                                     capture_output=True, timeout=25, creationflags=0x08000000)
                data = json.loads(out.stdout.decode("utf-8", errors="replace") or "[]")
                if isinstance(data, dict):
                    data = [data]
                _store_apps = [(normalize(d.get("Name", "")), d.get("Name", ""), d.get("AppID", "")) for d in data if d.get("AppID")]
            except Exception:
                _store_apps = []
    return _store_apps


def _best(query: str, names):
    """names: liste de (nom_normalisé, objet). Retourne le meilleur objet ou None."""
    q = strip_articles(normalize(query))
    if not q:
        return None
    scored = []
    for n, obj in names:
        if n == q:
            s = 3.0
        elif n.startswith(q):
            s = 2.0 + len(q) / max(len(n), 1)
        elif f" {q} " in f" {n} " or q in n.split():
            s = 1.5
        elif len(q) >= 4 and q in n:
            s = 1.2
        else:
            r = difflib.SequenceMatcher(None, q, n).ratio()
            s = r if r >= 0.78 else 0
        if s:
            scored.append((s, obj))
    return max(scored, key=lambda x: x[0])[1] if scored else None


def launch(name: str):
    """Retourne (ok, message). Ne prétend jamais avoir réussi si le lancement échoue."""
    spec = resolve_known(name)
    try:
        if spec:
            os.startfile(spec.target)
            return True, f"J'ai lancé {spec.label}."
        lnk = _best(name, [(n, p) for n, p in _scan_shortcuts()])
        if lnk:
            os.startfile(str(lnk))
            return True, f"J'ai lancé {lnk.stem}."
        app = _best(name, [(n, (label, appid)) for n, label, appid in _scan_store_apps()])
        if app:
            os.startfile("shell:AppsFolder\\" + app[1])
            return True, f"J'ai lancé {app[0]}."
    except AttributeError:
        return False, "Le lancement d'applications n'est disponible que sous Windows."
    except OSError as e:
        return False, f"Windows n'a pas pu lancer « {name} » ({e})."
    return False, f"Je ne trouve aucune application nommée « {name} »."


def _target_pids(name: str):
    import psutil
    spec = resolve_known(name)
    me = os.getpid()
    pids, classes = [], ()
    q = strip_articles(normalize(name)).replace(" ", "")
    for p in psutil.process_iter(["name"]):
        try:
            pname = (p.info["name"] or "").lower()
            stem = normalize(pname.rsplit(".", 1)[0]).replace(" ", "")
            if p.pid == me or stem in PROTECTED:
                if not (spec and pname in spec.procs and stem == "explorer"):
                    continue
            if spec:
                if pname in spec.procs:
                    pids.append(p.pid)
            elif len(q) >= 3 and (q == stem or (len(q) >= 4 and q in stem)):
                pids.append(p.pid)
        except Exception:
            continue
    if spec:
        classes = spec.close_classes
    return pids, classes, (spec.label if spec else name)


def close(name: str):
    """Demande la fermeture des fenêtres de l'application (l'appli peut proposer d'enregistrer)."""
    from windows import winctl
    try:
        pids, classes, label = _target_pids(name)
        if not pids:
            return False, f"« {name} » ne semble pas être ouverte."
        n = winctl.close_windows(pids, classes or None)
    except OSError as e:
        return False, str(e)
    if n == 0:
        return False, f"Je n'ai trouvé aucune fenêtre ouverte pour {label}."
    return True, f"J'ai demandé la fermeture de {label} ({n} fenêtre{'s' if n > 1 else ''}). Si elle a des données non enregistrées, elle te posera la question."
