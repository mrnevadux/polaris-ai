"""Gestion des fenêtres via l'API Windows (ctypes). Aucune commande shell."""
import ctypes
import os
import sys
import time
from ctypes import wintypes

SW_MAXIMIZE, SW_MINIMIZE, SW_RESTORE = 3, 6, 9
WM_CLOSE = 0x0010
PROTECTED_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"}


def _u32():
    if sys.platform != "win32":
        raise OSError("Disponible uniquement sous Windows.")
    u = ctypes.windll.user32
    u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetForegroundWindow.restype = wintypes.HWND
    return u


def _class_name(u, hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _pid_of(u, hwnd) -> int:
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def close_windows(pids, only_classes=None) -> int:
    """Demande poliment la fermeture (WM_CLOSE) des fenêtres visibles de ces processus."""
    u = _u32()
    pids = set(pids)
    hits = []
    CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _lp):
        if u.IsWindowVisible(hwnd) and u.GetWindowTextLengthW(hwnd) > 0 and _pid_of(u, hwnd) in pids:
            cls = _class_name(u, hwnd)
            if cls not in PROTECTED_CLASSES and (not only_classes or cls in only_classes):
                hits.append(hwnd)
        return True

    u.EnumWindows(CB(cb), 0)
    for h in hits:
        u.PostMessageW(h, WM_CLOSE, 0, 0)
    return len(hits)


def foreground_action(action: str):
    """Agit sur la fenêtre active (jamais sur Polaris lui-même). Retourne (ok, message)."""
    u = _u32()
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        return False, "Aucune fenêtre active."
    if _pid_of(u, hwnd) == os.getpid():
        return False, "La fenêtre active est Polaris : clique d'abord sur la fenêtre à gérer."
    if _class_name(u, hwnd) in PROTECTED_CLASSES:
        return False, "La fenêtre active est le bureau ou la barre des tâches."
    if action == "minimize":
        u.ShowWindow(hwnd, SW_MINIMIZE)
    elif action == "maximize":
        u.ShowWindow(hwnd, SW_MAXIMIZE)
    elif action == "restore":
        u.ShowWindow(hwnd, SW_RESTORE)
    elif action == "close":
        u.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    else:
        return False, "Action de fenêtre inconnue."
    return True, "C'est fait."


def minimize_all():
    """Affiche le bureau (Win+D)."""
    u = _u32()
    VK_LWIN, VK_D, KEYUP = 0x5B, 0x44, 0x0002
    u.keybd_event(VK_LWIN, 0, 0, 0)
    u.keybd_event(VK_D, 0, 0, 0)
    time.sleep(0.05)
    u.keybd_event(VK_D, 0, KEYUP, 0)
    u.keybd_event(VK_LWIN, 0, KEYUP, 0)
