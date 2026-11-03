"""Paramètres de Polaris (fichier JSON à côté de l'exécutable, application portable)."""
import copy
import json
import os
import sys
import threading
from datetime import date
from pathlib import Path

DEFAULTS = {
    "settings_version": 2,
    "gemini_model": "auto",          # "auto" = Polaris choisit le meilleur modèle Flash disponible
    "resolved_model": "",
    "api_key_enc": "",
    "economy_mode": False,
    "voice_on_start": True,
    "start_hidden": True,            # démarre réduit et se réveille avec « Hey Polaris »
    "auto_sleep_s": 25,              # se rendort (se réduit) après ce délai d'inactivité
    "speak_text_replies": False,
    "tts_enabled": True,
    "tts_rate": 1,
    "wake_sensitivity": "normal",   # low | normal | high
    "save_history": False,
    "extra_folders": [],
    "mic_device": None,
    "perm_apps": True,
    "perm_web": True,
    "perm_files_read": True,
    "perm_files_modify": True,
    "perm_control": True,            # souris / clavier / écran
    "min_request_interval": 1.0,
    "requests_log": ["", 0],
    "profile": {"first_name": "", "last_name": "", "nickname": "", "age": "", "address_form": "tu",
                "style": "court", "interests": "", "about": "", "assistant_name": "Polaris"},
}
RETIRED_MODELS = {"gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite", "gemini-2.0-flash",
                  "gemini-2.0-flash-001", "gemini-2.0-flash-lite", "gemini-2.0-flash-lite-001"}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(rel: str) -> Path:
    """Chemin d'une ressource embarquée (PyInstaller) ou du dossier du projet."""
    base = Path(getattr(sys, "_MEIPASS", app_dir()))
    return base / rel


def data_dir() -> Path:
    for base in (app_dir(), Path.home()):
        try:
            d = base / "Polaris_data"
            d.mkdir(parents=True, exist_ok=True)
            probe = d / ".w"
            probe.write_text("1")
            probe.unlink()
            return d
        except OSError:
            continue
    raise RuntimeError("Impossible de créer le dossier de données de Polaris.")


class Settings:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULTS)
        self._load()

    def _load(self):
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update({k: v for k, v in loaded.items() if k in DEFAULTS})
                if not isinstance(self.data.get("profile"), dict):
                    self.data["profile"] = copy.deepcopy(DEFAULTS["profile"])
                else:
                    merged = copy.deepcopy(DEFAULTS["profile"])
                    merged.update(self.data["profile"])
                    self.data["profile"] = merged
                if int(loaded.get("settings_version", 1)) < 2:   # migration : anciens réglages
                    self.data.update(settings_version=2, gemini_model="auto", resolved_model="", voice_on_start=True)
        except (OSError, ValueError):
            pass
        if str(self.data.get("gemini_model", "")).strip() in RETIRED_MODELS:
            self.data["gemini_model"], self.data["resolved_model"] = "auto", ""

    def save(self):
        with self._lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)

    def get(self, key, default=None):
        with self._lock:
            return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value, save=True):
        with self._lock:
            self.data[key] = value
            if save:
                self.save()

    # --- clé API (chiffrée avec Windows DPAPI, jamais en clair, jamais dans le dépôt) ---
    def set_api_key(self, key: str):
        from security import secrets
        key = (key or "").strip()
        self.set("api_key_enc", secrets.protect(key) if key else "")

    def get_api_key(self) -> str:
        enc = self.get("api_key_enc", "")
        if enc:
            try:
                from security import secrets
                return secrets.unprotect(enc)
            except Exception:
                return ""
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""

    def count_request(self) -> int:
        today = date.today().isoformat()
        with self._lock:
            d, n = (self.get("requests_log") or ["", 0])[:2]
            n = (n + 1) if d == today else 1
            self.set("requests_log", [today, n])
            return n

    def requests_today(self) -> int:
        d, n = (self.get("requests_log") or ["", 0])[:2]
        return n if d == date.today().isoformat() else 0
