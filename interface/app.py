import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import psutil
from PIL import Image

from config.settings import resource_path
from core import logger
from core.assistant import Assistant
from interface.pages import ActivityPage, ChatPage, HelpPage, HomePage, ProfilePage, SettingsPage, _font
from interface.theme import *  # noqa: F401,F403

GEMINI_STATES = {
    "nokey": ("Gemini : clé manquante", ORANGE), "ready": ("Gemini : prêt", CYAN), "ok": ("Gemini : connecté", GREEN),
    "quota": ("Gemini : quota atteint", ORANGE), "auth": ("Gemini : clé refusée", RED),
    "offline": ("Gemini : hors ligne", ORANGE), "model": ("Gemini : modèle introuvable", ORANGE),
    "bad": ("Gemini : requête refusée", ORANGE), "error": ("Gemini : erreur", RED),
}
VOICE_STATES = {"off": ("Micro coupé", DIM), "wake": ("Veille « Hey Polaris »", CYAN), "recording": ("Je t'écoute…", GREEN)}
NAV = [("home", "Accueil"), ("chat", "Conversation"), ("profile", "Profil"),
       ("activity", "Activité"), ("settings", "Paramètres"), ("help", "Aide")]


class PolarisApp(ctk.CTk):
    def __init__(self, settings):
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.settings = settings
        self.title("POLARIS")
        self.geometry("1060x700")
        self.minsize(900, 600)
        self.configure(fg_color=BG)
        self.after(300, self._set_icon)
        self._uiq = queue.Queue()
        self.voice_state, self._busy, self.agent_mode = "off", False, False
        self._level = self._target = 0.0
        self._auto_hide, self._sleep_job = False, None
        self._proc = psutil.Process()
        self._proc.cpu_percent(None)
        self._build()
        self.assistant = Assistant(settings, self)
        self._build_pages()
        self.assistant.announce_gemini_state()
        self.pages["chat"].load_history()
        self.show_page("home")
        self.bind_all("<Button-1>", self._user_input, add="+")
        self.bind_all("<Key>", self._user_input, add="+")
        self.after(100, self._pump)
        self.after(1000, self._update_stats)
        self.after(60, self._animate)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._startup()

    # ------------------------------------------------------------------ démarrage
    def _startup(self):
        has_key = self.assistant.gemini.has_key()
        prof = self.settings.get("profile") or {}
        if not has_key:
            self.add_message("system", "Bienvenue ! Pour commencer, ouvre « Paramètres » et colle ta clé API Gemini.")
            self.show_page("settings")
        elif not (prof.get("first_name") or prof.get("nickname")):
            self.add_message("system", "Bonjour, je suis Polaris. Va dans « Profil » pour te présenter (prénom, âge…) : je m'adapterai à toi.")
        else:
            self.add_message("system", "Je suis prêt. Dis « Hey Polaris » quand tu as besoin de moi.")
        if self.settings.get("voice_on_start"):
            self.after(700, self.assistant.start_voice)
        if has_key and self.settings.get("voice_on_start") and self.settings.get("start_hidden"):
            self.after(2500, self.iconify)   # démarre réduit : « Hey Polaris » le réveille

    def _set_icon(self):
        try:
            self.iconbitmap(str(resource_path("assets/polaris.ico")))
        except Exception:
            pass

    # ------------------------------------------------------------------ construction
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        side = ctk.CTkFrame(self, width=230, fg_color=PANEL, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        try:
            img = Image.open(resource_path("assets/logo.png"))
            self._logo = ctk.CTkImage(light_image=img, dark_image=img, size=(150, 147))
            ctk.CTkLabel(side, image=self._logo, text="", corner_radius=14).pack(pady=(18, 6))
        except Exception:
            ctk.CTkLabel(side, text="POLARIS", font=_font(26, "bold", True), text_color=CYAN).pack(pady=(24, 6))
        self.lbl_mic = ctk.CTkLabel(side, text="", anchor="w", font=_font(13))
        self.lbl_mic.pack(fill="x", padx=20, pady=(8, 2))
        self.lbl_gem = ctk.CTkLabel(side, text="", anchor="w", font=_font(13))
        self.lbl_gem.pack(fill="x", padx=20, pady=2)
        self.nav_btns = {}
        for key, label in NAV:
            b = ctk.CTkButton(side, text=label, anchor="w", height=38, corner_radius=10, fg_color="transparent",
                              hover_color=PANEL2, text_color=TEXT, font=_font(14, "bold", True),
                              command=lambda k=key: self.show_page(k))
            b.pack(fill="x", padx=14, pady=2)
            self.nav_btns[key] = b
        self.lbl_stats = ctk.CTkLabel(side, text="", text_color=DIM, font=_font(11))
        self.lbl_stats.pack(side="bottom", pady=(0, 12))
        self.lbl_eco = ctk.CTkLabel(side, text="", text_color=DIM, font=_font(11))
        self.lbl_eco.pack(side="bottom")
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self.set_voice_state("off", now=True)
        self.set_gemini_state("ready", now=True)
        self.apply_economy()

    def _build_pages(self):
        classes = {"home": HomePage, "chat": ChatPage, "profile": ProfilePage,
                   "activity": ActivityPage, "settings": SettingsPage, "help": HelpPage}
        self.pages = {}
        for key, cls in classes.items():
            p = cls(self.content, self)
            p.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = p
        self.current = "home"

    def show_page(self, key):
        self.current = key
        self.pages[key].tkraise()
        for k, b in self.nav_btns.items():
            b.configure(fg_color=DEEP if k == key else "transparent")
        if hasattr(self.pages[key], "on_show"):
            self.pages[key].on_show()

    # ------------------------------------------------------------------ pont thread-safe
    def call_in_ui(self, fn):
        self._uiq.put(fn)

    def _pump(self):
        try:
            while True:
                fn = self._uiq.get_nowait()
                try:
                    fn()
                except Exception:
                    logger.get().exception("Erreur UI")
        except queue.Empty:
            pass
        self.after(250 if self.settings.get("economy_mode") else 100, self._pump)

    # API utilisée par l'assistant (appelable depuis n'importe quel thread)
    def add_message(self, role, text, source="text"):
        def f():
            self.pages["chat"].append(role, text, source)
            if role == "polaris":
                self.pages["home"].set_last(text)
                self._arm_sleep()
        self.call_in_ui(f)

    def set_voice_state(self, state, now=False):
        def f():
            self.voice_state = state
            txt, col = VOICE_STATES.get(state, VOICE_STATES["off"])
            self.lbl_mic.configure(text="●  " + txt, text_color=col)
            if hasattr(self, "pages"):
                self.pages["home"].btn_mic.configure(text="Couper le micro" if state != "off" else "Activer le micro",
                                                     fg_color=DEEP if state != "off" else BLUE)
        f() if now else self.call_in_ui(f)

    def set_gemini_state(self, state, now=False):
        def f():
            txt, col = GEMINI_STATES.get(state, GEMINI_STATES["error"])
            self.lbl_gem.configure(text="●  " + txt, text_color=col)
        f() if now else self.call_in_ui(f)

    def set_busy(self, busy):
        self._busy = busy

    def set_level(self, lvl):
        self._target = max(self._target, lvl)

    def confirm(self, message):
        ev, box = threading.Event(), {"r": False}

        def ask():
            self.state("normal")
            self.deiconify()
            self.lift()
            box["r"] = messagebox.askyesno("Polaris — autorisation demandée", message, icon="question", parent=self)
            if self.agent_mode:
                self.iconify()
            ev.set()
        self.call_in_ui(ask)
        return box["r"] if ev.wait(180) else False

    def clear_history(self):
        self.pages["chat"].clear()

    # ------------------------------------------------------------------ réveil / veille
    def wake_up(self):
        def f():
            self._auto_hide = True
            if self.state() == "iconic":
                self.state("normal")
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(500, lambda: self.attributes("-topmost", False))
            self.show_page("home")
            self._arm_sleep()
        self.call_in_ui(f)

    def set_agent_mode(self, on):
        def f():
            self.agent_mode = on
            if on:
                self.iconify()                      # on libère l'écran pour la tâche
            else:
                self.state("normal")
                self.deiconify()
                self.lift()
                self._arm_sleep()
        self.call_in_ui(f)

    def _user_input(self, _e=None):
        self._auto_hide = False                      # tu as pris la main : je ne me réduis plus tout seul

    def _arm_sleep(self):
        if self._sleep_job:
            self.after_cancel(self._sleep_job)
            self._sleep_job = None
        sec = int(self.settings.get("auto_sleep_s") or 0)
        if sec > 0 and self._auto_hide:
            self._sleep_job = self.after(sec * 1000, self._maybe_sleep)

    def _maybe_sleep(self):
        self._sleep_job = None
        if not self._auto_hide:
            return
        if self._busy or self.agent_mode or self.assistant.tts.speaking or self.voice_state == "recording":
            self._arm_sleep()
            return
        self._auto_hide = False
        self.iconify()

    def apply_economy(self):
        eco = bool(self.settings.get("economy_mode"))
        self.lbl_eco.configure(text="Mode économie : activé" if eco else "")

    # ------------------------------------------------------------------ animation et mesures
    def _animate(self):
        ms = 600
        try:
            if self.state() != "iconic":
                ms = 200 if self.settings.get("economy_mode") else 45
                if self.current == "home":
                    self.pages["home"].draw()
        except Exception:
            pass
        self.after(ms, self._animate)

    def _update_stats(self):
        ms = 5000 if self.settings.get("economy_mode") else 2000
        try:
            if self.state() != "iconic":
                mem = self._proc.memory_info().rss / 1048576
                cpu = self._proc.cpu_percent(None) / (psutil.cpu_count() or 1)
                self.lbl_stats.configure(text=f"RAM {mem:.0f} Mo  •  CPU {cpu:.1f} %")
            else:
                ms = 10000
        except Exception:
            pass
        self.after(ms, self._update_stats)

    def _on_close(self):
        try:
            self.assistant.shutdown()
        finally:
            self.destroy()
