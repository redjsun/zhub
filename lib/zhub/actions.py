## Copyright (C) 2026  ZHUB contributors
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Button, gesture and thumb wheel actions chosen in the ZHUB panel.

This module is shared by the panel (GTK4) and the service (GTK3), so it must
not import Gtk. The panel saves choices to ACTIONS_FILE; the service turns
them into Solaar rules with compile_rules().
"""

import os
import shlex

import yaml

_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
ACTIONS_FILE = os.path.join(_CONFIG_HOME, "zhub", "actions.yaml")

# divert-keys modes, as numbered by the device
REGULAR, DIVERTED, GESTURES = 0, 1, 2

# Buttons that can be customized, by Solaar control name
MIDDLE = "Middle Button"
BACK = "Back Button"
FORWARD = "Forward Button"
GESTURE = "Mouse Gesture Button"
SMART_SHIFT = "Smart Shift"

BUTTON_LABELS = {
    MIDDLE: "Botão do meio",
    BACK: "Voltar",
    FORWARD: "Avançar",
    GESTURE: "Botão de gestos",
    SMART_SHIFT: "Botão SmartShift",
}

GESTURE_DIRECTIONS = {
    "click": ("Clique", None),
    "up": ("Para cima", "Mouse Up"),
    "down": ("Para baixo", "Mouse Down"),
    "left": ("Para a esquerda", "Mouse Left"),
    "right": ("Para a direita", "Mouse Right"),
}


class Action:
    def __init__(self, id, label, icon, native=None, keys=None, special=None):
        self.id = id
        self.label = label
        self.icon = icon
        self.native = native  # reprogrammable-keys target, handled by the mouse itself
        self.keys = keys  # keysyms sent by the service
        self.special = special  # "default", "gestures", "custom-keys", "command", "none"


def _a(id, label, icon, **kw):
    return Action(id, label, icon, **kw)


ACTION_GROUPS = [
    (
        "Mouse",
        [
            _a("default", "Padrão", "edit-undo-symbolic", special="default"),
            _a("gestures", "Gestos", "input-touchpad-symbolic", special="gestures"),
            _a("middle-click", "Clique do meio", "input-mouse-symbolic", native="Mouse Middle Button"),
            _a("back", "Voltar", "go-previous-symbolic", native="Mouse Back Button"),
            _a("forward", "Avançar", "go-next-symbolic", native="Mouse Forward Button"),
            _a("smart-shift", "Alternar SmartShift", "media-playlist-shuffle-symbolic", native="Smart Shift"),
            _a("none", "Desativado", "action-unavailable-symbolic", special="none"),
        ],
    ),
    (
        "Janelas e área de trabalho",
        [
            _a("overview", "Visão geral das atividades", "view-grid-symbolic", keys=["Super_L"]),
            _a("app-grid", "Mostrar aplicativos", "view-app-grid-symbolic", keys=["Super_L", "a"]),
            _a("show-desktop", "Mostrar área de trabalho", "user-desktop-symbolic", keys=["Super_L", "d"]),
            _a("workspace-prev", "Workspace anterior", "go-first-symbolic", keys=["Super_L", "Page_Up"]),
            _a("workspace-next", "Próximo workspace", "go-last-symbolic", keys=["Super_L", "Page_Down"]),
            _a("switch-app", "Alternar aplicativos", "view-dual-symbolic", keys=["Alt_L", "Tab"]),
            _a("maximize", "Maximizar janela", "window-maximize-symbolic", keys=["Super_L", "Up"]),
            _a("minimize", "Minimizar janela", "window-minimize-symbolic", keys=["Super_L", "h"]),
            _a("close-window", "Fechar janela", "window-close-symbolic", keys=["Alt_L", "F4"]),
            _a("lock", "Bloquear tela", "system-lock-screen-symbolic", keys=["Super_L", "l"]),
            _a("screenshot", "Captura de tela", "camera-photo-symbolic", keys=["Print"]),
        ],
    ),
    (
        "Edição",
        [
            _a("copy", "Copiar", "edit-copy-symbolic", keys=["Control_L", "c"]),
            _a("paste", "Colar", "edit-paste-symbolic", keys=["Control_L", "v"]),
            _a("cut", "Recortar", "edit-cut-symbolic", keys=["Control_L", "x"]),
            _a("undo", "Desfazer", "edit-undo-symbolic", keys=["Control_L", "z"]),
            _a("redo", "Refazer", "edit-redo-symbolic", keys=["Control_L", "Shift_L", "z"]),
            _a("select-all", "Selecionar tudo", "edit-select-all-symbolic", keys=["Control_L", "a"]),
        ],
    ),
    (
        "Navegador",
        [
            _a("new-tab", "Nova aba", "tab-new-symbolic", keys=["Control_L", "t"]),
            _a("close-tab", "Fechar aba", "window-close-symbolic", keys=["Control_L", "w"]),
            _a("reopen-tab", "Reabrir aba fechada", "view-refresh-symbolic", keys=["Control_L", "Shift_L", "t"]),
            _a("next-tab", "Próxima aba", "go-next-symbolic", keys=["Control_L", "Page_Down"]),
            _a("prev-tab", "Aba anterior", "go-previous-symbolic", keys=["Control_L", "Page_Up"]),
            _a("zoom-in", "Aumentar zoom", "zoom-in-symbolic", keys=["Control_L", "plus"]),
            _a("zoom-out", "Diminuir zoom", "zoom-out-symbolic", keys=["Control_L", "minus"]),
        ],
    ),
    (
        "Mídia",
        [
            _a("play-pause", "Reproduzir / pausar", "media-playback-start-symbolic", keys=["XF86_AudioPlay"]),
            _a("next-track", "Próxima faixa", "media-skip-forward-symbolic", keys=["XF86_AudioNext"]),
            _a("prev-track", "Faixa anterior", "media-skip-backward-symbolic", keys=["XF86_AudioPrev"]),
            _a("volume-up", "Aumentar volume", "audio-volume-high-symbolic", keys=["XF86_AudioRaiseVolume"]),
            _a("volume-down", "Diminuir volume", "audio-volume-low-symbolic", keys=["XF86_AudioLowerVolume"]),
            _a("mute", "Silenciar", "audio-volume-muted-symbolic", keys=["XF86_AudioMute"]),
        ],
    ),
    (
        "Personalizado",
        [
            _a("custom-keys", "Atalho de teclado…", "input-keyboard-symbolic", special="custom-keys"),
            _a("command", "Executar comando…", "utilities-terminal-symbolic", special="command"),
        ],
    ),
]

ACTIONS = {a.id: a for _group, actions in ACTION_GROUPS for a in actions}

# Thumb wheel: (label, icon, keys when rolled forward, keys when rolled back, base threshold)
# The diverted thumb wheel reports 120 units per full turn on the MX Master 3S. The base
# threshold is the rotation needed per action at the default sensitivity.
THUMB_WHEEL_MODES = {
    "hscroll": ("Rolagem horizontal", "object-flip-horizontal-symbolic", None, None, None),
    "volume": ("Volume", "audio-volume-high-symbolic", ["XF86_AudioRaiseVolume"], ["XF86_AudioLowerVolume"], 8),
    "zoom": ("Zoom", "zoom-in-symbolic", ["Control_L", "plus"], ["Control_L", "minus"], 12),
    "tabs": ("Trocar de aba", "tab-new-symbolic", ["Control_L", "Page_Down"], ["Control_L", "Page_Up"], 12),
    "workspaces": ("Trocar de workspace", "view-grid-symbolic", ["Super_L", "Page_Down"], ["Super_L", "Page_Up"], 20),
}

THUMB_WHEEL_SENSITIVITY = (1, 10)
DEFAULT_THUMB_WHEEL_SENSITIVITY = 5


def thumbwheel_threshold(base, sensitivity):
    """Rotation needed per action: the default sensitivity uses the base, 10 halves it, 1 needs 5x more."""
    return max(1, round(base * DEFAULT_THUMB_WHEEL_SENSITIVITY / sensitivity))


_KEY_LABELS = {
    "Control_L": "Ctrl",
    "Control_R": "Ctrl",
    "Shift_L": "Shift",
    "Shift_R": "Shift",
    "Alt_L": "Alt",
    "Alt_R": "Alt",
    "Super_L": "Super",
    "Super_R": "Super",
    "Page_Up": "PgUp",
    "Page_Down": "PgDn",
    "plus": "+",
    "minus": "-",
    "Print": "PrtSc",
}


def format_keys(keys):
    return " + ".join(_KEY_LABELS.get(k, k.upper() if len(k) == 1 else k.replace("XF86_", "")) for k in keys)


# ---------------------------------------------------------------- persistence


def default_device_config():
    return {
        "buttons": {GESTURE: {"action": "gestures"}},
        "gestures": {
            "click": {"action": "overview"},
            "up": {"action": "app-grid"},
            "down": {"action": "show-desktop"},
            "left": {"action": "workspace-prev"},
            "right": {"action": "workspace-next"},
        },
        "thumbwheel": "hscroll",
        "thumbwheel_sensitivity": DEFAULT_THUMB_WHEEL_SENSITIVITY,
    }


def load():
    try:
        with open(ACTIONS_FILE) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    data.setdefault("devices", {})
    return data


def save(data):
    os.makedirs(os.path.dirname(ACTIONS_FILE), exist_ok=True)
    tmp = ACTIONS_FILE + ".tmp"
    with open(tmp, "w") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    os.replace(tmp, ACTIONS_FILE)


def device_config(data, device_id):
    config = data["devices"].setdefault(device_id, default_device_config())
    defaults = default_device_config()
    for k, v in defaults.items():
        config.setdefault(k, v)
    return config


def describe(choice):
    """Human label for a stored choice like {"action": "copy"} or {"action": "custom-keys", "keys": [...]}."""
    if not choice:
        return ACTIONS["default"].label
    action = ACTIONS.get(choice.get("action"), ACTIONS["default"])
    if action.special == "custom-keys" and choice.get("keys"):
        return format_keys(choice["keys"])
    if action.special == "command" and choice.get("command"):
        return choice["command"]
    return action.label


def divert_mode(choice):
    """divert-keys mode needed by a button choice."""
    action = ACTIONS.get((choice or {}).get("action"), ACTIONS["default"])
    if action.special == "gestures":
        return GESTURES
    if action.native or action.special == "default":
        return REGULAR
    return DIVERTED  # keys, commands and "none" are handled (or swallowed) by the service


# ---------------------------------------------------------------- rule generation


def _effect(choice):
    """Rule action component for a choice, or None if the service has nothing to do."""
    action = ACTIONS.get((choice or {}).get("action"))
    if action is None:
        return None
    if action.keys:
        return {"KeyPress": [action.keys, "click"]}
    if action.special == "custom-keys" and choice.get("keys"):
        return {"KeyPress": [choice["keys"], "click"]}
    if action.special == "command" and choice.get("command"):
        return {"Execute": shlex.split(choice["command"])}
    return None


def compile_rules(data):
    rules = []
    for device_id, config in data.get("devices", {}).items():
        device = {"Device": str(device_id)}
        buttons = config.get("buttons", {})
        for button, choice in buttons.items():
            if divert_mode(choice) == GESTURES:
                for direction, gesture in config.get("gestures", {}).items():
                    effect = _effect(gesture)
                    if effect and direction in GESTURE_DIRECTIONS:
                        movement = GESTURE_DIRECTIONS[direction][1]
                        gesture_condition = {"MouseGesture": [button] + ([movement] if movement else [])}
                        rules.append({"Rule": [device, gesture_condition, effect]})
            else:
                effect = _effect(choice)
                if effect:
                    rules.append({"Rule": [device, {"Key": [button, "pressed"]}, effect]})
        mode = THUMB_WHEEL_MODES.get(config.get("thumbwheel"))
        if mode and mode[2]:
            _label, _icon, forward, back, base = mode
            sensitivity = config.get("thumbwheel_sensitivity", DEFAULT_THUMB_WHEEL_SENSITIVITY)
            threshold = thumbwheel_threshold(base, sensitivity)
            rules.append({"Rule": [device, {"Test": ["thumb_wheel_up", threshold]}, {"KeyPress": [back, "click"]}]})
            rules.append({"Rule": [device, {"Test": ["thumb_wheel_down", threshold]}, {"KeyPress": [forward, "click"]}]})
    return rules
