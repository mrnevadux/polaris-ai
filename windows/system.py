import os

from core.textutil import normalize

SETTINGS_PAGES = {
    "": "ms-settings:",
    "wifi": "ms-settings:network-wifi", "internet": "ms-settings:network-status",
    "reseau": "ms-settings:network-status", "bluetooth": "ms-settings:bluetooth",
    "affichage": "ms-settings:display", "ecran": "ms-settings:display",
    "son": "ms-settings:sound", "audio": "ms-settings:sound",
    "applications": "ms-settings:appsfeatures", "mises a jour": "ms-settings:windowsupdate",
    "windows update": "ms-settings:windowsupdate", "confidentialite": "ms-settings:privacy",
    "micro": "ms-settings:privacy-microphone", "microphone": "ms-settings:privacy-microphone",
    "personnalisation": "ms-settings:personalization", "batterie": "ms-settings:batterysaver",
    "stockage": "ms-settings:storagesense", "langue": "ms-settings:regionlanguage",
    "voix": "ms-settings:speech", "imprimantes": "ms-settings:printers",
}


def settings_uri(page: str) -> str:
    n = normalize(page or "")
    for k, uri in SETTINGS_PAGES.items():
        if k and (n == k or k in n):
            return uri
    return SETTINGS_PAGES[""]


def open_settings(page: str = "") -> str:
    uri = settings_uri(page)
    os.startfile(uri)  # URI ms-settings: uniquement (liste blanche ci-dessus)
    return uri
