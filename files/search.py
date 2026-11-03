"""Recherche de fichiers (nom, extension, contenu) dans les dossiers autorisés."""
import html
import os
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from core.textutil import normalize

EXT_GROUPS = {
    "image": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".heic", ".tiff", ".svg"},
    "pdf": {".pdf"},
    "word": {".docx", ".doc", ".odt", ".rtf"},
    "excel": {".xlsx", ".xls", ".csv", ".ods"},
    "powerpoint": {".pptx", ".ppt", ".odp"},
    "python": {".py"},
    "texte": {".txt", ".md", ".log"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    "audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz"},
}
TEXT_EXT = {".txt", ".md", ".py", ".csv", ".json", ".log", ".html", ".htm", ".xml", ".ini", ".cfg",
            ".yaml", ".yml", ".js", ".css", ".c", ".cpp", ".java", ".ts", ".tsx", ".sql", ".bat"}
SKIP_DIRS = {"node_modules", "__pycache__", "appdata", "$recycle.bin", ".git", "venv", ".venv", "site-packages"}
MAX_CONTENT_BYTES = 5 * 1024 * 1024


@dataclass
class Result:
    path: Path
    size: int
    mtime: float

    @property
    def name(self):
        return self.path.name


def exts_from(spec) -> set:
    """Convertit 'pdf', 'image', '.py', 'py' ou une liste en ensemble d'extensions."""
    if not spec:
        return set()
    items = spec if isinstance(spec, (list, tuple, set)) else re.split(r"[,\s;]+", str(spec))
    out = set()
    for it in items:
        it = normalize(str(it)).strip()
        if not it:
            continue
        if it in EXT_GROUPS:
            out |= EXT_GROUPS[it]
        else:
            out.add(it if it.startswith(".") else "." + it)
    return out


def extract_text(path: Path, max_chars: int = 200_000) -> str:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXT:
            with open(path, "rb") as f:
                return f.read(max_chars * 2).decode("utf-8", errors="replace")[:max_chars]
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            parts = []
            for page in reader.pages[:40]:
                parts.append(page.extract_text() or "")
                if sum(map(len, parts)) > max_chars:
                    break
            return "\n".join(parts)[:max_chars]
        if ext == ".docx":
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="replace")
            xml = xml.replace("</w:p>", "\n")
            return html.unescape(re.sub(r"<[^>]+>", " ", xml))[:max_chars]
    except Exception:
        return ""
    return ""


def can_read_content(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXT | {".pdf", ".docx"}


def search(roots, query="", exts=None, content="", limit=40, timeout=25.0, max_depth=8):
    tokens = [t for t in normalize(query).split() if t]
    content_n = normalize(content)
    exts = exts or set()
    if not tokens and not exts and not content_n:
        return []
    deadline = time.monotonic() + timeout
    found = []
    seen = set()
    stack = [(Path(r), 0) for r in roots]
    while stack and time.monotonic() < deadline:
        folder, depth = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_symlink() or e.name.startswith("."):
                    continue
                if e.is_dir(follow_symlinks=False):
                    if depth < max_depth and e.name.lower() not in SKIP_DIRS:
                        stack.append((Path(e.path), depth + 1))
                    continue
                p = Path(e.path)
                if exts and p.suffix.lower() not in exts:
                    continue
                if tokens:
                    name_n = normalize(p.stem)
                    if not all(t in name_n for t in tokens):
                        continue
                st = e.stat()
                if content_n:
                    if st.st_size > MAX_CONTENT_BYTES or not can_read_content(p):
                        continue
                    if content_n not in normalize(extract_text(p)):
                        continue
                key = os.path.normcase(str(p))
                if key in seen:
                    continue
                seen.add(key)
                found.append(Result(p, st.st_size, st.st_mtime))
            except OSError:
                continue
        if len(found) >= limit * 5:
            break
    found.sort(key=lambda r: r.mtime, reverse=True)
    return found[:limit]


def human_size(n: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unit == "Go":
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024
