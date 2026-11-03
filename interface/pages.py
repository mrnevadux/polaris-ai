"""Pages de l'interface : Accueil, Conversation, Profil, Activité, Paramètres, Aide."""
import json
import math
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from config.settings import data_dir, resource_path
from interface.theme import *  # noqa: F401,F403


def _font(size=14, weight="normal", head=False):
    return ctk.CTkFont(family=HEAD if head else BODY, size=size, weight=weight)


def _title(master, text):
    return ctk.CTkLabel(master, text=text, text_color=CYAN, font=_font(15, "bold", True), anchor="w")


# =============================================================== Accueil
class HomePage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.app = app
        self.cv = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self._badge_img = ImageTk.PhotoImage(self._make_badge())
        c = self.cv
        self.ring_out = c.create_oval(0, 0, 0, 0, outline="#0F2250", width=1)
        self.ring_dash = c.create_oval(0, 0, 0, 0, outline="#1B3C84", width=1, dash=(2, 7))
        self.ring_mid = c.create_oval(0, 0, 0, 0, outline=BLUE, width=2)
        self.arc1 = c.create_arc(0, 0, 0, 0, start=0, extent=70, style="arc", outline=CYAN, width=4)
        self.arc2 = c.create_arc(0, 0, 0, 0, start=180, extent=45, style="arc", outline=BLUE, width=3)
        self.glow = c.create_oval(0, 0, 0, 0, fill="#0B1C3D", outline="")
        self.img = c.create_image(0, 0, image=self._badge_img)
        self.title = c.create_text(0, 0, text="POLARIS", fill=CYAN, font=(HEAD, 30, "bold"))
        self.caption = c.create_text(0, 0, text="", fill=TEXT, font=(BODY, 16))
        self.last = c.create_text(0, 0, text="", fill=DIM, font=(BODY, 12), width=620, justify="center")
        self._col = None
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(pady=(0, 16))
        self.btn_mic = ctk.CTkButton(bar, text="Activer le micro", width=170, height=40, fg_color=BLUE,
                                     hover_color="#1C54B8", font=_font(14, "bold"),
                                     command=lambda: app.assistant.toggle_voice())
        self.btn_mic.pack(side="left", padx=6)
        ctk.CTkButton(bar, text="■  STOP", width=120, height=40, fg_color="#8A1C1C", hover_color=RED,
                      font=_font(14, "bold"), command=lambda: app.assistant.emergency_stop()).pack(side="left", padx=6)

    @staticmethod
    def _make_badge():
        S, K = 190, 4
        big = Image.new("RGBA", (S * K, S * K), (0, 0, 0, 0))
        ImageDraw.Draw(big).ellipse((0, 0, S * K - 1, S * K - 1), fill=(238, 245, 255, 255))
        im = big.resize((S, S), Image.LANCZOS)
        try:
            em = Image.open(resource_path("assets/emblem.png")).convert("RGBA").resize((152, 152), Image.LANCZOS)
            im.alpha_composite(em, (19, 19))
        except Exception:
            pass
        return im

    def set_last(self, text):
        t = (text or "").replace("\n", " ")
        self.cv.itemconfig(self.last, text=(t[:260] + "…") if len(t) > 260 else t)

    def draw(self):
        a = self.app
        c = self.cv
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 300)
        cx, cy = w / 2, h / 2 - 34
        t = time.monotonic()
        lvl = a._level
        a._level = max(a._target, a._level * 0.85)
        a._target *= 0.6
        st = a.voice_state
        if a.agent_mode:
            col, cap = ORANGE, "Je pilote ton PC…  (Échap ou STOP pour arrêter)"
        elif a._busy:
            col, cap = BLUE, "Je réfléchis…"
        elif st == "recording":
            col, cap = CYAN, "Je t'écoute…"
        elif st == "wake":
            col, cap = "#2F6BFF", "Dis  « Hey Polaris »"
        else:
            col, cap = "#33466F", "Micro coupé"
        if col != self._col:
            self._col = col
            c.itemconfig(self.arc1, outline=col)
            c.itemconfig(self.ring_mid, outline=col)
        c.itemconfig(self.caption, text=cap)
        pulse = lvl * 16 if st == "recording" else (6 * (0.5 + 0.5 * math.sin(t * 2)) if st == "wake" else 0)
        R = {"glow": 104, "mid": 118 + pulse, "arc1": 132, "arc2": 150, "dash": 148, "out": 176}
        speed = 150 if (a._busy or st == "recording" or a.agent_mode) else 40

        def oval(item, r):
            c.coords(item, cx - r, cy - r, cx + r, cy + r)
        oval(self.glow, R["glow"]); oval(self.ring_mid, R["mid"]); oval(self.ring_dash, R["dash"]); oval(self.ring_out, R["out"])
        oval(self.arc1, R["arc1"]); oval(self.arc2, R["arc2"])
        c.itemconfig(self.arc1, start=(t * speed) % 360)
        c.itemconfig(self.arc2, start=(-t * speed * 0.7) % 360)
        c.coords(self.img, cx, cy)
        c.coords(self.title, cx, cy + R["out"] + 26)
        c.coords(self.caption, cx, cy + R["out"] + 62)
        c.coords(self.last, cx, cy + R["out"] + 104)


