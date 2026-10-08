## Copyright (C) 2026  ZHUB contributors
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""ZHUB panel: a GTK4 + libadwaita front end for the ZHUB service."""

import logging
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
try:
    gi.require_foreign("cairo")
except ImportError:
    sys.exit("ZHUB precisa do pacote python3-gi-cairo: sudo apt install python3-gi-cairo")

from gi.repository import Adw  # NOQA: E402
from gi.repository import Gdk  # NOQA: E402
from gi.repository import Gtk  # NOQA: E402

from .client import Client  # NOQA: E402
from .pages import DeviceCard  # NOQA: E402
from .pages import DeviceController  # NOQA: E402
from .pages import DevicePage  # NOQA: E402

APP_ID = "io.github.zhub.Panel"
VERSION = "0.1.0"

logger = logging.getLogger(__name__)


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="ZHUB", default_width=1100, default_height=720)
        self.set_size_request(380, 500)
        self.devices = {}  # id -> DeviceController
        self.toasts = Adw.ToastOverlay()
        self.nav = Adw.NavigationView()
        self.toasts.set_child(self.nav)
        self.set_content(self.toasts)

        self.flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=True,
            max_children_per_line=4,
            column_spacing=18,
            row_spacing=18,
            valign=Gtk.Align.START,
            halign=Gtk.Align.CENTER,
        )
        self.status = Adw.StatusPage(
            icon_name="input-mouse-symbolic",
            title="Procurando dispositivos…",
            description="Iniciando o serviço do ZHUB",
        )
        self.home_stack = Gtk.Stack()
        self.home_stack.add_named(self.status, "status")
        home_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24, margin_top=36, margin_bottom=36, margin_start=24, margin_end=24)
        home_box.append(Gtk.Label(label="Seus dispositivos", css_classes=["title-1"], xalign=0))
        home_box.append(self.flow)
        self.home_stack.add_named(Gtk.ScrolledWindow(child=Adw.Clamp(maximum_size=1000, child=home_box)), "devices")

        header = Adw.HeaderBar(title_widget=Adw.WindowTitle(title="ZHUB", subtitle="Painel de dispositivos"))
        about = Gtk.Button(icon_name="help-about-symbolic", tooltip_text="Sobre o ZHUB")
        about.connect("clicked", self._about)
        header.pack_end(about)
        home_view = Adw.ToolbarView(content=self.home_stack)
        home_view.add_top_bar(header)
        self.nav.add(Adw.NavigationPage(title="ZHUB", tag="home", child=home_view))

        self.client = Client(self._ready, self._device_changed, self._lost)

    def toast(self, message):
        self.toasts.add_toast(Adw.Toast(title=message, timeout=4))

    def _ready(self):
        self.status.set_description("Conectado ao serviço, lendo dispositivos…")
        self.client.list_devices(self._got_devices, self._list_failed)

    def _list_failed(self, message):
        self.status.set_title("Não foi possível ler os dispositivos")
        self.status.set_description(message)

    def _lost(self):
        self.status.set_title("Serviço do ZHUB parado")
        self.status.set_description("Abra o ZHUB de novo para reiniciar o serviço.")
        self.home_stack.set_visible_child_name("status")

    def _got_devices(self, infos):
        for info in infos:
            self._device_changed(info, rebuild=False)
        self._rebuild_home()

    def _device_changed(self, info, rebuild=True):
        controller = self.devices.get(info["id"])
        if controller is None:
            self.devices[info["id"]] = DeviceController(self.client, info, self.toast)
        else:
            had_settings = bool(controller.info.get("settings"))
            controller.update(info if info.get("settings") or not had_settings else {**info, "settings": controller.info["settings"]})
        if rebuild:
            self._rebuild_home()

    def _rebuild_home(self):
        while child := self.flow.get_first_child():
            self.flow.remove(child)
        for controller in sorted(self.devices.values(), key=lambda c: (not c.info.get("online"), c.info["name"])):
            self.flow.append(DeviceCard(controller.info, self._open_device))
        if self.devices:
            self.home_stack.set_visible_child_name("devices")
        else:
            self.status.set_title("Nenhum dispositivo encontrado")
            self.status.set_description("Ligue o mouse ou mexa nele para acordá-lo.")
            self.home_stack.set_visible_child_name("status")

    def _open_device(self, device_id):
        controller = self.devices[device_id]
        if not controller.info.get("settings"):
            self.toast("O dispositivo está desconectado: ligue o mouse e tente de novo")
            return
        page = self.nav.find_page(device_id)
        if page is None:
            page = DevicePage(controller, self.client.show_classic_window)
        self.nav.push(page)

    def _about(self, _button):
        about = Adw.AboutDialog(
            application_name="ZHUB",
            application_icon="input-mouse",
            developer_name="yzabella",
            version=VERSION,
            comments="Painel para personalizar mouses e teclados Logitech no Linux.\n\n"
            "Baseado no Solaar. Projeto não oficial, sem afiliação com a Logitech.",
            website="https://github.com/pwr-Solaar/Solaar",
            license_type=Gtk.License.GPL_2_0,
        )
        about.add_credit_section("Baseado em", ["Solaar https://github.com/pwr-Solaar/Solaar"])
        about.present(self)


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_startup(self):
        Adw.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_path(os.path.join(os.path.dirname(__file__), "style.css"))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        window = self.get_active_window() or Window(self)
        window.present()


def main():
    logging.basicConfig(level=logging.INFO if "-v" in sys.argv else logging.WARNING)
    return Application().run([a for a in sys.argv if a != "-v"])
