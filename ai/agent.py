"""Pilotage de l'écran : capture -> Gemini choisit UNE action structurée -> Polaris l'exécute.
Seules les actions de la liste blanche existent (clic, texte, touches, défilement, ouverture d'URL/d'appli).
Téléchargement, suppression et paiement exigent ton autorisation. Échap ou STOP interrompt tout."""
import time

from core import logger
from windows import apps, inputctl, screen, web

MAX_STEPS = 25
RISKS = {"download": "télécharger un fichier", "delete": "supprimer quelque chose", "payment": "faire un achat ou un paiement"}


def _num(v, default=500.0):
    try:
        return max(0.0, min(1000.0, float(v)))
    except (TypeError, ValueError):
        return default


def run(ctx, goal: str):
    from core.tools import ToolResult
    ui = ctx.ui
    history = []
    ui.set_agent_mode(True)
    try:
        for step in range(1, MAX_STEPS + 1):
            if ctx.cancel.is_set() or inputctl.esc_pressed():
                return ToolResult(False, "J'ai arrêté la tâche.")
            jpeg, (w, h) = screen.grab_jpeg()
            act = ctx.gemini.vision_step(goal, history, jpeg)
            kind = str(act.get("action", "")).lower().strip()
            thought = str(act.get("thought", ""))[:160]
            risk = str(act.get("risk", "none")).lower().strip()
            if kind == "done":
                return ToolResult(True, str(act.get("summary") or "C'est fait."))
            if kind == "fail":
                return ToolResult(False, str(act.get("summary") or "Je n'y arrive pas."))
            if kind == "key" and inputctl.is_delete_combo(str(act.get("keys", ""))):
                risk = "delete"
            if risk in RISKS:
                if not ctx.confirm(f"Polaris veut {RISKS[risk]} :\n{thought}\n\nAutoriser cette action ?"):
                    logger.log_action("computer_task", f"{risk} refusé : {thought}", False)
                    return ToolResult(False, "Action refusée : j'arrête la tâche.")
            try:
                desc = _execute(kind, act, w, h)
            except (PermissionError, ValueError, OSError) as e:
                logger.log_action("computer_task", f"étape {step} bloquée : {e}", False)
                return ToolResult(False, f"Étape bloquée : {e}")
            if desc is None:
                return ToolResult(False, f"Action inconnue demandée par l'IA : « {kind} ». J'arrête par sécurité.")
            history.append(f"{step}. {desc}")
            logger.log_action("computer_task", f"étape {step} : {desc}", True)
            ui.add_message("system", f"Étape {step} : {thought or desc}")
            time.sleep(0.9)
        return ToolResult(False, f"Je n'ai pas terminé en {MAX_STEPS} étapes. Dis-moi si je dois continuer.")
    finally:
        ui.set_agent_mode(False)


def _execute(kind, act, w, h):
    if kind in ("click", "double_click", "right_click"):
        px, py = _num(act.get("x")) / 1000 * w, _num(act.get("y")) / 1000 * h
        inputctl.click(px, py, "right" if kind == "right_click" else "left", kind == "double_click")
        return f"{kind} ({int(px)},{int(py)})"
    if kind == "type":
        text = str(act.get("text", ""))
        inputctl.type_text(text)
        return f"texte saisi ({len(text)} caractères)"
    if kind == "key":
        keys = str(act.get("keys", ""))
        inputctl.press(keys)
        return f"touches {keys}"
    if kind == "scroll":
        if act.get("x") is not None and act.get("y") is not None:
            inputctl.move(_num(act.get("x")) / 1000 * w, _num(act.get("y")) / 1000 * h)
        dy = int(max(-10, min(10, float(act.get("dy", -3) or -3))))
        inputctl.scroll(dy)
        return f"défilement {dy}"
    if kind == "wait":
        time.sleep(2)
        return "attente"
    if kind == "open_url":
        url = web.resolve_url(str(act.get("url", "")))
        if not url:
            raise ValueError("adresse non valide")
        web.open_url(url)
        time.sleep(1.5)
        return f"ouverture de {url}"
    if kind == "open_app":
        ok, msg = apps.launch(str(act.get("app", "")))
        if not ok:
            raise ValueError(msg)
        time.sleep(1.5)
        return f"ouverture de {act.get('app')}"
    return None
