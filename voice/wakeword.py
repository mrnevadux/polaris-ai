"""Détection du mot de réveil dans un texte déjà reconnu localement par Vosk."""
import difflib

from core.textutil import normalize

TARGET = "polaris"
THRESHOLDS = {"low": 0.85, "normal": 0.78, "high": 0.70}


def find_wake(text: str, sensitivity: str = "normal"):
    """Retourne (trouvé, reste de la phrase après le mot de réveil)."""
    thr = THRESHOLDS.get(sensitivity, 0.78)
    orig = (text or "").split()
    norm = [normalize(t).replace(" ", "") for t in orig]
    for i in range(len(orig)):
        for n in (1, 2, 3):
            if i + n > len(orig):
                break
            cand = "".join(norm[i:i + n])
            if not cand or abs(len(cand) - len(TARGET)) > 3:
                continue
            if difflib.SequenceMatcher(None, cand, TARGET).ratio() >= thr:
                return True, " ".join(orig[i + n:]).strip()
    return False, ""
