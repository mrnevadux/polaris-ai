import logging
import logging.handlers
from pathlib import Path

_done = False


def setup(data_dir: Path):
    global _done
    if _done:
        return
    _done = True
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    app = logging.getLogger("polaris")
    app.setLevel(logging.INFO)
    h = logging.handlers.RotatingFileHandler(Path(data_dir) / "polaris.log", maxBytes=512_000, backupCount=1, encoding="utf-8")
    h.setFormatter(fmt)
    app.addHandler(h)
    act = logging.getLogger("polaris.actions")
    act.setLevel(logging.INFO)
    act.propagate = False
    h2 = logging.handlers.RotatingFileHandler(Path(data_dir) / "actions.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    h2.setFormatter(fmt)
    act.addHandler(h2)


def get():
    return logging.getLogger("polaris")


def log_action(kind: str, detail: str, ok: bool = True):
    logging.getLogger("polaris.actions").info("%s | %s | %s", "OK" if ok else "ECHEC", kind, detail)
