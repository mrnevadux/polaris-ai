"""Commandes locales (sans Internet, sans Gemini). Retourne [(outil, args)] ou None."""
import re

from core.textutil import normalize
from windows.apps import strip_articles
from windows.web import KNOWN_SITES

OPEN = r"(?:ouvre|ouvrir|lance|lancer|demarre|demarrer|affiche|afficher)"
CLOSE = r"(?:ferme|fermer|quitte|quitter)"
POLITE = r"^(?:polaris\s+)?(?:s il te plait\s+)?(?:peux tu|pouvez vous|tu peux|pourrais tu)?\s*"
DEFER_WORDS = {"fichier", "fichiers", "document", "documents", "pdf", "image", "images", "photo", "photos",
               "dossier", "dossiers", "video", "videos", "musique", "telechargement", "telechargements"}
ORD = {"premier": 1, "1er": 1, "premiere": 1, "deuxieme": 2, "2eme": 2, "2e": 2, "second": 2, "troisieme": 3,
       "3eme": 3, "3e": 3, "quatrieme": 4, "4eme": 4, "cinquieme": 5, "dernier": "last", "derniere": "last"}
EXT_WORDS = {"pdf": "pdf", "pdfs": "pdf", "image": "image", "images": "image", "photo": "image", "photos": "image",
             "python": "python", "word": "word", "excel": "excel", "tableur": "excel", "powerpoint": "powerpoint",
             "presentation": "powerpoint", "texte": "texte", "video": "video", "videos": "video",
             "musique": "audio", "musiques": "audio", "audio": "audio", "archive": "archive", "archives": "archive", "zip": "archive"}
FOLDER_RE = r"dans\s+(?:mes|mon|le|la|les|l)?\s*(telechargements?|downloads|documents|bureau|images|photos|videos|musique)"
FOLDER_MAP = {"telechargement": "telechargements", "telechargements": "telechargements", "downloads": "telechargements",
              "documents": "documents", "bureau": "bureau", "images": "images", "photos": "images",
              "videos": "videos", "musique": "musique"}
STOP = {"le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "mon", "ma", "mes", "ton", "tous", "toutes", "tout",
        "fichier", "fichiers", "document", "documents", "dossier", "dossiers", "sur", "concernant", "a", "propos", "pour",
        "qui", "que", "nomme", "nommes", "appele", "appeles", "s", "il", "te", "plait", "moi", "dans", "cherche", "trouve",
        "recherche", "retrouve", "liste", "montre", "peux", "tu", "pouvez", "vous", "polaris", "et", "ou", "au", "aux",
        "contenant", "avec", "mot", "mots", "mes", "ordinateur", "pc"} | set(EXT_WORDS)


def parse(text: str):
    n = normalize(text)
    if not n:
        return None
    n = re.sub(r"^(?:hey |he |ok |et )?polaris\s+", "", n)

    if n in ("stop", "tais toi", "silence", "arrete", "arrete toi", "ca suffit", "tais toi polaris"):
        return [("stop_speaking", {})]
    if re.search(r"\b(arrete|coupe|desactive|eteins|stop)\b.*\b(ecout\w*|micro|microphone)\b", n):
        return [("mic_off", {})]
    if re.search(r"\bquelle (?:heure|date)\b|\bquel jour\b|\bheure est il\b", n):
        return [("time_now", {})]

    # « ouvre le premier résultat »
    m = re.match(POLITE + OPEN + r"\s+(?:le |la |l )?(?:(premier|1er|premiere|deuxieme|2eme|2e|second|troisieme|3eme|3e|quatrieme|4eme|cinquieme|dernier|derniere)"
                 r"|(?:resultat|fichier|numero)\s+(\d+))\s*(?:resultat|fichier|document)?$", n)
    if m:
        key = ORD.get(m.group(1)) if m.group(1) else int(m.group(2))
        return [("open_file", {"path": f"result:{key}"})]

    # fenêtres
    if re.search(r"\b(minimise|reduis|reduire|cache)\b.*\b(tout|toutes|fenetres|bureau)\b|\baffiche le bureau\b", n):
        return [("window_action", {"action": "minimize_all"})]
    m = re.match(POLITE + r"(minimise|reduis|maximise|agrandis|restaure|ferme)\s+(?:la |cette )?fenetre", n)
    if m:
        act = {"minimise": "minimize", "reduis": "minimize", "maximise": "maximize", "agrandis": "maximize",
               "restaure": "restore", "ferme": "close"}[m.group(1)]
        return [("window_action", {"action": act})]

    m = re.match(POLITE + OPEN + r"\s+(.+)$", n)
    if m:
        target = m.group(1)
        toks = set(target.split())
        if toks & DEFER_WORDS:
            return None
        t = strip_articles(target)
        if not t:
            return None
        if t.startswith("site ") or t in KNOWN_SITES or t.removeprefix("site ") in KNOWN_SITES \
                or re.match(r"^(?:[\w-]+\.)+[a-z]{2,}(?:/\S*)?$", t):
            return [("open_url", {"url": t})]
        if re.match(r"^(parametres?|reglages|settings)(?:\s+(.+))?$", t):
            page = re.sub(r"^(parametres?|reglages|settings)\s*(?:de\s+|du\s+|des\s+|windows\s*)?", "", t)
            return [("open_settings", {"page": page})]
        return [("open_app", {"name": t})]

    m = re.match(POLITE + CLOSE + r"\s+(.+)$", n)
    if m:
        t = strip_articles(m.group(1))
        if t and not (set(t.split()) & {"fenetre", "ecoute", "micro"}):
            return [("close_app", {"name": t})]

    return parse_file_search(n)


def parse_file_search(n: str):
    if not re.match(POLITE + r"(cherche|trouve|recherche|retrouve|liste|montre)\b", n):
        return None
    if re.search(r"\b(sur internet|sur google|sur le web|en ligne|sur youtube)\b", n):
        return None
    toks = set(n.split())
    if not (toks & (set(EXT_WORDS) | {"fichier", "fichiers", "document", "documents", "dossier", "contient"})) and "contient" not in n:
        return None

    content = ""
    m = re.search(r"contien\w*\s+(?:le mot |les mots |le terme |le texte |l expression )?(.+)$", n)
    if m:
        content = m.group(1).strip()
        n = n[:m.start()].strip()
    folder = ""
    m = re.search(FOLDER_RE, n)
    if m:
        folder = FOLDER_MAP[m.group(1)]
        n = (n[:m.start()] + " " + n[m.end():]).strip()
    ext = next((EXT_WORDS[t] for t in n.split() if t in EXT_WORDS), "")
    if re.search(r"\bfichiers? py\b", n):
        ext = "python"
    query = " ".join(t for t in n.split() if t not in STOP and t != "py")
    if not (query or ext or content):
        return None
    return [("search_files", {"query": query, "ext": ext, "content": content, "folder": folder})]
