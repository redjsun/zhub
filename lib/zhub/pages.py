## Copyright (C) 2026  ZHUB contributors
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Device pages: buttons, gestures, point & scroll and Easy-Switch."""

from gi.repository import Adw
from gi.repository import GLib
from gi.repository import Gtk

from . import actions
from .mouse_canvas import THUMB_WHEEL
from .mouse_canvas import MouseCanvas
from .mouse_canvas import MouseThumbnail
from .widgets import ActionList
from .widgets import battery_icon
from .widgets import battery_text

REPROG = "reprogrammable-keys"
DIVERT = "divert-keys"

# settings handled by dedicated widgets, never shown in the generic list
_HANDLED = {
    "dpi",
    "smart-shift",
    "scroll-ratchet",
    "hires-smooth-invert",
    "hires-smooth-resolution",
    "hires-scroll-mode",
    "thumb-scroll-mode",
    "thumb-scroll-invert",
    "change-host",
    REPROG,
    DIVERT,
}

GESTURE_PRESETS = {
    "Navegação no GNOME": {
        "click": "overview",
        "up": "app-grid",
        "down": "show-desktop",
        "left": "workspace-prev",
        "right": "workspace-next",
    },
    "Mídia": {"click": "play-pause", "up": "volume-up", "down": "volume-down", "left": "prev-track", "right": "next-track"},
    "Navegador": {"click": "new-tab", "up": "reopen-tab", "down": "close-tab", "left": "prev-tab", "right": "next-tab"},
    "Janelas": {"click": "switch-app", "up": "maximize", "down": "minimize", "left": "workspace-prev", "right": "workspace-next"},
}


def is_mx_master(info):
    return "MX Master" in (info.get("name") or "")


class DeviceController:
    """Device state plus the logic to apply button/gesture choices."""

    def __init__(self, client, info, toast):
        self.client = client
        self.info = info
        self.toast = toast
        self.listeners = []

    @property
    def id(self):
        return self.info["id"]

    def update(self, info):
        self.info = info
        for listener in self.listeners:
            listener()

    def setting(self, name):
        return next((s for s in self.info.get("settings", []) if s["name"] == name), None)

    def _error(self, message):
        self.toast(f"Não foi possível aplicar: {message}")

    def set(self, name, value):
        self.client.set_setting(self.id, name, value, self.update, self._error)

    def set_key(self, name, key, value, callback=None):
        def done(info):
            self.update(info)
            if callback:
                callback()

        self.client.set_setting_key(self.id, name, int(key), int(value), done, self._error)

    # ------------------------------------------------------------ buttons

    def cid(self, control):
        """Device control id for a Solaar control name."""
        for setting_name in (REPROG, DIVERT):
            s = self.setting(setting_name)
            if s:
                for cid, key in s["keys"].items():
                    if key["name"] == control:
                        return cid
        return None

    def buttons(self):
        """Customizable buttons present on this device, in display order."""
        return [b for b in actions.BUTTON_LABELS if self.cid(b) is not None]

    def allowed_actions(self, control):
        reprog = self.setting(REPROG)
        cid = self.cid(control)
        native_names = []
        if reprog and cid in reprog["keys"]:
            choices = reprog["keys"][cid]["choices"]
            native_names = [name for _id, name in choices[1:]]  # first choice is the default
        divertable = bool(self.setting(DIVERT)) and cid in self.setting(DIVERT)["keys"]
        allowed = []
        for action in actions.ACTIONS.values():
            if action.special == "default":
                allowed.append(action.id)
            elif action.native:
                if action.native in native_names:
                    allowed.append(action.id)
            elif action.special == "gestures":
                if divertable and control == actions.GESTURE:
                    allowed.append(action.id)
            elif divertable:
                allowed.append(action.id)
        return allowed

    def current_choice(self, control):
        """What the button does now, from the saved choice and the device state."""
        cid = self.cid(control)
        divert = self.setting(DIVERT)
        reprog = self.setting(REPROG)
        mode = divert["value"].get(cid, 0) if divert else 0
        stored = actions.device_config(actions.load(), self.id)["buttons"].get(control)
        if stored and actions.divert_mode(stored) == mode:
            action = actions.ACTIONS.get(stored.get("action"))
            if not (action and action.native):
                return stored
        if mode == actions.GESTURES:
            return {"action": "gestures"}
        if mode == actions.DIVERTED:
            return stored or {"action": "none"}
        if reprog and cid in reprog["keys"]:
            choices = reprog["keys"][cid]["choices"]
            current = reprog["value"].get(cid)
            if choices and current != choices[0][0]:
                name = next((n for i, n in choices if i == current), None)
                action = next((a for a in actions.ACTIONS.values() if a.native == name), None)
                if action:
                    return {"action": action.id}
        return {"action": "default"}

    def set_button(self, control, choice):
        data = actions.load()
        config = actions.device_config(data, self.id)
        config["buttons"][control] = choice
        actions.save(data)

        cid = self.cid(control)
        reprog = self.setting(REPROG)
        divert = self.setting(DIVERT)
        action = actions.ACTIONS[choice["action"]]
        steps = []
        if reprog and cid in reprog["keys"]:
            choices = reprog["keys"][cid]["choices"]
            target = next((i for i, n in choices if n == action.native), choices[0][0])
            if reprog["value"].get(cid) != target:
                steps.append((REPROG, cid, target))
        if divert and cid in divert["keys"]:
            mode = actions.divert_mode(choice)
            if divert["value"].get(cid) != mode:
                steps.append((DIVERT, cid, mode))

        def run_steps():
            if steps:
                name, key, value = steps.pop(0)
                self.set_key(name, key, value, run_steps)
            else:
                self.client.reload_actions()
                self.update(self.info)

        run_steps()

    def set_gesture(self, direction, choice):
        data = actions.load()
        actions.device_config(data, self.id)["gestures"][direction] = choice
        actions.save(data)
        self.client.reload_actions()
        self.update(self.info)

    def set_gesture_preset(self, preset):
        data = actions.load()
        actions.device_config(data, self.id)["gestures"] = {d: {"action": a} for d, a in GESTURE_PRESETS[preset].items()}
        actions.save(data)
        self.client.reload_actions()
        self.update(self.info)

    def gestures(self):
        return actions.device_config(actions.load(), self.id)["gestures"]

    # ------------------------------------------------------------ thumb wheel

    def thumbwheel_mode(self):
        mode = actions.device_config(actions.load(), self.id).get("thumbwheel", "hscroll")
        diverted = (self.setting("thumb-scroll-mode") or {}).get("value")
        return mode if diverted or mode == "hscroll" else "hscroll"

    def set_thumbwheel_mode(self, mode):
        data = actions.load()
        actions.device_config(data, self.id)["thumbwheel"] = mode
        actions.save(data)
        self.client.reload_actions()
        if self.setting("thumb-scroll-mode"):
            self.set("thumb-scroll-mode", mode != "hscroll")


def _scrolled(child):
    return Gtk.ScrolledWindow(child=child, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)


class ButtonsPage(Gtk.Box):
    def __init__(self, device):
        super().__init__()
        self.device = device
        self._selected = None

        self.split = Adw.OverlaySplitView(sidebar_position=Gtk.PackType.END, show_sidebar=False, max_sidebar_width=380, min_sidebar_width=320)
        self.split.set_hexpand(True)
        self.append(self.split)

        controls = {b: actions.BUTTON_LABELS[b] for b in device.buttons()}
        if device.setting("thumb-scroll-mode"):
            controls[THUMB_WHEEL] = "Roda do polegar"

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["canvas-page"])
        if is_mx_master(device.info):
            self.canvas = MouseCanvas(controls, self._open)
            content.append(self.canvas)
            hint = "Clique em um ponto do mouse para personalizar"
        else:
            self.canvas = None
            group = Adw.PreferencesGroup(title="Botões")
            self._rows = {}
            for control, title in controls.items():
                row = Adw.ActionRow(title=title, activatable=True)
                row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
                row.connect("activated", lambda _r, c=control: self._open(c))
                group.add(row)
                self._rows[control] = row
            page = Adw.PreferencesPage()
            page.add(group)
            content.append(page)
            hint = "Escolha um botão para personalizar"
        content.append(Gtk.Label(label=hint, css_classes=["dim-label", "caption"], margin_bottom=18))
        self.split.set_content(content)

        self._panel_title = Adw.WindowTitle()
        close = Gtk.Button(icon_name="window-close-symbolic", css_classes=["flat", "circular"])
        close.connect("clicked", lambda _b: self._close())
        header = Adw.HeaderBar(show_start_title_buttons=False, show_end_title_buttons=False, show_back_button=False, title_widget=self._panel_title)
        header.pack_end(close)
        self._panel_body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel = Adw.ToolbarView(content=_scrolled(self._panel_body), css_classes=["action-panel"])
        panel.add_top_bar(header)
        self.split.set_sidebar(panel)

        device.listeners.append(self.refresh)
        self.refresh()

    def _close(self):
        self.split.set_show_sidebar(False)
        self._selected = None
        if self.canvas:
            self.canvas.select(None)

    def _label(self, control):
        if control == THUMB_WHEEL:
            return actions.THUMB_WHEEL_MODES[self.device.thumbwheel_mode()][0]
        return actions.describe(self.device.current_choice(control))

    def refresh(self):
        for control in list(actions.BUTTON_LABELS) + [THUMB_WHEEL]:
            if self.canvas:
                self.canvas.set_value(control, self._label(control))
            elif control in getattr(self, "_rows", {}):
                self._rows[control].set_subtitle(self._label(control))
        if self._selected:
            self._fill_panel(self._selected)

    def _open(self, control):
        self._selected = control
        if self.canvas:
            self.canvas.select(control)
        self._fill_panel(control)
        self.split.set_show_sidebar(True)

    def _fill_panel(self, control):
        while child := self._panel_body.get_first_child():
            self._panel_body.remove(child)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, margin_top=12, margin_bottom=24, margin_start=16, margin_end=16)
        if control == THUMB_WHEEL:
            self._panel_title.set_title("Roda do polegar")
            body.append(self._thumbwheel_panel())
        else:
            self._panel_title.set_title(actions.BUTTON_LABELS[control])
            choice = self.device.current_choice(control)
            self._panel_title.set_subtitle(actions.describe(choice))
            body.append(
                ActionList(
                    self.device.allowed_actions(control),
                    choice,
                    lambda c, ctl=control: self.device.set_button(ctl, c),
                    self,
                )
            )
        self._panel_body.append(body)

    def _thumbwheel_panel(self):
        current = self.device.thumbwheel_mode()
        self._panel_title.set_subtitle(actions.THUMB_WHEEL_MODES[current][0])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        group = Adw.PreferencesGroup(title="Função", description="O que acontece ao girar a roda do polegar")
        for mode, (label, icon, *_rest) in actions.THUMB_WHEEL_MODES.items():
            row = Adw.ActionRow(title=label, activatable=True)
            row.add_prefix(Gtk.Image(icon_name=icon))
            if mode == current:
                row.add_suffix(Gtk.Image(icon_name="object-select-symbolic", css_classes=["accent"]))
            row.connect("activated", lambda _r, m=mode: self.device.set_thumbwheel_mode(m))
            group.add(row)
        box.append(group)
        invert = self.device.setting("thumb-scroll-invert")
        if invert:
            extra = Adw.PreferencesGroup()
            row = Adw.SwitchRow(title="Inverter direção", active=bool(invert["value"]))
            row.connect("notify::active", lambda r, _p: self.device.set("thumb-scroll-invert", r.get_active()))
            extra.add(row)
            box.append(extra)
        return box


class _GestureCard(Gtk.Button):
    def __init__(self, icon, title, on_click):
        super().__init__(css_classes=["gesture-card", "card"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=14, margin_bottom=14, margin_start=12, margin_end=12)
        box.append(Gtk.Image(icon_name=icon, pixel_size=28, css_classes=["accent"]))
        box.append(Gtk.Label(label=title, css_classes=["caption-heading", "dim-label"]))
        self.value = Gtk.Label(css_classes=["heading"], wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=16)
        box.append(self.value)
        self.set_child(box)
        self.connect("clicked", lambda _b: on_click())


class GesturesPage(Gtk.Box):
    """Visual gesture editor: hold the gesture button and move the mouse."""

    _ICONS = {
        "up": "go-up-symbolic",
        "down": "go-down-symbolic",
        "left": "go-previous-symbolic",
        "right": "go-next-symbolic",
        "click": "input-mouse-symbolic",
    }
    _GRID = {"up": (1, 0), "left": (0, 1), "click": (1, 1), "right": (2, 1), "down": (1, 2)}

    def __init__(self, device):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.device = device
        self._updating = False

        clamp = Adw.Clamp(maximum_size=720, margin_top=24, margin_bottom=24, margin_start=16, margin_end=16)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        clamp.set_child(box)
        self.append(_scrolled(clamp))

        self.banner = Adw.Banner(title="O botão de gestos não está no modo gestos", button_label="Ativar gestos")
        self.banner.connect("button-clicked", lambda _b: device.set_button(actions.GESTURE, {"action": "gestures"}))
        self.prepend(self.banner)

        intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        intro.append(Gtk.Label(label="Botão de gestos", css_classes=["title-2"], xalign=0))
        intro.append(
            Gtk.Label(
                label="Segure o botão sob o polegar e mova o mouse em uma direção. Um clique simples, sem mover, também tem sua própria ação.",
                wrap=True,
                xalign=0,
                css_classes=["dim-label"],
            )
        )
        box.append(intro)

        presets = Adw.PreferencesGroup()
        self.preset_row = Adw.ComboRow(title="Predefinição", model=Gtk.StringList.new(list(GESTURE_PRESETS) + ["Personalizado"]))
        self.preset_row.connect("notify::selected", self._preset_selected)
        presets.add(self.preset_row)
        box.append(presets)

        grid = Gtk.Grid(column_spacing=14, row_spacing=14, column_homogeneous=True, row_homogeneous=True, halign=Gtk.Align.CENTER)
        self.cards = {}
        for direction, (col, row) in self._GRID.items():
            title = actions.GESTURE_DIRECTIONS[direction][0]
            card = _GestureCard(self._ICONS[direction], title, lambda d=direction: self._edit(d))
            card.set_size_request(170, 120)
            if direction == "click":
                card.add_css_class("gesture-center")
            grid.attach(card, col, row, 1, 1)
            self.cards[direction] = card
        box.append(grid)

        device.listeners.append(self.refresh)
        self.refresh()

    def refresh(self):
        gestures = self.device.gestures()
        for direction, card in self.cards.items():
            card.value.set_label(actions.describe(gestures.get(direction)))
        self.banner.set_revealed(self.device.current_choice(actions.GESTURE).get("action") != "gestures")
        ids = {d: (g or {}).get("action") for d, g in gestures.items()}
        names = list(GESTURE_PRESETS)
        index = next((i for i, n in enumerate(names) if GESTURE_PRESETS[n] == ids), len(names))
        self._updating = True
        self.preset_row.set_selected(index)
        self._updating = False

    def _preset_selected(self, row, _param):
        if self._updating:
            return
        names = list(GESTURE_PRESETS)
        if row.get_selected() < len(names):
            self.device.set_gesture_preset(names[row.get_selected()])

    def _edit(self, direction):
        allowed = [a.id for a in actions.ACTIONS.values() if a.keys or a.special in ("custom-keys", "command", "none")]
        dialog = Adw.Dialog(title=f"Gesto: {actions.GESTURE_DIRECTIONS[direction][0]}", content_width=420, content_height=620)

        def chosen(choice):
            dialog.close()
            self.device.set_gesture(direction, choice)

        body = Gtk.Box(margin_top=12, margin_bottom=24, margin_start=16, margin_end=16)
        body.append(ActionList(allowed, self.device.gestures().get(direction), chosen, self))
        view = Adw.ToolbarView(content=_scrolled(body))
        view.add_top_bar(Adw.HeaderBar())
        dialog.set_child(view)
        dialog.present(self)


class _ScaleRow(Adw.PreferencesRow):
    """A row with a title, a value label and a slider, written when the user stops dragging."""

    def __init__(self, title, values, fmt, on_change):
        super().__init__(activatable=False)
        self._values = values
        self._fmt = fmt
        self._on_change = on_change
        self._timeout = None
        self._updating = False
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=12, margin_bottom=8, margin_start=12, margin_end=12)
        top = Gtk.Box()
        top.append(Gtk.Label(label=title, hexpand=True, xalign=0))
        self.value_label = Gtk.Label(css_classes=["numeric", "accent"])
        top.append(self.value_label)
        box.append(top)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, len(values) - 1, 1)
        self.scale.set_draw_value(False)
        self.scale.set_round_digits(0)
        self.scale.connect("value-changed", self._changed)
        box.append(self.scale)
        self.set_child(box)

    def set_value(self, value):
        if value in self._values:
            self._updating = True
            self.scale.set_value(self._values.index(value))
            self.value_label.set_label(self._fmt(value))
            self._updating = False

    def _changed(self, scale):
        value = self._values[int(round(scale.get_value()))]
        self.value_label.set_label(self._fmt(value))
        if self._updating:
            return
        if self._timeout:
            GLib.source_remove(self._timeout)
        self._timeout = GLib.timeout_add(350, self._commit, value)

    def _commit(self, value):
        self._timeout = None
        self._on_change(value)
        return False


class PointerPage(Gtk.Box):
    """Point & scroll: DPI, SmartShift, scroll direction and other device settings."""

    def __init__(self, device):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.device = device
        self._updating = False
        self._smartshift_last = 12
        self.page = Adw.PreferencesPage()
        self.append(self.page)
        self._rows = {}

        dpi = device.setting("dpi")
        if dpi:
            group = Adw.PreferencesGroup(title="Ponteiro", description="Velocidade do cursor em pontos por polegada")
            values = [c[0] for c in dpi["choices"]]
            row = _ScaleRow("Velocidade (DPI)", values, lambda v: f"{v} DPI", lambda v: device.set("dpi", v))
            group.add(row)
            self._rows["dpi"] = row
            self.page.add(group)

        wheel = Adw.PreferencesGroup(title="Roda de rolagem")
        if device.setting("smart-shift"):
            row = Adw.SwitchRow(title="SmartShift", subtitle="Libera a roda sozinha quando você rola rápido")
            row.connect("notify::active", self._smartshift_toggled)
            wheel.add(row)
            self._rows["smartshift-on"] = row
            sensitivity = _ScaleRow("Sensibilidade", list(range(1, 50)), lambda v: str(v), self._smartshift_changed)
            wheel.add(sensitivity)
            self._rows["smart-shift"] = sensitivity
        if device.setting("scroll-ratchet"):
            ratchet = device.setting("scroll-ratchet")
            labels = {1: "Rotação livre", 2: "Catraca"}
            row = Adw.ComboRow(title="Modo da roda", model=Gtk.StringList.new([labels.get(i, n) for i, n in ratchet["choices"]]))
            row.connect("notify::selected", lambda r, _p: self._combo_changed("scroll-ratchet", r))
            wheel.add(row)
            self._rows["scroll-ratchet"] = row
        self._toggle(wheel, "hires-smooth-resolution", "Rolagem suave", "Rolagem em alta resolução, pixel a pixel")
        self._toggle(wheel, "hires-smooth-invert", "Rolagem natural", "Inverte a direção da rolagem")
        if wheel.get_first_child() and device.setting("hires-smooth-resolution") or device.setting("smart-shift"):
            self.page.add(wheel)

        if device.setting("thumb-scroll-mode") or device.setting("thumb-scroll-invert"):
            thumb = Adw.PreferencesGroup(title="Roda do polegar")
            modes = list(actions.THUMB_WHEEL_MODES)
            row = Adw.ComboRow(title="Função", model=Gtk.StringList.new([actions.THUMB_WHEEL_MODES[m][0] for m in modes]))
            row.connect("notify::selected", lambda r, _p: None if self._updating else device.set_thumbwheel_mode(modes[r.get_selected()]))
            thumb.add(row)
            self._rows["thumbwheel"] = row
            self._toggle(thumb, "thumb-scroll-invert", "Inverter direção", None)
            self.page.add(thumb)

        others = [s for s in device.info["settings"] if s["name"] not in _HANDLED and s["kind"] != "map"]
        if others:
            group = Adw.PreferencesGroup(title="Outras configurações")
            for s in others:
                if s["kind"] == "toggle":
                    self._toggle(group, s["name"], s["label"], None)
                elif s["kind"] == "choice":
                    row = Adw.ComboRow(title=s["label"], model=Gtk.StringList.new([n for _i, n in s["choices"]]))
                    row.connect("notify::selected", lambda r, _p, n=s["name"]: self._combo_changed(n, r))
                    group.add(row)
                    self._rows[s["name"]] = row
                elif s["kind"] == "range":
                    lo, hi = s["range"]
                    row = Adw.SpinRow.new_with_range(lo, hi, 1)
                    row.set_title(s["label"])
                    row.connect("notify::value", lambda r, _p, n=s["name"]: None if self._updating else device.set(n, int(r.get_value())))
                    group.add(row)
                    self._rows[s["name"]] = row
            self.page.add(group)

        device.listeners.append(self.refresh)
        self.refresh()

    def _toggle(self, group, name, title, subtitle):
        if not self.device.setting(name):
            return
        row = Adw.SwitchRow(title=title)
        if subtitle:
            row.set_subtitle(subtitle)
        row.connect("notify::active", lambda r, _p: None if self._updating else self.device.set(name, r.get_active()))
        group.add(row)
        self._rows[name] = row

    def _combo_changed(self, name, row):
        if self._updating:
            return
        setting = self.device.setting(name)
        self.device.set(name, setting["choices"][row.get_selected()][0])

    def _smartshift_toggled(self, row, _param):
        self._rows["smart-shift"].set_visible(row.get_active())
        if not self._updating:
            self.device.set("smart-shift", self._smartshift_last if row.get_active() else 50)

    def _smartshift_changed(self, value):
        self._smartshift_last = value
        self.device.set("smart-shift", value)

    def refresh(self):
        self._updating = True
        try:
            for name, row in self._rows.items():
                setting = self.device.setting(name)
                if name == "thumbwheel":
                    row.set_selected(list(actions.THUMB_WHEEL_MODES).index(self.device.thumbwheel_mode()))
                elif name == "smartshift-on":
                    value = (self.device.setting("smart-shift") or {}).get("value")
                    on = value is not None and value < 50
                    row.set_active(on)
                    self._rows["smart-shift"].set_visible(on)
                elif setting is None or setting.get("value") is None:
                    continue
                elif name == "smart-shift":
                    if setting["value"] < 50:
                        self._smartshift_last = setting["value"]
                        row.set_value(setting["value"])
                elif isinstance(row, _ScaleRow):
                    row.set_value(setting["value"])
                elif isinstance(row, Adw.SwitchRow):
                    row.set_active(bool(setting["value"]))
                elif isinstance(row, Adw.ComboRow):
                    ids = [c[0] for c in setting["choices"]]
                    if setting["value"] in ids:
                        row.set_selected(ids.index(setting["value"]))
                elif isinstance(row, Adw.SpinRow):
                    row.set_value(setting["value"])
        finally:
            self._updating = False


class EasySwitchPage(Gtk.Box):
    def __init__(self, device):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.device = device
        clamp = Adw.Clamp(maximum_size=760, margin_top=32, margin_bottom=32, margin_start=16, margin_end=16)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.append(Gtk.Label(label="Easy-Switch", css_classes=["title-2"], xalign=0))
        box.append(
            Gtk.Label(
                label="Use o botão embaixo do mouse para alternar entre até três computadores. O canal atual está destacado.",
                wrap=True,
                xalign=0,
                css_classes=["dim-label"],
            )
        )
        self.cards = Gtk.Box(spacing=16, homogeneous=True)
        box.append(self.cards)
        clamp.set_child(box)
        self.append(_scrolled(clamp))
        device.listeners.append(self.refresh)
        self.refresh()

    def refresh(self):
        while child := self.cards.get_first_child():
            self.cards.remove(child)
        setting = self.device.setting("change-host")
        if not setting:
            return
        for host_id, name in setting["choices"]:
            number, _sep, host = name.partition(":")
            current = host_id == setting["value"]
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["card", "host-card"])
            if current:
                card.add_css_class("current")
            card.append(Gtk.Label(label=number, css_classes=["host-number"]))
            card.append(Gtk.Label(label=host or "Livre", css_classes=["heading"], ellipsize=3))
            if current:
                card.append(Gtk.Label(label="Conectado agora", css_classes=["caption", "accent"]))
            else:
                button = Gtk.Button(label="Mudar para este", css_classes=["pill", "small"], halign=Gtk.Align.CENTER)
                button.connect("clicked", lambda _b, h=host_id, n=host or number: self._switch(h, n))
                card.append(button)
            self.cards.append(card)

    def _switch(self, host_id, name):
        dialog = Adw.AlertDialog(
            heading=f"Mudar para {name}?",
            body="O mouse vai se conectar ao outro computador e parar de funcionar aqui até você voltar pelo botão Easy-Switch.",
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("switch", "Mudar")
        dialog.set_response_appearance("switch", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda _d, r: self.device.set("change-host", host_id) if r == "switch" else None)
        dialog.present(self)


class DevicePage(Adw.NavigationPage):
    def __init__(self, device, open_classic):
        super().__init__(title=device.info["name"], tag=device.id)
        self.device = device

        stack = Adw.ViewStack()
        stack.add_titled_with_icon(ButtonsPage(device), "buttons", "Botões", "input-mouse-symbolic")
        if device.cid(actions.GESTURE) is not None and device.setting(DIVERT):
            stack.add_titled_with_icon(GesturesPage(device), "gestures", "Gestos", "input-touchpad-symbolic")
        stack.add_titled_with_icon(PointerPage(device), "pointer", "Apontar e rolar", "find-location-symbolic")
        if device.setting("change-host"):
            stack.add_titled_with_icon(EasySwitchPage(device), "easyswitch", "Easy-Switch", "network-wireless-symbolic")

        header = Adw.HeaderBar(title_widget=Adw.ViewSwitcher(stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE))
        self.battery = Gtk.Box(spacing=6, css_classes=["battery"])
        self.battery_icon = Gtk.Image()
        self.battery_label = Gtk.Label(css_classes=["numeric"])
        self.battery.append(self.battery_icon)
        self.battery.append(self.battery_label)
        header.pack_end(self.battery)

        menu = Gtk.MenuButton(icon_name="view-more-symbolic", tooltip_text="Mais opções")
        popover = Gtk.Popover()
        classic = Gtk.Button(label="Regras avançadas (Solaar clássico)", css_classes=["flat"])
        classic.connect("clicked", lambda _b: (popover.popdown(), open_classic()))
        popover.set_child(classic)
        menu.set_popover(popover)
        header.pack_end(menu)

        self.offline = Adw.Banner(title="Dispositivo desconectado: ligue ou mexa no mouse")
        view = Adw.ToolbarView(content=stack)
        view.add_top_bar(header)
        view.add_top_bar(self.offline)
        switcher_bar = Adw.ViewSwitcherBar(stack=stack)
        view.add_bottom_bar(switcher_bar)
        self.set_child(view)

        device.listeners.append(self.refresh)
        self.refresh()

    def refresh(self):
        info = self.device.info
        icon = battery_icon(info.get("battery"))
        self.battery.set_visible(icon is not None)
        if icon:
            self.battery_icon.set_from_icon_name(icon)
            self.battery_label.set_label(battery_text(info["battery"]))
        self.offline.set_revealed(not info.get("online"))


class DeviceCard(Gtk.Button):
    def __init__(self, info, on_open):
        super().__init__(css_classes=["card", "device-card"])
        self._info = info
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=20, margin_bottom=18, margin_start=18, margin_end=18)
        if is_mx_master(info):
            box.append(MouseThumbnail(130))
        else:
            box.append(Gtk.Image(icon_name="input-mouse-symbolic", pixel_size=96, css_classes=["dim-label"], margin_top=17, margin_bottom=17))
        box.append(Gtk.Label(label=info["name"], css_classes=["title-4"]))
        status = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        icon = battery_icon(info.get("battery"))
        if icon:
            status.append(Gtk.Image(icon_name=icon))
        status.append(
            Gtk.Label(label=battery_text(info.get("battery")) if info.get("online") else "Desconectado", css_classes=["dim-label"])
        )
        box.append(status)
        self.set_child(box)
        self.connect("clicked", lambda _b: on_open(info["id"]))
