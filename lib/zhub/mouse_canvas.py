## Copyright (C) 2026  ZHUB contributors
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Interactive top view of an MX Master style mouse with clickable hotspots."""

import math

from gi.repository import Adw
from gi.repository import Graphene
from gi.repository import Gsk
from gi.repository import Gtk

from . import actions

# Design space: the whole canvas is CANVAS_W x CANVAS_H, the mouse body is
# drawn in its own BODY_W x BODY_H box centred on the canvas.
CANVAS_W, CANVAS_H = 720, 440
BODY_W, BODY_H = 230, 360
BODY_X = (CANVAS_W - BODY_W) / 2
BODY_Y = (CANVAS_H - BODY_H) / 2

THUMB_WHEEL = "thumbwheel"

# control -> (hotspot x, hotspot y in body space, side, callout y in canvas space)
HOTSPOTS = {
    actions.MIDDLE: (122, 74, "right", 70),
    actions.SMART_SHIFT: (122, 132, "right", 150),
    THUMB_WHEEL: (30, 176, "left", 120),
    actions.FORWARD: (25, 218, "left", 190),
    actions.BACK: (22, 243, "left", 260),
    actions.GESTURE: (42, 290, "left", 330),
}

CALLOUT_GAP = 70  # horizontal distance between the body and the callouts


def body_path(cr):
    cr.move_to(120, 6)
    cr.curve_to(170, 4, 200, 25, 205, 60)
    cr.curve_to(210, 110, 222, 170, 216, 232)
    cr.curve_to(210, 312, 176, 352, 128, 354)
    cr.curve_to(78, 356, 22, 332, 9, 290)
    cr.curve_to(1, 262, 0, 236, 9, 210)
    cr.curve_to(16, 186, 30, 170, 35, 150)
    cr.curve_to(38, 120, 32, 90, 40, 60)
    cr.curve_to(50, 25, 80, 6, 120, 6)
    cr.close_path()


def _rounded_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _linear(cairo, x0, y0, x1, y1, stops):
    gradient = cairo.LinearGradient(x0, y0, x1, y1)
    for offset, (r, g, b, *a) in stops:
        gradient.add_color_stop_rgba(offset, r, g, b, a[0] if a else 1)
    return gradient


def draw_mouse(cr, dark, highlight=None):
    """Draw the mouse in body space (0..BODY_W, 0..BODY_H)."""
    import cairo

    # soft shadow
    shadow = cairo.RadialGradient(118, 200, 40, 118, 200, 200)
    shadow.add_color_stop_rgba(0, 0, 0, 0, 0.35 if dark else 0.22)
    shadow.add_color_stop_rgba(1, 0, 0, 0, 0)
    cr.save()
    cr.translate(8, 14)
    cr.scale(1, 1.02)
    body_path(cr)
    cr.set_source(shadow)
    cr.fill()
    cr.restore()

    # body
    body_path(cr)
    cr.set_source(
        _linear(cairo, 0, 0, BODY_W, BODY_H, [(0, (0.36, 0.37, 0.40)), (0.55, (0.22, 0.23, 0.25)), (1, (0.15, 0.15, 0.17))])
    )
    cr.fill_preserve()
    cr.set_source_rgba(1, 1, 1, 0.10)
    cr.set_line_width(1.5)
    cr.stroke()

    # palm rest sheen
    cr.save()
    body_path(cr)
    cr.clip()
    sheen = cairo.RadialGradient(150, 250, 10, 150, 250, 150)
    sheen.add_color_stop_rgba(0, 1, 1, 1, 0.10)
    sheen.add_color_stop_rgba(1, 1, 1, 1, 0)
    cr.set_source(sheen)
    cr.paint()

    # buttons area, slightly lighter, ending in a soft curve
    cr.move_to(0, 0)
    cr.line_to(BODY_W, 0)
    cr.line_to(BODY_W, 150)
    cr.curve_to(170, 168, 80, 170, 0, 150)
    cr.close_path()
    cr.set_source(_linear(cairo, 0, 0, 0, 170, [(0, (1, 1, 1, 0.09)), (1, (1, 1, 1, 0.02))]))
    cr.fill()

    # seams between the buttons and the palm rest
    cr.set_line_width(1.4)
    cr.set_source_rgba(0, 0, 0, 0.55)
    cr.move_to(36, 152)
    cr.curve_to(80, 172, 170, 170, 212, 148)
    cr.stroke()
    cr.move_to(122, 6)
    cr.line_to(122, 36)
    cr.move_to(122, 142)
    cr.line_to(122, 164)
    cr.stroke()
    cr.restore()

    # scroll wheel channel and metal wheel
    _rounded_rect(cr, 108, 34, 28, 84, 12)
    cr.set_source_rgba(0, 0, 0, 0.6)
    cr.fill()
    _rounded_rect(cr, 112, 40, 20, 72, 9)
    cr.set_source(
        _linear(cairo, 112, 0, 132, 0, [(0, (0.45, 0.47, 0.50)), (0.5, (0.86, 0.87, 0.89)), (1, (0.42, 0.44, 0.47))])
    )
    cr.fill()
    cr.set_line_width(1)
    cr.set_source_rgba(0, 0, 0, 0.28)
    for y in range(44, 110, 4):
        cr.move_to(113, y)
        cr.line_to(131, y)
    cr.stroke()

    # SmartShift button
    _rounded_rect(cr, 113, 123, 18, 18, 5)
    cr.set_source(_linear(cairo, 0, 123, 0, 141, [(0, (0.30, 0.31, 0.34)), (1, (0.18, 0.19, 0.21))]))
    cr.fill_preserve()
    cr.set_source_rgba(1, 1, 1, 0.18)
    cr.stroke()

    # thumb wheel peeking out on the left flank
    _rounded_rect(cr, 20, 150, 18, 54, 7)
    cr.set_source(_linear(cairo, 20, 0, 38, 0, [(0, (0.30, 0.31, 0.34)), (0.5, (0.62, 0.64, 0.67)), (1, (0.25, 0.26, 0.28))]))
    cr.fill()
    cr.set_source_rgba(0, 0, 0, 0.35)
    for y in range(154, 202, 4):
        cr.move_to(21, y)
        cr.line_to(37, y)
    cr.stroke()

    # forward / back buttons
    for x, y in ((14, 208), (11, 233)):
        _rounded_rect(cr, x, y, 22, 20, 8)
        cr.set_source(_linear(cairo, 0, y, 0, y + 20, [(0, (0.40, 0.41, 0.44)), (1, (0.24, 0.25, 0.27))]))
        cr.fill_preserve()
        cr.set_source_rgba(0, 0, 0, 0.5)
        cr.stroke()

    # gesture button under the thumb
    cr.save()
    cr.translate(42, 290)
    cr.scale(1.6, 1)
    cr.arc(0, 0, 14, 0, 2 * math.pi)
    cr.restore()
    cr.set_source_rgba(1, 1, 1, 0.07)
    cr.fill_preserve()
    cr.set_source_rgba(0, 0, 0, 0.4)
    cr.stroke()

    # status LED
    cr.arc(122, 330, 3, 0, 2 * math.pi)
    cr.set_source_rgba(0.35, 0.85, 0.45, 0.85)
    cr.fill()

    if highlight in HOTSPOTS:
        x, y, *_ = HOTSPOTS[highlight]
        glow = cairo.RadialGradient(x, y, 2, x, y, 34)
        glow.add_color_stop_rgba(0, 0.21, 0.52, 0.89, 0.55)
        glow.add_color_stop_rgba(1, 0.21, 0.52, 0.89, 0)
        cr.set_source(glow)
        cr.arc(x, y, 34, 0, 2 * math.pi)
        cr.fill()


class MouseThumbnail(Gtk.DrawingArea):
    """Small, non interactive drawing for device cards."""

    def __init__(self, size=120):
        super().__init__(content_width=size, content_height=size)
        self.set_draw_func(self._draw)

    def _draw(self, _area, cr, width, height):
        scale = min(width / BODY_W, height / BODY_H) * 0.92
        cr.translate((width - BODY_W * scale) / 2, (height - BODY_H * scale) / 2)
        cr.scale(scale, scale)
        draw_mouse(cr, Adw.StyleManager.get_default().get_dark())


class _Callout(Gtk.Button):
    def __init__(self, title):
        super().__init__(css_classes=["callout", "flat"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.title = Gtk.Label(label=title, xalign=0, css_classes=["callout-title"])
        self.value = Gtk.Label(xalign=0, css_classes=["callout-value"], ellipsize=3, max_width_chars=22)
        box.append(self.title)
        box.append(self.value)
        self.set_child(box)


class MouseCanvas(Gtk.Widget):
    """The mouse drawing with a hotspot and a callout for every customizable control."""

    def __init__(self, controls, on_select):
        super().__init__(hexpand=True, vexpand=True)
        self._on_select = on_select
        self._selected = None
        self._items = {}  # control -> (dot, callout)
        for control, title in controls.items():
            if control not in HOTSPOTS:
                continue
            dot = Gtk.Button(css_classes=["hotspot"], tooltip_text=title)
            dot.set_child(Gtk.Image(icon_name="list-add-symbolic", pixel_size=12))
            callout = _Callout(title)
            for widget in (dot, callout):
                widget.connect("clicked", lambda _w, c=control: self.select(c, notify=True))
                widget.set_parent(self)
            self._items[control] = (dot, callout)
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_: self.queue_draw())

    def set_value(self, control, text):
        if control in self._items:
            self._items[control][1].value.set_label(text)

    def select(self, control, notify=False):
        self._selected = control
        for c, (dot, callout) in self._items.items():
            for widget in (dot, callout):
                if c == control:
                    widget.add_css_class("selected")
                else:
                    widget.remove_css_class("selected")
        self.queue_draw()
        if notify and control is not None:
            self._on_select(control)

    def do_dispose(self):
        for dot, callout in self._items.values():
            dot.unparent()
            callout.unparent()
        self._items = {}

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            return 560, CANVAS_W, -1, -1
        return 380, CANVAS_H, -1, -1

    def _transform(self):
        width, height = self.get_width(), self.get_height()
        scale = min(width / CANVAS_W, height / CANVAS_H, 1.4)
        ox = (width - CANVAS_W * scale) / 2
        oy = (height - CANVAS_H * scale) / 2
        return scale, ox, oy

    def _hotspot_point(self, control):
        """Hotspot centre and callout anchor, in widget coordinates."""
        scale, ox, oy = self._transform()
        x, y, side, cy = HOTSPOTS[control]
        hx = ox + (BODY_X + x) * scale
        hy = oy + (BODY_Y + y) * scale
        if side == "left":
            ax = ox + (BODY_X - CALLOUT_GAP) * scale
        else:
            ax = ox + (BODY_X + BODY_W + CALLOUT_GAP) * scale
        ay = oy + cy * scale
        return hx, hy, ax, ay, side

    def do_size_allocate(self, width, height, baseline):
        for control, (dot, callout) in self._items.items():
            hx, hy, ax, ay, side = self._hotspot_point(control)
            _min, dot_w, *_ = dot.measure(Gtk.Orientation.HORIZONTAL, -1)
            _min, dot_h, *_ = dot.measure(Gtk.Orientation.VERTICAL, -1)
            self._place(dot, hx - dot_w / 2, hy - dot_h / 2, dot_w, dot_h)
            _min, cw, *_ = callout.measure(Gtk.Orientation.HORIZONTAL, -1)
            _min, ch, *_ = callout.measure(Gtk.Orientation.VERTICAL, cw)
            cx = ax - cw if side == "left" else ax
            self._place(callout, max(0, min(cx, width - cw)), ay - ch / 2, cw, ch)

    @staticmethod
    def _place(widget, x, y, w, h):
        point = Graphene.Point()
        point.init(x, y)
        widget.allocate(int(w), int(h), -1, Gsk.Transform().translate(point))

    def do_snapshot(self, snapshot):
        width, height = self.get_width(), self.get_height()
        rect = Graphene.Rect()
        rect.init(0, 0, width, height)
        cr = snapshot.append_cairo(rect)
        scale, ox, oy = self._transform()
        dark = Adw.StyleManager.get_default().get_dark()

        # leader lines from hotspots to callouts
        for control in self._items:
            hx, hy, ax, ay, side = self._hotspot_point(control)
            elbow = ax + (24 if side == "left" else -24) * scale
            selected = control == self._selected
            if selected:
                cr.set_source_rgba(0.21, 0.52, 0.89, 0.95)
            else:
                cr.set_source_rgba(*((1, 1, 1, 0.28) if dark else (0, 0, 0, 0.25)))
            cr.set_line_width(2 if selected else 1.2)
            cr.move_to(hx, hy)
            cr.line_to(elbow, ay)
            cr.line_to(ax, ay)
            cr.stroke()

        cr.save()
        cr.translate(ox + BODY_X * scale, oy + BODY_Y * scale)
        cr.scale(scale, scale)
        draw_mouse(cr, dark, self._selected)
        cr.restore()

        for dot, callout in self._items.values():
            self.snapshot_child(callout, snapshot)
            self.snapshot_child(dot, snapshot)
