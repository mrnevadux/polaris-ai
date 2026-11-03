"""Chef d'orchestre : reçoit les demandes (texte ou voix), choisit local / Gemini, exécute les outils."""
import queue
import threading
from collections import deque

from ai.gemini_client import GeminiClient, GeminiError
from core import executor, logger, router
from core.textutil import normalize
from core.tools import ToolContext, describe_tools
from security.permissions import Permissions
from voice.listener import VoiceListener
from voice.tts import TTS

OFFLINE_HELP = ("Je n'ai pas compris cette demande en mode local. Avec Internet et une clé Gemini je comprends "
                "les demandes complexes ; en local je sais ouvrir/fermer des applications, chercher des fichiers, donner l'heure.")


class Assistant:
    def __init__(self, settings, ui):
        self.settings = settings
        self.ui = ui
        self.perms = Permissions(settings)
        self.gemini = GeminiClient(settings)
        self.tts = TTS(settings, on_warning=lambda m: self.ui.add_message("system", m))
        self.listener = None
        self.history = deque(maxlen=8)
        self.cancel = threading.Event()
        self.ctx = ToolContext(settings=settings, perms=self.perms, gemini=self.gemini, confirm=ui.confirm,
                               stop_speaking=self.tts.stop, mic_off=self.stop_voice, ui=ui, cancel=self.cancel)
        self._q = queue.Queue()
        self._worker = threading.Thread(target=self._loop, name="polaris-worker", daemon=True)
        self._worker.start()

    # ---------- état Gemini ----------
    def announce_gemini_state(self):
        self.ui.set_gemini_state("ready" if self.gemini.has_key() else "nokey")

    # ---------- voix ----------
    def start_voice(self):
        if self.listener and self.listener.running:
            return
        self.listener = VoiceListener(
            self.settings, on_command=lambda t: self.submit(t, "voice"),
            on_state=self.ui.set_voice_state,
            on_error=lambda m: self.ui.add_message("system", m),
            on_wake=self._on_wake, on_level=self.ui.set_level, is_muted=lambda: self.tts.speaking)
        self.listener.start()

    def _on_wake(self):
        try:
            import winsound
            winsound.Beep(1100, 90)
        except Exception:
            pass
        self.ui.wake_up()

    def stop_voice(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
        self.ui.set_voice_state("off")

    def toggle_voice(self):
        if self.listener and self.listener.running:
            self.stop_voice()
        else:
            self.start_voice()

    def emergency_stop(self):
        """Coupe immédiatement le micro, la voix et la file d'attente."""
        self.cancel.set()           # interrompt aussi une tâche d'écran en cours
        self.stop_voice()
        self.tts.stop()
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        self.ui.add_message("system", "Écoute arrêtée. Le micro est libéré.")

    def shutdown(self):
        self.stop_voice()
        self.tts.shutdown()

    # ---------- traitement ----------
    def submit(self, text: str, source: str = "text"):
        if text and text.strip():
            self._q.put((text.strip(), source))

    def _loop(self):
        while True:
            text, source = self._q.get()
            try:
                self._handle(text, source)
            except Exception as e:
                logger.get().exception("Erreur de traitement")
                self.ui.add_message("polaris", f"Erreur interne : {e}")
            finally:
                self.ui.set_busy(False)

    def _handle(self, text: str, source: str):
        self.cancel.clear()
        self.ui.add_message("user", text, source)
        self.ui.set_busy(True)
        reply, speak = self._process(text)
        self.history.append(("user", text))
        self.history.append(("polaris", reply[:300]))
        self.ui.add_message("polaris", reply)
        if source == "voice" or self.settings.get("speak_text_replies"):
            self.tts.say(speak or reply)

    def _process(self, text: str):
        calls = router.parse(text)
        if calls:
            return self._run_calls(calls)
        if not self.gemini.has_key():
            self.ui.set_gemini_state("nokey")
            return ("Je ne comprends pas encore cette demande en mode local. Ajoute ta clé API Gemini dans Paramètres "
                    "pour que je puisse répondre aux questions et comprendre le français naturel.", None)
        try:
            ctx_line = ""
            if self.ctx.last_results:
                names = "; ".join(f"{i}. {r.name}" for i, r in enumerate(self.ctx.last_results[:10], 1))
                ctx_line = f"Résultats de la dernière recherche de fichiers : {names}"
            plan = self.gemini.plan(text, list(self.history), ctx_line, describe_tools())
            self.ui.set_gemini_state("ok")
        except GeminiError as e:
            self.ui.set_gemini_state(e.kind)
            return (e.user_message + ("" if e.kind != "offline" else " " + OFFLINE_HELP), None)
        if plan["calls"]:
            return self._run_calls([(c["tool"], c["args"]) for c in plan["calls"]])
        return (plan["say"] or "Je n'ai pas de réponse à cette demande.", None)

    def _run_calls(self, calls):
        texts, speaks = [], []
        for tool, args in calls:
            try:
                res = executor.run_call(self.ctx, tool, args)
                if tool in ("web_search", "summarize_file"):
                    self.ui.set_gemini_state("ok")
            except GeminiError as e:
                self.ui.set_gemini_state(e.kind)
                res = type("R", (), {"text": e.user_message, "speak": None, "ok": False})()
            texts.append(res.text)
            speaks.append(res.speak or res.text)
            if not res.ok and tool not in ("close_app",):
                break  # on n'enchaîne pas après un échec
        return "\n".join(texts), " ".join(speaks)
