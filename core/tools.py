"""Outils autorisés de Polaris. L'IA ne peut déclencher QUE ces actions, jamais une commande libre."""
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from core.textutil import normalize
from files import manager, search as fsearch
from security.permissions import folders_for_alias
from windows import apps, system, web

DANGEROUS_EXT = {".exe", ".bat", ".cmd", ".ps1", ".msi", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".scr", ".com", ".lnk", ".reg", ".jar", ".hta"}
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


class ToolError(Exception):
    pass


@dataclass
class ToolResult:
    ok: bool
    text: str
    speak: Optional[str] = None


@dataclass
class ToolContext:
    settings: Any
    perms: Any
    gemini: Any
    confirm: Callable[[str], bool]
    stop_speaking: Callable[[], None] = lambda: None
    mic_off: Callable[[], None] = lambda: None
    ui: Any = None
    cancel: Any = field(default_factory=threading.Event)
    screen_ok: bool = False
    last_results: list = field(default_factory=list)

    def resolve_path(self, value: str) -> Path:
        v = (value or "").strip()
        if v.lower().startswith("result:"):
            key = v.split(":", 1)[1].strip().lower()
            if not self.last_results:
                raise ToolError("Je n'ai aucun résultat de recherche en mémoire. Lance d'abord une recherche.")
            try:
                idx = len(self.last_results) - 1 if key in ("last", "dernier") else int(key) - 1
                return self.last_results[idx].path
            except (ValueError, IndexError):
                raise ToolError(f"Il n'y a pas de résultat numéro {key}.")
        p = Path(os.path.expandvars(os.path.expanduser(v)))
        if not v or not p.is_absolute():
            raise ToolError("Je ne connais pas ce fichier : fais d'abord une recherche.")
        if not self.perms.is_allowed(p):
            raise ToolError("Ce fichier est en dehors des dossiers autorisés (Paramètres > Dossiers).")
        if not p.exists():
            raise ToolError("Ce fichier n'existe pas.")
        return p

    def check_allowed(self, p: Path) -> Path:
        if not self.perms.is_allowed(p):
            raise ToolError("Ce chemin est en dehors des dossiers autorisés.")
        return p

    def resolve_folder(self, value: str) -> Path:
        v = (value or "").strip()
        n = normalize(v)
        for alias in ("bureau", "documents", "telechargements", "images", "videos", "musique"):
            if n == alias or n == alias.rstrip("s") or (alias == "telechargements" and n in ("downloads", "telechargement")):
                cands = folders_for_alias(alias)
                if cands:
                    return cands[0]
        p = Path(os.path.expandvars(os.path.expanduser(v)))
        if p.is_absolute() and p.is_dir():
            return self.check_allowed(p)
        raise ToolError(f"Dossier « {value} » introuvable ou non autorisé.")


def _s(args: dict, key: str) -> str:
    v = args.get(key, "")
    return v.strip() if isinstance(v, str) else ("" if v is None else str(v))


# ---------------- outils ----------------
def t_open_app(ctx, a):
    name = _s(a, "name")
    if not name:
        raise ToolError("Quelle application dois-je ouvrir ?")
    if apps.strip_articles(normalize(name)) in ("parametres", "parametre", "reglages", "settings"):
        return t_open_settings(ctx, {})
    ok, msg = apps.launch(name)
    return ToolResult(ok, msg)


def t_close_app(ctx, a):
    name = _s(a, "name")
    if not name:
        raise ToolError("Quelle application dois-je fermer ?")
    ok, msg = apps.close(name)
    return ToolResult(ok, msg)


def t_open_url(ctx, a):
    url = web.resolve_url(_s(a, "url") or _s(a, "site"))
    if not url:
        raise ToolError("Adresse de site non valide (seuls http et https sont autorisés).")
    web.open_url(url)
    return ToolResult(True, f"J'ai ouvert {url} dans ton navigateur.")


def t_open_settings(ctx, a):
    try:
        uri = system.open_settings(_s(a, "page"))
    except AttributeError:
        return ToolResult(False, "L'ouverture des paramètres n'est disponible que sous Windows.")
    except OSError as e:
        return ToolResult(False, f"Impossible d'ouvrir les paramètres Windows ({e}).")
    return ToolResult(True, "J'ai ouvert les paramètres Windows.")


