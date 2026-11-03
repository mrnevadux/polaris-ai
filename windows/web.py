import re
import webbrowser

from core.textutil import normalize

KNOWN_SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "wikipedia": "https://fr.wikipedia.org",
    "github": "https://github.com",
    "netflix": "https://www.netflix.com",
    "twitch": "https://www.twitch.tv",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
    "amazon": "https://www.amazon.fr",
    "gemini": "https://gemini.google.com",
    "claude": "https://claude.ai",
    "chatgpt": "https://chatgpt.com",
    "maps": "https://www.google.com/maps",
    "google maps": "https://www.google.com/maps",
    "drive": "https://drive.google.com",
}


def resolve_url(text: str):
    """Retourne une URL http(s) sûre ou None."""
    t = re.sub(r"^(?:le\s+)?(?:site(?:\s+web)?\s+)", "", (text or "").strip(), flags=re.I)
    n = normalize(t)
    if n in KNOWN_SITES:
        return KNOWN_SITES[n]
    cand = t.strip().strip("<>\"'")
    if re.match(r"^https?://[^\s]+$", cand, re.I):
        return cand
    if re.match(r"^(?:[\w-]+\.)+[a-z]{2,}(?:/[^\s]*)?$", cand, re.I):
        return "https://" + cand
    return None


def open_url(url: str):
    webbrowser.open(url, new=2)
