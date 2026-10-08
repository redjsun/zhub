## Copyright (C) 2026  ZHUB contributors
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Reusable widgets: action picker, shortcut recorder and command dialog."""

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gtk

from keysyms.keysymdef import key_symbols

from . import actions

_MODIFIERS = [
    (Gdk.ModifierType.CONTROL_MASK, "Control_L"),
    (Gdk.ModifierType.SHIFT_MASK, "Shift_L"),
    (Gdk.ModifierType.ALT_MASK, "Alt_L"),
    (Gdk.ModifierType.SUPER_MASK, "Super_L"),
]
_MODIFIER_KEYS = {"Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R", "Super_L", "Super_R", "Meta_L", "Meta_R"}


def _keysym_name(keyval):
    name = Gdk.keyval_name(Gdk.keyval_to_lower(keyval))
    if name and name.startswith("XF86") and not name.startswith("XF86_"):
        name = "XF86_" + name[4:]
    return name if name in key_symbols else None


class ActionList(Gtk.Box):
    """Grouped list of actions; calls on_choose(choice) when one is picked."""

    def __init__(self, allowed, current, on_choose, parent_widget):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self._on_choose = on_choose
        self._parent_widget = parent_widget
        current_id = (current or {}).get("action", "default")
        for group_title, group_actions in actions.ACTION_GROUPS:
            visible = [a for a in group_actions if a.id in allowed]
            if not visible:
                continue
            group = Adw.PreferencesGroup(title=group_title)
            for action in visible:
                row = Adw.ActionRow(title=action.label, activatable=True)
                row.add_prefix(Gtk.Image(icon_name=action.icon))
                if action.keys:
                    row.set_subtitle(actions.format_keys(action.keys))
                if action.id == current_id:
                    if action.special in ("custom-keys", "command"):
                        row.set_subtitle(actions.describe(current))
                    row.add_suffix(Gtk.Image(icon_name="object-select-symbolic", css_classes=["accent"]))
                    row.add_css_class("current-action")
                row.connect("activated", lambda _r, a=action: self._picked(a, current))
                group.add(row)
            self.append(group)

    def _picked(self, action, current):
        if action.special == "custom-keys":
            ShortcutDialog(current.get("keys") if current else None, lambda keys: self._on_choose({"action": action.id, "keys": keys})).present(
                self._parent_widget
            )
        elif action.special == "command":
            ask_command(
                self._parent_widget,
                (current or {}).get("command", ""),
                lambda command: self._on_choose({"action": action.id, "command": command}),
            )
        else:
            self._on_choose({"action": action.id})


class ShortcutDialog(Adw.Dialog):
    """Records a key combination, like the keystroke assignment in Options+."""

    def __init__(self, keys, on_done):
        super().__init__(title="Atalho de teclado", content_width=420)
        self._on_done = on_done
        self._keys = keys

        save = Gtk.Button(label="Salvar", css_classes=["suggested-action"], sensitive=bool(keys))
        save.connect("clicked", self._save)
        self._save_button = save
        header = Adw.HeaderBar()
        header.pack_end(save)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=24, margin_bottom=32, margin_start=24, margin_end=24)
        box.append(Gtk.Image(icon_name="input-keyboard-symbolic", pixel_size=48, css_classes=["dim-label"]))
        box.append(Gtk.Label(label="Pressione a combinação de teclas", css_classes=["title-3"]))
        self._shown = Gtk.Label(label=actions.format_keys(keys) if keys else "…", css_classes=["shortcut-preview"])
        box.append(self._shown)
        box.append(
            Gtk.Label(
                label="Atalhos com a tecla Super podem ser capturados pelo GNOME antes de chegar aqui.",
                wrap=True,
                justify=Gtk.Justification.CENTER,
                css_classes=["dim-label", "caption"],
            )
        )

        view = Adw.ToolbarView(content=box)
        view.add_top_bar(header)
        self.set_child(view)

        keys_controller = Gtk.EventControllerKey()
        keys_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys_controller.connect("key-pressed", self._key_pressed)
        self.add_controller(keys_controller)

    def _key_pressed(self, _controller, keyval, _keycode, state):
        name = _keysym_name(keyval)
        if name is None or name in _MODIFIER_KEYS:
            return name in _MODIFIER_KEYS
        if name == "Escape" and not state & Gtk.accelerator_get_default_mod_mask():
            return False  # let Escape close the dialog
        keys = [k for mask, k in _MODIFIERS if state & mask] + [name]
        self._keys = keys
        self._shown.set_label(actions.format_keys(keys))
        self._save_button.set_sensitive(True)
        return True

    def _save(self, _button):
        self.close()
        self._on_done(self._keys)


def ask_command(parent, current, on_done):
    dialog = Adw.AlertDialog(heading="Executar comando", body="Comando executado quando a ação for acionada.")
    entry = Gtk.Entry(text=current, placeholder_text="ex.: gnome-calculator", activates_default=True)
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancelar")
    dialog.add_response("save", "Salvar")
    dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("save")

    def response(_dialog, answer):
        if answer == "save" and entry.get_text().strip():
            on_done(entry.get_text().strip())

    dialog.connect("response", response)
    dialog.present(parent)


def battery_icon(battery):
    if not battery:
        return None
    level = battery.get("level")
    if level is None:
        return "battery-symbolic"
    rounded = min(100, int(round(level / 10.0)) * 10)
    return f"battery-level-{rounded}{'-charging' if battery.get('charging') else ''}-symbolic"


def battery_text(battery):
    if not battery:
        return ""
    return f"{battery['level']}%" if battery.get("level") is not None else battery.get("text", "")