def t_window_action(ctx, a):
    from windows import winctl
    action = normalize(_s(a, "action")).replace(" ", "_")
    try:
        if action in ("minimize_all", "minimiser_tout", "afficher_le_bureau"):
            winctl.minimize_all()
            return ToolResult(True, "J'ai affiché le bureau.")
        ok, msg = winctl.foreground_action(action)
    except OSError as e:
        return ToolResult(False, str(e))
    return ToolResult(ok, msg)


def t_search_files(ctx, a):
    query, content = _s(a, "query"), _s(a, "content")
    exts = fsearch.exts_from(a.get("ext"))
    folder = _s(a, "folder")
    roots = [ctx.resolve_folder(folder)] if folder else ctx.perms.allowed_roots()
    if not roots:
        raise ToolError("Aucun dossier autorisé trouvé.")
    if not (query or exts or content):
        raise ToolError("Que dois-je chercher ? Donne un nom, un type de fichier ou un mot à trouver dedans.")
    limit = a.get("limit") if isinstance(a.get("limit"), int) else 40
    res = fsearch.search(roots, query, exts, content, limit=max(1, min(limit, 100)))
    ctx.last_results = res
    if not res:
        return ToolResult(True, "Je n'ai trouvé aucun fichier correspondant.")
    shown = res[:10]
    lines = [f"{i}. {r.name}  —  {r.path.parent}  ({fsearch.human_size(r.size)})" for i, r in enumerate(shown, 1)]
    more = f"\n… et {len(res) - 10} autres." if len(res) > 10 else ""
    text = f"J'ai trouvé {len(res)} fichier{'s' if len(res) > 1 else ''} :\n" + "\n".join(lines) + more + \
           "\nDis par exemple « ouvre le premier résultat »."
    speak = f"J'ai trouvé {len(res)} fichier{'s' if len(res) > 1 else ''}. Le premier est {shown[0].name}."
    return ToolResult(True, text, speak)


def _confirm_open(ctx, a):
    p = ctx.resolve_path(_s(a, "path"))
    if p.suffix.lower() in DANGEROUS_EXT:
        return f"« {p.name} » est un programme ou un script exécutable. L'ouvrir peut lancer du code sur ton PC. Continuer ?"
    return None


def t_open_file(ctx, a):
    p = ctx.resolve_path(_s(a, "path"))
    try:
        os.startfile(str(p))
    except AttributeError:
        return ToolResult(False, "L'ouverture de fichiers n'est disponible que sous Windows.")
    except OSError as e:
        return ToolResult(False, f"Windows n'a pas pu ouvrir « {p.name} » ({e}).")
    return ToolResult(True, f"J'ai ouvert « {p.name} ».")


def _read_for_ai(ctx, a):
    p = ctx.resolve_path(_s(a, "path"))
    if not fsearch.can_read_content(p):
        raise ToolError("Je sais lire les fichiers texte, PDF et Word (.docx) uniquement.")
    text = fsearch.extract_text(p, max_chars=30_000)
    if not text.strip():
        raise ToolError("Je n'ai pas pu extraire de texte de ce fichier (scan, image, fichier protégé ?).")
    return p, text


def _confirm_summarize(ctx, a):
    p, text = _read_for_ai(ctx, a)
    return f"Envoyer le contenu de « {p.name} » ({len(text)} caractères) à Gemini (Google) pour l'analyser ?"


def t_summarize_file(ctx, a):
    p, text = _read_for_ai(ctx, a)
    return ToolResult(True, ctx.gemini.summarize(text, _s(a, "instruction")))


def _confirm_rename(ctx, a):
    p = ctx.resolve_path(_s(a, "path"))
    return f"Renommer « {p.name} » en « {_s(a, 'new_name')} » ?"


def t_rename_file(ctx, a):
    p = ctx.resolve_path(_s(a, "path"))
    try:
        new = manager.rename(p, _s(a, "new_name"))
    except (manager.FileError, OSError) as e:
        return ToolResult(False, str(e))
    return ToolResult(True, f"« {p.name} » est maintenant « {new.name} ».")


