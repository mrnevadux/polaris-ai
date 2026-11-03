"""Opérations sur fichiers. Aucune suppression définitive : corbeille uniquement."""
import shutil
from pathlib import Path

CLASSIFY = {
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".heic"},
    "PDF": {".pdf"},
    "Documents": {".doc", ".docx", ".odt", ".txt", ".rtf", ".md"},
    "Tableurs": {".xls", ".xlsx", ".csv", ".ods"},
    "Présentations": {".ppt", ".pptx", ".odp"},
    "Vidéos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    "Musique": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
}


class FileError(Exception):
    pass


def rename(path: Path, new_name: str) -> Path:
    if not new_name or any(c in new_name for c in '\\/:*?"<>|'):
        raise FileError("Nom de fichier invalide.")
    target = path.with_name(new_name)
    if target.exists():
        raise FileError(f"« {new_name} » existe déjà : je n'écrase rien.")
    path.rename(target)
    return target


def move(path: Path, dest_dir: Path) -> Path:
    if not dest_dir.is_dir():
        raise FileError("Le dossier de destination n'existe pas.")
    target = dest_dir / path.name
    if target.exists():
        raise FileError(f"« {path.name} » existe déjà dans le dossier de destination : je n'écrase rien.")
    shutil.move(str(path), str(target))
    return target


def trash(path: Path):
    if path.is_dir():
        raise FileError("Je ne supprime pas de dossiers.")
    from send2trash import send2trash
    send2trash(str(path))


def unique_target(folder: Path, name: str) -> Path:
    t = folder / name
    i = 1
    while t.exists():
        t = folder / f"{Path(name).stem} ({i}){Path(name).suffix}"
        i += 1
    return t


def plan_classify(folder: Path) -> dict:
    plan = {}
    for p in folder.iterdir():
        if p.is_file() and not p.name.startswith(".") and p.name.lower() != "desktop.ini":
            for cat, exts in CLASSIFY.items():
                if p.suffix.lower() in exts:
                    plan.setdefault(cat, []).append(p)
                    break
    return plan


def apply_classify(folder: Path, plan: dict) -> int:
    n = 0
    for cat, files in plan.items():
        sub = folder / cat
        sub.mkdir(exist_ok=True)
        for f in files:
            shutil.move(str(f), str(unique_target(sub, f.name)))
            n += 1
    return n