# =============================================================== Conversation
class ChatPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.chat = ctk.CTkTextbox(self, fg_color=PANEL, text_color=TEXT, wrap="word", font=_font(14),
                                   border_width=1, border_color=DEEP, corner_radius=12)
        self.chat.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))
        self.chat.tag_config("user", foreground=CYAN)
        self.chat.tag_config("polaris", foreground="#7FA6FF")
        self.chat.tag_config("system", foreground=ORANGE)
        self.chat.tag_config("dim", foreground=DIM)
        self.chat.configure(state="disabled")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))
        row.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(row, placeholder_text="Écris ta demande à Polaris…", height=42, fg_color=PANEL,
                                  border_color=BLUE, corner_radius=21)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._send())
        ctk.CTkButton(row, text="Envoyer", width=100, height=42, corner_radius=21, fg_color=BLUE,
                      command=self._send).grid(row=0, column=1)

    def _send(self):
        t = self.entry.get().strip()
        if t:
            self.entry.delete(0, "end")
            self.app.assistant.submit(t, "text")

    def append(self, role, text, source="text", save=True):
        names = {"user": "Toi" + (" (voix)" if source == "voice" else ""), "polaris": "Polaris", "system": "Système"}
        stamp = datetime.now().strftime("%H:%M")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{names.get(role, role)}  ", role)
        self.chat.insert("end", f"{stamp}\n", "dim")
        self.chat.insert("end", f"{text}\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")
        if save and role in ("user", "polaris") and self.app.settings.get("save_history"):
            try:
                with open(data_dir() / "history.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"r": role, "t": text, "s": source, "d": stamp}, ensure_ascii=False) + "\n")
            except OSError:
                pass

    def load_history(self):
        if not self.app.settings.get("save_history"):
            return
        try:
            for ln in (data_dir() / "history.jsonl").read_text(encoding="utf-8").splitlines()[-40:]:
                d = json.loads(ln)
                self.append(d["r"], d["t"], d.get("s", "text"), save=False)
        except (OSError, ValueError, KeyError):
            pass

    def clear(self):
        try:
            (data_dir() / "history.jsonl").unlink(missing_ok=True)
        except OSError:
            pass
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")

    def on_show(self):
        self.entry.focus_set()


# =============================================================== Profil
STYLES = {"Court": "court", "Équilibré": "equilibre", "Détaillé": "detaille"}
FORMS = {"Tutoiement": "tu", "Vouvoiement": "vous"}


class ProfilePage(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.app = app
        p = app.settings.get("profile")
        _title(self, "Personnalisation").pack(fill="x", padx=18, pady=(16, 2))
        ctk.CTkLabel(self, text="Polaris utilise ces infos pour te parler comme tu veux. Elles restent dans le dossier Polaris_data "
                                "et sont envoyées à Gemini avec tes demandes.", text_color=DIM, anchor="w", justify="left",
                     wraplength=640).pack(fill="x", padx=18)
        self.e = {}
        for key, label in (("first_name", "Prénom"), ("last_name", "Nom"), ("nickname", "Surnom (comment Polaris t'appelle)"),
                           ("age", "Âge"), ("assistant_name", "Nom de ton assistant"), ("interests", "Centres d'intérêt")):
            ctk.CTkLabel(self, text=label, text_color=TEXT, anchor="w").pack(fill="x", padx=18, pady=(10, 0))
            ent = ctk.CTkEntry(self, fg_color=PANEL, border_color=DEEP)
            ent.insert(0, str(p.get(key, "")))
            ent.pack(fill="x", padx=18, pady=2)
            self.e[key] = ent
        ctk.CTkLabel(self, text="Façon de parler", text_color=TEXT, anchor="w").pack(fill="x", padx=18, pady=(12, 0))
        self.form = ctk.CTkSegmentedButton(self, values=list(FORMS), selected_color=BLUE)
        self.form.set(next(k for k, v in FORMS.items() if v == p.get("address_form", "tu")))
        self.form.pack(fill="x", padx=18, pady=2)
        ctk.CTkLabel(self, text="Longueur des réponses", text_color=TEXT, anchor="w").pack(fill="x", padx=18, pady=(12, 0))
        self.style = ctk.CTkSegmentedButton(self, values=list(STYLES), selected_color=BLUE)
        self.style.set(next((k for k, v in STYLES.items() if v == p.get("style", "court")), "Court"))
        self.style.pack(fill="x", padx=18, pady=2)
        ctk.CTkLabel(self, text="À savoir sur toi (facultatif)", text_color=TEXT, anchor="w").pack(fill="x", padx=18, pady=(12, 0))
        self.about = ctk.CTkTextbox(self, height=90, fg_color=PANEL, border_width=1, border_color=DEEP)
        self.about.insert("1.0", p.get("about", ""))
        self.about.pack(fill="x", padx=18, pady=2)
        ctk.CTkButton(self, text="Enregistrer mon profil", fg_color=BLUE, height=40, font=_font(14, "bold"),
                      command=self._save).pack(padx=18, pady=16, anchor="w")
        self.msg = ctk.CTkLabel(self, text="", text_color=GREEN, anchor="w")
        self.msg.pack(fill="x", padx=18)

    def _save(self):
        prof = {k: v.get().strip() for k, v in self.e.items()}
        prof["age"] = "".join(c for c in prof["age"] if c.isdigit())[:3]
        prof["assistant_name"] = prof["assistant_name"] or "Polaris"
        prof["address_form"] = FORMS[self.form.get()]
        prof["style"] = STYLES[self.style.get()]
        prof["about"] = self.about.get("1.0", "end").strip()
        self.app.settings.set("profile", prof)
        self.msg.configure(text="Profil enregistré.")


# =============================================================== Activité
class ActivityPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))
        _title(top, "Journal des actions").pack(side="left")
        ctk.CTkButton(top, text="Actualiser", width=100, fg_color=PANEL2, command=self.refresh).pack(side="right")
        ctk.CTkButton(top, text="Ouvrir le dossier", width=130, fg_color=PANEL2,
                      command=lambda: os.startfile(str(data_dir()))).pack(side="right", padx=6)
        self.box = ctk.CTkTextbox(self, fg_color=PANEL, text_color=TEXT, font=ctk.CTkFont(family="Consolas", size=12),
                                  border_width=1, border_color=DEEP, wrap="none")
        self.box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 16))

    def refresh(self):
        try:
            lines = (data_dir() / "actions.log").read_text(encoding="utf-8").splitlines()[-200:][::-1]
        except OSError:
            lines = []
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.insert("1.0", "\n".join(lines) or "Aucune action enregistrée pour l'instant.")
        self.box.configure(state="disabled")

    def on_show(self):
        self.refresh()