def _confirm_move(ctx, a):
    p = ctx.resolve_path(_s(a, "path"))
    d = ctx.resolve_folder(_s(a, "dest_folder"))
    return f"Déplacer « {p.name} » vers « {d} » ?"


def t_move_file(ctx, a):
    p = ctx.resolve_path(_s(a, "path"))
    d = ctx.resolve_folder(_s(a, "dest_folder"))
    try:
        new = manager.move(p, d)
    except (manager.FileError, OSError) as e:
        return ToolResult(False, str(e))
    return ToolResult(True, f"J'ai déplacé « {p.name} » vers « {new.parent} ».")


def _confirm_delete(ctx, a):
    p = ctx.resolve_path(_s(a, "path"))
    return f"Mettre « {p.name} » à la corbeille ?"


def t_delete_file(ctx, a):
    p = ctx.resolve_path(_s(a, "path"))
    try:
        manager.trash(p)
    except (manager.FileError, OSError) as e:
        return ToolResult(False, str(e))
    return ToolResult(True, f"« {p.name} » a été mis à la corbeille (tu peux le restaurer).")


def _confirm_classify(ctx, a):
    folder = ctx.resolve_folder(_s(a, "folder"))
    plan = manager.plan_classify(folder)
    if not plan:
        raise ToolError("Il n'y a rien à classer dans ce dossier.")
    detail = ", ".join(f"{len(v)} → {k}" for k, v in plan.items())
    return f"Classer les fichiers de « {folder} » dans des sous-dossiers ({detail}) ?"


def t_classify_files(ctx, a):
    folder = ctx.resolve_folder(_s(a, "folder"))
    plan = manager.plan_classify(folder)
    n = manager.apply_classify(folder, plan)
    return ToolResult(True, f"J'ai classé {n} fichier{'s' if n > 1 else ''} dans « {folder} ».")


def t_web_search(ctx, a):
    q = _s(a, "query")
    if not q:
        raise ToolError("Que dois-je chercher sur Internet ?")
    return ToolResult(True, ctx.gemini.search_answer(q))


def _confirm_computer(ctx, a):
    if ctx.screen_ok:
        return None
    return ("Polaris va regarder ton écran (captures envoyées à Gemini) et contrôler la souris et le clavier pour :\n"
            f"« {_s(a, 'goal')} »\n\nIl te demandera ton accord avant tout téléchargement, suppression ou paiement. "
            "Échap arrête tout. Autoriser pour cette session ?")


def t_computer_task(ctx, a):
    goal = _s(a, "goal")
    if not goal:
        raise ToolError("Quelle tâche dois-je faire à l'écran ?")
    ctx.screen_ok = True
    from ai import agent
    try:
        return agent.run(ctx, goal)
    except OSError as e:
        return ToolResult(False, str(e))


def _download_target(ctx, a):
    u = web.resolve_url(_s(a, "url"))
    if not u or not u.lower().startswith(("http://", "https://")):
        raise ToolError("Adresse de téléchargement non valide.")
    cands = folders_for_alias("telechargements")
    dest = cands[0] if cands else Path.home() / "Downloads"
    name = _s(a, "filename") or u.split("?")[0].rstrip("/").split("/")[-1] or "telechargement"
    name = "".join(c for c in name if c not in '\\/:*?"<>|')[:120] or "telechargement"
    return u, dest, name


def _confirm_download(ctx, a):
    u, dest, name = _download_target(ctx, a)
    warn = "\n⚠ C'est un programme exécutable : ne l'ouvre que si tu fais confiance à la source." \
        if Path(name).suffix.lower() in DANGEROUS_EXT else ""
    return f"Télécharger « {name} » depuis {u} dans « {dest} » ?{warn}"


def t_download_file(ctx, a):
    import urllib.request
    u, dest, name = _download_target(ctx, a)
    dest.mkdir(parents=True, exist_ok=True)
    target = manager.unique_target(dest, name)
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Polaris/1.0"})
        total = 0
        with urllib.request.urlopen(req, timeout=30) as r, open(target, "wb") as f:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                total += len(chunk)
                if total > 500 * 1024 * 1024:
                    raise ToolError("Fichier trop gros (limite 500 Mo).")
                f.write(chunk)
    except ToolError:
        target.unlink(missing_ok=True)
        raise
    except Exception as e:
        target.unlink(missing_ok=True)
        return ToolResult(False, f"Le téléchargement a échoué : {e}")
    return ToolResult(True, f"Téléchargé dans « {target} » ({fsearch.human_size(total)}).")


