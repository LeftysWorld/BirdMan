"""The only module that talks to the Inky. Everything else just hands it an image."""

_panel = None

ROTATE = 90                 # which way a portrait frame is turned on the wall: 90 or 270


def push_to_panel(img) -> str:
    """Send to the Inky if there is one. On a laptop this quietly does nothing.

    The panel itself is always landscape. If the image is portrait (W and H swapped in
    config.py because the frame hangs upright) it is turned to match before sending.
    """
    global _panel
    try:
        if _panel is None:
            from inky.auto import auto
            _panel = auto()
    except Exception as e:                              # no library, or no panel attached
        return f"no panel ({e.__class__.__name__})"
    size = tuple(_panel.resolution)
    if img.size == size[::-1]:
        img = img.rotate(ROTATE, expand=True)
    if img.size != size:
        return f"panel is {size}, image is {img.size} - fix W, H in config.py"
    try:
        _panel.set_image(img)
        _panel.show()
    except Exception as e:                              # a panel hiccup must not kill the day
        return f"panel error ({e})"
    return "panel updated"
