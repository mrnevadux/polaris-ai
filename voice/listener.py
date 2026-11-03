"""Écoute micro 100 % locale : Vosk (français) détecte « Polaris » puis transcrit la demande.
Aucun son n'est enregistré sur disque ni envoyé sur Internet : seul le TEXTE de la demande
peut ensuite être envoyé à Gemini. Pour économiser le processeur, la reconnaissance ne tourne
que lorsqu'il y a du son (silence = rien n'est analysé). Le micro est libéré dès l'arrêt."""
import json
import queue
import threading
import time
from array import array
from pathlib import Path

from config.settings import resource_path
from core import logger
from voice.wakeword import find_wake

RATE = 16000
BLOCK = 4000          # 0,25 s d'audio par bloc
COMMAND_WAIT = 8.0    # secondes d'attente de la demande après « Polaris »
COMMAND_MAX = 25.0
GATE_HANG = 1.6       # secondes de reconnaissance après le dernier son


class VoiceListener:
    def __init__(self, settings, on_command, on_state, on_error, on_wake=None, on_level=None, is_muted=lambda: False):
        self.settings = settings
        self.on_command = on_command
        self.on_state = on_state
        self.on_error = on_error
        self.on_wake = on_wake
        self.on_level = on_level
        self.is_muted = is_muted
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="polaris-voice", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        t = self._thread
        if t and t is not threading.current_thread():
            t.join(timeout=2.5)
        self._thread = None

    @staticmethod
    def model_path() -> Path:
        return resource_path("model")

    def _emit(self, text: str):
        text = (text or "").strip()
        if text:
            try:
                self.on_command(text)
            except Exception as e:
                logger.get().error("Erreur commande : %s", e)

    def _woke(self):
        if self.on_wake:
            try:
                self.on_wake()
            except Exception as e:
                logger.get().error("Erreur réveil : %s", e)

    def _run(self):
        model = rec = None
        try:
            mp = self.model_path()
            if not (mp / "am").exists():
                self.on_error("Modèle vocal français introuvable (dossier « model »).")
                return
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model, SetLogLevel
            SetLogLevel(-1)
            model = Model(str(mp))
            rec = KaldiRecognizer(model, RATE)
            audio_q = queue.Queue(maxsize=60)
            eco = bool(self.settings.get("economy_mode"))

            def cb(indata, frames, t, status):
                try:
                    audio_q.put_nowait(bytes(indata))
                except queue.Full:
                    pass

            st = {"mode": "wake", "deadline": 0.0, "cmd_start": 0.0, "feeding": False, "last_loud": 0.0,
                  "noise": 200.0, "muted": False}

            def handle_wake_text(text, now):
                found, rest = find_wake(text, self.settings.get("wake_sensitivity", "normal"))
                if not found:
                    return
                self._woke()
                if rest:
                    self._emit(rest)
                else:
                    st.update(mode="command", cmd_start=now, deadline=now + COMMAND_WAIT)
                    self.on_state("recording")
                    rec.Reset()

            with sd.RawInputStream(samplerate=RATE, blocksize=BLOCK, dtype="int16", channels=1,
                                   callback=cb, device=self.settings.get("mic_device")):
                self.on_state("wake")
                while not self._stop.is_set():
                    try:
                        data = audio_q.get(timeout=0.3)
                    except queue.Empty:
                        continue
                    now = time.monotonic()
                    if self.is_muted():  # Polaris parle : on ignore le son pour ne pas s'entendre
                        rec.Reset()
                        st["muted"], st["feeding"] = True, False
                        if st["mode"] == "command":
                            st["deadline"] = now + COMMAND_WAIT
                        continue
                    if st["muted"]:
                        st["muted"] = False
                        rec.Reset()
                    a = array("h")
                    a.frombytes(data)
                    peak = max(max(a), -min(a))
                    if self.on_level and not eco:
                        self.on_level(min(1.0, peak / 12000.0))
                    # bruit de fond estimé -> seuil de détection de parole
                    st["noise"] = peak if peak < st["noise"] else st["noise"] * 1.002 + 0.2
                    loud = peak > max(300.0, st["noise"] * 3.0)
                    if loud:
                        st["last_loud"] = now

                    if st["mode"] == "wake":
                        if not (loud or now - st["last_loud"] < GATE_HANG):
                            if st["feeding"]:           # le son s'est arrêté : on finalise puis on dort
                                st["feeding"] = False
                                handle_wake_text(json.loads(rec.FinalResult()).get("text", ""), now)
                                rec.Reset()
                            continue                    # silence : aucun calcul de reconnaissance
                        st["feeding"] = True
                        if rec.AcceptWaveform(data):
                            handle_wake_text(json.loads(rec.Result()).get("text", ""), now)
                    else:
                        if rec.AcceptWaveform(data):
                            text = json.loads(rec.Result()).get("text", "")
                            st.update(mode="wake", feeding=False)
                            self.on_state("wake")
                            rec.Reset()
                            self._emit(text)
                        else:
                            if json.loads(rec.PartialResult()).get("partial"):
                                st["deadline"] = max(st["deadline"], min(now + 4.0, st["cmd_start"] + COMMAND_MAX))
                            if now > st["deadline"]:
                                st.update(mode="wake", feeding=False)
                                self.on_state("wake")
                                rec.Reset()
        except Exception as e:
            logger.get().error("Erreur écoute : %s", e)
            self.on_error(f"Micro ou reconnaissance vocale indisponible : {e}")
        finally:
            rec = None
            model = None  # libère la mémoire du modèle
            self.on_state("off")