def t_time_now(ctx, a):
    n = datetime.now()
    text = f"Il est {n.hour} heures {n.minute:02d}, nous sommes {DAYS[n.weekday()]} {n.day} {MONTHS[n.month - 1]} {n.year}."
    return ToolResult(True, text)


def t_stop_speaking(ctx, a):
    ctx.stop_speaking()
    return ToolResult(True, "D'accord, je me tais.")


def t_mic_off(ctx, a):
    ctx.mic_off()
    return ToolResult(True, "J'ai coupé l'écoute du micro.")


@dataclass
class Tool:
    name: str
    category: str
    desc: str
    fn: Callable
    confirm: Optional[Callable] = None


TOOLS = {t.name: t for t in [
    Tool("open_app", "apps", 'open_app(name) : ouvre une application installée ("bloc-notes", "calculatrice", "spotify"...)', t_open_app),
    Tool("close_app", "apps", "close_app(name) : demande la fermeture d'une application ouverte", t_close_app),
    Tool("open_url", "web", 'open_url(url) : ouvre un site (nom connu comme "youtube" ou adresse http/https)', t_open_url),
    Tool("open_settings", "apps", 'open_settings(page) : paramètres Windows ("wifi", "bluetooth", "son", "affichage", "" = accueil)', t_open_settings),
    Tool("window_action", "apps", "window_action(action) : minimize_all | minimize | maximize | restore | close (fenêtre active)", t_window_action),
    Tool("search_files", "files_read", 'search_files(query, ext, content, folder) : cherche des fichiers. query = mots du nom ; ext = pdf|image|word|excel|powerpoint|python|texte|video|audio|archive ou ".ext" ; content = mot présent dans le fichier ; folder = bureau|documents|telechargements|images|videos|musique (vide = tous)', t_search_files),
    Tool("open_file", "files_read", 'open_file(path) : ouvre un fichier ("result:N" = Nième résultat de la dernière recherche)', t_open_file, _confirm_open),
    Tool("summarize_file", "files_read", "summarize_file(path, instruction) : lit un PDF/Word/texte et le résume ou répond à une consigne (demande confirmation avant envoi à Gemini)", t_summarize_file, _confirm_summarize),
    Tool("rename_file", "files_modify", "rename_file(path, new_name) : renomme un fichier", t_rename_file),
    Tool("move_file", "files_modify", "move_file(path, dest_folder) : déplace un fichier vers un dossier autorisé", t_move_file),
    Tool("delete_file", "files_modify", "delete_file(path) : met un fichier à la corbeille", t_delete_file, _confirm_delete),
    Tool("classify_files", "files_modify", "classify_files(folder) : range les fichiers d'un dossier dans des sous-dossiers par type", t_classify_files),
    Tool("computer_task", "control", "computer_task(goal) : prend le contrôle de la souris et du clavier pour accomplir une tâche à l'écran (naviguer sur un site, cliquer, remplir un formulaire, utiliser un programme). goal = la tâche complète en une phrase. Demande l'accord avant tout téléchargement, suppression ou paiement", t_computer_task, _confirm_computer),
    Tool("download_file", "web", "download_file(url, filename) : télécharge un fichier dans Téléchargements (demande toujours confirmation)", t_download_file, _confirm_download),
    Tool("web_search", "web", "web_search(query) : recherche sur Internet et répond avec des sources", t_web_search),
    Tool("time_now", "apps", "time_now() : heure et date actuelles", t_time_now),
    Tool("stop_speaking", "apps", "stop_speaking() : arrête la voix de Polaris", t_stop_speaking),
    Tool("mic_off", "apps", "mic_off() : coupe l'écoute du micro", t_mic_off),
]}


def describe_tools() -> str:
    return "\n".join("- " + t.desc for t in TOOLS.values())
