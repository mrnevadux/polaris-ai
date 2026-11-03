"""Compile Polaris.exe avec PyInstaller (utilisé par GitHub Actions, utilisable en local sous Windows)."""
import importlib.util
import os
import sys

import PyInstaller.__main__ as pyi

SEP = ";" if os.name == "nt" else ":"
args = ["main.py", "--noconfirm", "--clean", "--onefile", "--windowed", "--name", "Polaris",
        "--add-data", f"assets{SEP}assets", "--add-data", f"model{SEP}model",
        "--hidden-import", "win32com.client", "--hidden-import", "pythoncom", "--hidden-import", "win32timezone",
        "--hidden-import", "PIL.ImageTk", "--hidden-import", "PIL.ImageGrab", "--hidden-import", "PIL._tkinter_finder"]
if os.path.exists("assets/polaris.ico"):
    args += ["--icon", "assets/polaris.ico"]
for pkg in ("customtkinter", "vosk", "google.genai", "sounddevice", "_sounddevice_data", "pypdf", "send2trash"):
    try:
        found = importlib.util.find_spec(pkg) is not None
    except (ImportError, ValueError):
        found = False
    if found:
        args += ["--collect-all", pkg]
    else:
        print(f"[build] paquet absent, ignoré : {pkg}", file=sys.stderr)
pyi.run(args)
