import io


def grab_jpeg(max_w: int = 1280):
    """Capture l'écran principal. Retourne (octets JPEG, (largeur réelle, hauteur réelle))."""
    from PIL import ImageGrab
    img = ImageGrab.grab().convert("RGB")
    w, h = img.size
    if w > max_w:
        img = img.resize((max_w, int(h * max_w / w)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    return buf.getvalue(), (w, h)
