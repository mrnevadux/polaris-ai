"""Souris et clavier via SendInput (ctypes). Actions structurées uniquement."""
import ctypes
import sys
import time
from ctypes import wintypes

VK = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B, "windows": 0x5B,
      "enter": 0x0D, "entree": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09,
      "space": 0x20, "espace": 0x20, "backspace": 0x08, "delete": 0x2E, "suppr": 0x2E, "del": 0x2E,
      "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "home": 0x24, "end": 0x23,
      "pageup": 0x21, "pagedown": 0x22}
for _i in range(1, 13):
    VK[f"f{_i}"] = 0x6F + _i
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B}
DELETE_KEYS = {0x2E}
BLOCKED_CLASSES = {"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "VirtualConsoleClass"}  # terminaux


def parse_keys(spec: str):
    """'ctrl+shift+t' -> [0x11, 0x10, 0x54]. Lève ValueError si une touche est inconnue."""
    out = []
    for tok in str(spec).lower().replace(" ", "").split("+"):
        if tok in VK:
            out.append(VK[tok])
        elif len(tok) == 1 and tok.isalnum() and tok.isascii():
            out.append(ord(tok.upper()))
        else:
            raise ValueError(f"Touche inconnue : {tok!r}")
    if not out:
        raise ValueError("Aucune touche")
    return out


def is_delete_combo(spec: str) -> bool:
    try:
        return any(k in DELETE_KEYS for k in parse_keys(spec))
    except ValueError:
        return False


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _UNION)]


def _u32():
    if sys.platform != "win32":
        raise OSError("Le contrôle de la souris et du clavier n'est disponible que sous Windows.")
    return ctypes.windll.user32


def _send(inputs):
    arr = (_INPUT * len(inputs))(*inputs)
    _u32().SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))


def _key(vk=0, scan=0, flags=0):
    i = _INPUT(type=1)
    i.u.ki = _KEYBDINPUT(vk, scan, flags, 0, 0)
    return i


def _mouse(flags, data=0):
    i = _INPUT(type=0)
    i.u.mi = _MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)
    return i


def foreground_class() -> str:
    u = _u32()
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    buf = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(u.GetForegroundWindow(), buf, 256)
    return buf.value


def esc_pressed() -> bool:
    try:
        return bool(_u32().GetAsyncKeyState(0x1B) & 0x8000)
    except OSError:
        return False


def click(x: int, y: int, button: str = "left", double: bool = False):
    _u32().SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    down, up = {"left": (0x2, 0x4), "right": (0x8, 0x10)}[button]
    for _ in range(2 if double else 1):
        _send([_mouse(down), _mouse(up)])
        time.sleep(0.08)


def move(x: int, y: int):
    _u32().SetCursorPos(int(x), int(y))


def scroll(amount: int):
    """amount > 0 : vers le haut ; < 0 : vers le bas (1 cran = 120)."""
    _send([_mouse(0x0800, int(amount * 120))])


def _guard_terminal():
    if foreground_class() in BLOCKED_CLASSES:
        raise PermissionError("Je ne tape jamais dans un terminal (PowerShell, cmd) : trop risqué.")


def type_text(text: str):
    _guard_terminal()
    for ch in text[:2000]:
        if ch == "\n":
            _send([_key(0x0D), _key(0x0D, 0, 2)])
        elif ch == "\t":
            _send([_key(0x09), _key(0x09, 0, 2)])
        else:
            data = ch.encode("utf-16-le")
            for i in range(0, len(data), 2):
                code = int.from_bytes(data[i:i + 2], "little")
                _send([_key(0, code, 0x4), _key(0, code, 0x4 | 0x2)])
        time.sleep(0.01)


def press(spec: str):
    vks = parse_keys(spec)
    low = str(spec).lower().replace(" ", "")
    if low in ("win+r", "windows+r"):
        raise PermissionError("Je n'ouvre pas la boîte « Exécuter » : je ne lance pas de commandes libres.")
    _guard_terminal()
    mods, key = vks[:-1], vks[-1]
    seq = []
    for m in mods:
        seq.append(_key(m, 0, 1 if m in EXTENDED else 0))
    seq.append(_key(key, 0, 1 if key in EXTENDED else 0))
    seq.append(_key(key, 0, 2 | (1 if key in EXTENDED else 0)))
    for m in reversed(mods):
        seq.append(_key(m, 0, 2 | (1 if m in EXTENDED else 0)))
    _send(seq)
