"""Synthèse vocale via SAPI5 (voix Windows), dans un thread dédié créé à la première utilisation."""
import queue
import threading
import time

from core import logger
from core.textutil import clean_for_speech


class TTS:
    def __init__(self, settings, on_warning=None):
        self.settings = settings
        self.on_warning = on_warning
        self._q = queue.Queue()
        self._thread = None
        self._stop = threading.Event()
        self._speaking = False
        self._mute_until = 0.0
        self._failed = False

    @property
    def speaking(self) -> bool:
        return self._speaking or time.monotonic() < self._mute_until

    def say(self, text: str):
        if self._failed or not self.settings.get("tts_enabled", True):
            return
        text = clean_for_speech(text)
        if not text:
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="polaris-tts", daemon=True)
            self._thread.start()
        self._q.put(text)

    def stop(self):
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        if self._speaking:
            self._stop.set()

    def shutdown(self):
        self.stop()
        self._q.put(None)

    @staticmethod
    def _pick_french(voice) -> bool:
        voices = voice.GetVoices()
        for i in range(voices.Count):
            v = voices.Item(i)
            try:
                lang = int(v.GetAttribute("Language").split(";")[0], 16) & 0x3FF
                if lang == 0x0C:  # français
                    voice.Voice = v
                    return True
            except Exception:
                pass
            if any(k in v.GetDescription().lower() for k in ("french", "français", "francais", "hortense")):
                voice.Voice = v
                return True
        return False

    def _run(self):
        try:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            if not self._pick_french(voice) and self.on_warning:
                self.on_warning("Aucune voix française Windows trouvée : j'utilise la voix par défaut. "
                                "Ajoute le français dans Paramètres Windows > Heure et langue > Voix.")
        except Exception as e:
            self._failed = True
            logger.get().error("TTS indisponible : %s", e)
            if self.on_warning:
                self.on_warning("La synthèse vocale n'est pas disponible sur ce PC (les réponses restent affichées).")
            return
        while True:
            text = self._q.get()
            if text is None:
                break
            self._stop.clear()
            self._speaking = True
            try:
                voice.Rate = int(self.settings.get("tts_rate", 1))
                voice.Volume = 100
                voice.Speak(text, 1)  # asynchrone, pour pouvoir interrompre
                while not voice.WaitUntilDone(100):
                    if self._stop.is_set():
                        voice.Speak("", 3)  # asynchrone + purge
                        break
            except Exception as e:
                logger.get().error("Erreur TTS : %s", e)
            finally:
                self._speaking = False
                self._mute_until = time.monotonic() + 0.6
