"""Autorisations : catégories activables et dossiers autorisés."""
import os
from pathlib import Path

CATEGORY_KEYS = {
    "apps": "perm_apps",
    "web": "perm_web",
    "files_read": "perm_files_read",
    "files_modify": "perm_files_modify",
    "control": "perm_control",
}

FOLDER_ALIASES = {
    "bureau": ("Desktop", "Bureau"),
    "documents": ("Documents",),
    "telechargements": ("Downloads", "Téléchargements"),
    "images": ("Pictures", "Images"),
    "videos": ("Videos", "Vidéos"),
    "musique": ("Music", "Musique"),
}


def known_folders() -> list:
    home = Path.home()
    bases = [home] + sorted(p for p in home.glob("OneDrive*") if p.is_dir())
    roots = []
    for alias_names in FOLDER_ALIASES.values():
        for base in bases:
            for n in alias_names:
                p = base / n
                if p.is_dir() and p not in roots:
                    roots.append(p)
    return roots


def folders_for_alias(alias: str) -> list:
    names = FOLDER_ALIASES.get(alias, ())
    home = Path.home()
    bases = [home] + sorted(p for p in home.glob("OneDrive*") if p.is_dir())
    return [b / n for b in bases for n in names if (b / n).is_dir()]


def _inside(path, root) -> bool:
    try:
        p = os.path.normcase(os.path.realpath(path))
        r = os.path.normcase(os.path.realpath(root))
        return os.path.commonpath([p, r]) == r
    except ValueError:
        return False


class Permissions:
    def __init__(self, settings):
        self.settings = settings

    def category_enabled(self, category: str) -> bool:
        key = CATEGORY_KEYS.get(category)
        return True if key is None else bool(self.settings.get(key, True))

    def allowed_roots(self) -> list:
        roots = known_folders()
        for f in self.settings.get("extra_folders", []) or []:
            p = Path(f)
            if p.is_dir() and p not in roots:
                roots.append(p)
        return roots

    def is_allowed(self, path) -> bool:
        return any(_inside(path, r) for r in self.allowed_roots())