# =============================================================== Paramètres
SENS = {"Faible": "low", "Normale": "normal", "Élevée": "high"}


class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.app, self.s = app, app.settings
        _title(self, "Gemini").pack(fill="x", padx=18, pady=(16, 2))
        has = bool(self.s.get("api_key_enc"))
        self.key = ctk.CTkEntry(self, show="•", fg_color=PANEL, border_color=DEEP,
                                placeholder_text="Clé enregistrée — laisse vide pour la conserver" if has else "Colle ta clé API Gemini ici")
        self.key.pack(fill="x", padx=18, pady=4)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=18)
        ctk.CTkButton(row, text="Enregistrer", fg_color=BLUE, width=110, command=self._save_key).pack(side="left", padx=(0, 6))
        ctk.CTkButton(row, text="Tester", fg_color=PANEL2, width=80, command=self._test).pack(side="left")
        ctk.CTkButton(row, text="Effacer la clé", fg_color=PANEL2, width=110, command=self._clear_key).pack(side="left", padx=6)
        self.model_lbl = ctk.CTkLabel(self, text="", text_color=TEXT, anchor="w")
        self.model_lbl.pack(fill="x", padx=18, pady=(8, 0))
        ctk.CTkButton(self, text="Détecter le meilleur modèle Gemini", fg_color=PANEL2, command=self._detect).pack(padx=18, pady=4, anchor="w")
        self.msg = ctk.CTkLabel(self, text="", text_color=TEXT, anchor="w", justify="left", wraplength=620)
        self.msg.pack(fill="x", padx=18, pady=2)
        self._refresh_model()

        _title(self, "Réveil et veille").pack(fill="x", padx=18, pady=(18, 2))
        self._switch("Écouter « Hey Polaris » dès l'ouverture", "voice_on_start")
        self._switch("Démarrer réduit (Polaris se réveille quand tu l'appelles)", "start_hidden")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=3)
        ctk.CTkLabel(row, text="Se rendormir après (secondes, 0 = jamais) :", text_color=TEXT).pack(side="left")
        self.sleep = ctk.CTkEntry(row, width=70, fg_color=PANEL, border_color=DEEP)
        self.sleep.insert(0, str(self.s.get("auto_sleep_s", 25)))
        self.sleep.pack(side="left", padx=8)
        self.sleep.bind("<FocusOut>", self._save_sleep)
        self._switch("Mode économie de ressources", "economy_mode", app.apply_economy)
        self._switch("Réponses vocales", "tts_enabled")
        self._switch("Lire aussi les réponses aux messages écrits", "speak_text_replies")
        ctk.CTkLabel(self, text="Sensibilité du mot de réveil", text_color=TEXT, anchor="w").pack(fill="x", padx=18, pady=(8, 0))
        seg = ctk.CTkSegmentedButton(self, values=list(SENS), selected_color=BLUE,
                                     command=lambda v: self.s.set("wake_sensitivity", SENS[v]))
        seg.set(next(k for k, v in SENS.items() if v == self.s.get("wake_sensitivity", "normal")))
        seg.pack(fill="x", padx=18, pady=4)

        _title(self, "Ce que Polaris a le droit de faire").pack(fill="x", padx=18, pady=(18, 2))
        self._switch("Applications et fenêtres", "perm_apps")
        self._switch("Internet (sites, recherche, téléchargements avec accord)", "perm_web")
        self._switch("Lire les fichiers", "perm_files_read")
        self._switch("Modifier les fichiers (renommer, déplacer, corbeille avec accord)", "perm_files_modify")
        self._switch("Contrôler l'écran, la souris et le clavier", "perm_control")

        _title(self, "Dossiers autorisés").pack(fill="x", padx=18, pady=(18, 2))
        self.folders = ctk.CTkLabel(self, text="", text_color=TEXT, anchor="w", justify="left", wraplength=620)
        self.folders.pack(fill="x", padx=18)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=4)
        ctk.CTkButton(row, text="Ajouter un dossier…", fg_color=BLUE, command=self._add_folder).pack(side="left", padx=(0, 6))
        ctk.CTkButton(row, text="Retirer mes ajouts", fg_color=PANEL2, command=self._reset_folders).pack(side="left")
        self._refresh_folders()

        _title(self, "Confidentialité").pack(fill="x", padx=18, pady=(18, 2))
        self._switch("Enregistrer l'historique des conversations (texte)", "save_history")
        ctk.CTkButton(self, text="Effacer l'historique", fg_color=PANEL2,
                      command=app.clear_history).pack(padx=18, pady=(4, 20), anchor="w")

    def _switch(self, text, key, cb=None):
        sw = ctk.CTkSwitch(self, text=text, text_color=TEXT, progress_color=BLUE)
        if self.s.get(key):
            sw.select()

        def changed():
            self.s.set(key, bool(sw.get()))
            if cb:
                cb()
        sw.configure(command=changed)
        sw.pack(fill="x", padx=18, pady=3, anchor="w")

    def _save_sleep(self, _e=None):
        try:
            self.s.set("auto_sleep_s", max(0, int(self.sleep.get())))
        except ValueError:
            self.sleep.delete(0, "end")
            self.sleep.insert(0, str(self.s.get("auto_sleep_s", 25)))

    def _refresh_model(self):
        self.model_lbl.configure(text=f"Modèle utilisé : {self.app.assistant.gemini.current_model()}   "
                                      f"•   Requêtes aujourd'hui : {self.s.requests_today()}")

    def _save_key(self):
        k = self.key.get().strip()
        if not k:
            self.msg.configure(text="Rien à enregistrer.")
            return
        try:
            self.s.set_api_key(k)
        except Exception as e:
            self.msg.configure(text=f"Impossible de protéger la clé : {e}")
            return
        self.key.delete(0, "end")
        self.app.assistant.gemini.reset()
        self.app.assistant.announce_gemini_state()
        self.msg.configure(text="Clé enregistrée (chiffrée pour ta session Windows). Clique sur « Tester ».")

    def _clear_key(self):
        self.s.set("api_key_enc", "")
        self.app.assistant.gemini.reset()
        self.app.assistant.announce_gemini_state()
        self.msg.configure(text="Clé effacée.")

    def _run_bg(self, label, work):
        self.msg.configure(text=label, text_color=TEXT)

        def run():
            try:
                out, state, ok = work(), "ok", True
            except Exception as e:
                out, state, ok = getattr(e, "user_message", str(e)), getattr(e, "kind", "error"), False

            def done():
                self.msg.configure(text=out, text_color=GREEN if ok else ORANGE)
                self.app.set_gemini_state(state)
                self._refresh_model()
            self.app.call_in_ui(done)
        threading.Thread(target=run, daemon=True).start()

    def _test(self):
        self._run_bg("Test en cours…", lambda: "Connexion OK — réponse : " + self.app.assistant.gemini.test())

    def _detect(self):
        def work():
            self.s.set("gemini_model", "auto")
            self.s.set("resolved_model", "")
            return "Modèle choisi automatiquement : " + self.app.assistant.gemini.resolve_model()
        self._run_bg("Recherche du meilleur modèle…", work)

    def _add_folder(self):
        d = filedialog.askdirectory(parent=self, title="Dossier à autoriser")
        if d:
            lst = list(self.s.get("extra_folders", []))
            if d not in lst:
                lst.append(d)
                self.s.set("extra_folders", lst)
            self._refresh_folders()

    def _reset_folders(self):
        self.s.set("extra_folders", [])
        self._refresh_folders()

    def _refresh_folders(self):
        roots = self.app.assistant.perms.allowed_roots()
        self.folders.configure(text="\n".join(str(r) for r in roots) or "Aucun dossier détecté.")

    def on_show(self):
        self._refresh_model()
        self._refresh_folders()


