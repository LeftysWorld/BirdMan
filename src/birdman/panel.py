"""The only module that talks to the Inky. Everything else just hands it an image."""

_panel = None


def push_to_panel(img) -> str:
    """Send to the Inky if there is one. On a laptop this quietly does nothing."""
    global _panel
    try:
        if _panel is None:
            from inky.auto import auto
            _panel = auto()
    except Exception as e:                              # no library, or no panel attached
        return f"no panel ({e.__class__.__name__})"
    if tuple(_panel.resolution) != img.size:
        return f"panel is {_panel.resolution}, image is {img.size} - fix W, H in config.py"
    try:
        _panel.set_image(img)
        _panel.show()
    except Exception as e:                              # a panel hiccup must not kill the day
        return f"panel error ({e})"
    return "panel updated"
