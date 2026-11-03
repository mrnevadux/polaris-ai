"""Protection de la clé API avec Windows DPAPI (liée à la session Windows de l'utilisateur)."""
import base64
import ctypes
import sys
from ctypes import wintypes


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _make_blob(data: bytes):
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _crypt(data: bytes, protect: bool) -> bytes:
    blob_in, _keep = _make_blob(data)
    blob_out = _Blob()
    crypt32 = ctypes.windll.crypt32
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(blob_in), "Polaris", None, None, None, 0, ctypes.byref(blob_out))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    if not ok:
        raise OSError("Échec DPAPI")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def protect(text: str) -> str:
    raw = text.encode("utf-8")
    if sys.platform == "win32":
        return "dpapi:" + base64.b64encode(_crypt(raw, True)).decode("ascii")
    return "plain:" + base64.b64encode(raw).decode("ascii")  # tests hors Windows uniquement


def unprotect(token: str) -> str:
    kind, _, payload = token.partition(":")
    raw = base64.b64decode(payload)
    if kind == "dpapi":
        if sys.platform != "win32":
            raise OSError("DPAPI indisponible")
        return _crypt(raw, False).decode("utf-8")
    if kind == "plain":
        return raw.decode("utf-8")
    raise ValueError("Format inconnu")
