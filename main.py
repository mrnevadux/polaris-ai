"""POLARIS — point d'entrée."""
import multiprocessing
import sys

_mutex = None


def _single_instance() -> bool:
    global _mutex
    if sys.platform != "win32":
        return True
    import ctypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    _mutex = k.CreateMutexW(None, False, "Local\\Polaris_Assistant_Mutex")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def _dpi_aware():
    """Coordonnées d'écran exactes (nécessaire au pilotage souris)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    multiprocessing.freeze_support()
    _dpi_aware()
    from config.settings import Settings, data_dir
    from core import logger
    d = data_dir()
    logger.setup(d)
    try:
        if not _single_instance():
            from tkinter import Tk, messagebox
            r = Tk(); r.withdraw()
            messagebox.showinfo("Polaris", "Polaris est déjà ouvert.")
            return
        from interface.app import PolarisApp
        PolarisApp(Settings(d / "settings.json")).mainloop()
    except Exception as e:
        logger.get().exception("Plantage au démarrage")
        try:
            from tkinter import Tk, messagebox
            r = Tk(); r.withdraw()
            messagebox.showerror("Polaris", f"Polaris n'a pas pu démarrer :\n{e}\n\nDétails : Polaris_data/polaris.log")
        except Exception:
            pass


if __name__ == "__main__":
    main()
