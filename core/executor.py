"""Exécution contrôlée : liste blanche, autorisations, confirmation, journalisation."""
from core import logger
from core.tools import TOOLS, ToolContext, ToolError, ToolResult

CATEGORY_LABELS = {"apps": "Applications et fenêtres", "web": "Internet", "files_read": "Lecture de fichiers", "files_modify": "Modification de fichiers", "control": "Contrôle de l'écran, de la souris et du clavier"}


def run_call(ctx: ToolContext, tool_name: str, args: dict) -> ToolResult:
    tool = TOOLS.get(tool_name)
    if tool is None:
        logger.log_action(tool_name, "outil inconnu (refusé)", False)
        return ToolResult(False, "Cette action n'est pas autorisée.")
    if not ctx.perms.category_enabled(tool.category):
        logger.log_action(tool_name, "autorisation désactivée", False)
        return ToolResult(False, f"L'autorisation « {CATEGORY_LABELS.get(tool.category, tool.category)} » est désactivée dans les paramètres.")
    args = args if isinstance(args, dict) else {}
    try:
        if tool.confirm:
            msg = tool.confirm(ctx, args)
            if msg and not ctx.confirm(msg):
                logger.log_action(tool_name, f"{args} — refusé par l'utilisateur", False)
                return ToolResult(False, "Action annulée.")
        res = tool.fn(ctx, args)
    except ToolError as e:
        logger.log_action(tool_name, f"{args} — {e}", False)
        return ToolResult(False, str(e))
    except Exception as e:
        if hasattr(e, "kind") and hasattr(e, "user_message"):  # GeminiError : remonté tel quel
            raise
        logger.get().exception("Erreur outil %s", tool_name)
        logger.log_action(tool_name, f"{args} — erreur {e}", False)
        return ToolResult(False, f"L'action a échoué : {e}")
    logger.log_action(tool_name, f"{args} — {res.text[:120]}", res.ok)
    return res
