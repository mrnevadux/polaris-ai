import re
import unicodedata


def normalize(s: str) -> str:
    """Minuscules, sans accents, ponctuation simplifiée (conserve les points pour les domaines)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", " ").replace("'", " ").replace("-", " ")
    s = re.sub(r"[^\w\s.]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_for_speech(text: str, limit: int = 450) -> str:
    text = re.sub(r"```.*?```", " (le code est affiché à l'écran) ", text or "", flags=re.S)
    text = re.sub(r"https?://\S+", " lien ", text)
    text = re.sub(r"[*_`#>|~]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        cut = text[:limit]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        text = (cut[: end + 1] if end > 120 else cut) + " La suite est affichée à l'écran."
    return text