# =============================================================== Aide
HELP = """Réveille-moi en disant « Hey Polaris » (un bip confirme), puis donne ta demande. Je me réduis tout seul quand j'ai fini.

APPLICATIONS ET WINDOWS
  « Hey Polaris, ouvre le Bloc-notes » · « ferme la calculatrice » · « ouvre Spotify »
  « ouvre les paramètres Wi-Fi » · « affiche le bureau » · « minimise la fenêtre »

INTERNET
  « ouvre YouTube » · « cherche sur Internet la météo à Annecy »

FAIRE DES CHOSES À L'ÉCRAN (souris + clavier)
  « Va sur Wikipédia et cherche Apollo 11 »
  « Ouvre mon navigateur et remplis le formulaire de contact »
  Je regarde l'écran, je clique et je tape à ta place. Échap ou STOP m'arrête tout de suite.
  Je te demande ton accord avant de TÉLÉCHARGER, SUPPRIMER ou PAYER. Je ne tape jamais de mot de passe ni dans un terminal.

FICHIERS
  « Trouve mon fichier PDF sur Apollo 11 » · « Cherche une image dans mes téléchargements »
  « Trouve tous mes fichiers Python » · « Cherche un fichier qui contient le mot facture »
  « Ouvre le premier résultat » · « Résume ce document » (avec ton accord) · « Classe mon dossier Téléchargements »
  Suppression : toujours avec ton accord, et uniquement vers la corbeille.

QUESTIONS, TEXTES, CODE
  « Explique-moi les trous noirs » · « Écris un mail pour… » · « Aide-moi à corriger ce code »

AUTRES
  « Quelle heure est-il ? » · « Stop » (je me tais) · « Arrête d'écouter » (je coupe le micro)
"""


class HelpPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        _title(self, "Aide — ce que je sais faire").grid(row=0, column=0, sticky="w", padx=18, pady=(16, 4))
        box = ctk.CTkTextbox(self, fg_color=PANEL, text_color=TEXT, font=_font(14), wrap="word", border_width=1, border_color=DEEP)
        box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 16))
        box.insert("1.0", HELP)
        box.configure(state="disabled")
