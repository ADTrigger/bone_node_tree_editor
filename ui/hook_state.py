_ui_hooks_registered = False


def is_ui_hooks_registered() -> bool:
    return _ui_hooks_registered


def set_ui_hooks_registered(state: bool):
    global _ui_hooks_registered
    _ui_hooks_registered = state
