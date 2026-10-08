## Copyright (C) 2026  ZHUB contributors
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

"""Talks to the ZHUB service (the Solaar fork) over D-Bus."""

import json
import logging
import os
import subprocess
import sys

from gi.repository import Gio
from gi.repository import GLib

logger = logging.getLogger(__name__)

BUS_NAME = "io.github.zhub.Service"
OBJECT_PATH = "/io/github/zhub/Service"
INTERFACE = "io.github.zhub.Service1"

_SERVICE_BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bin", "zhub-service")


class Client:
    def __init__(self, on_ready, on_device_changed, on_lost):
        self._on_ready = on_ready
        self._on_device_changed = on_device_changed
        self._on_lost = on_lost
        self._proxy = None
        self._started_service = False
        self._watch = Gio.bus_watch_name(
            Gio.BusType.SESSION, BUS_NAME, Gio.BusNameWatcherFlags.NONE, self._appeared, self._vanished
        )

    def _appeared(self, _conn, _name, _owner):
        self._proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES, None, BUS_NAME, OBJECT_PATH, INTERFACE, None
        )
        self._proxy.connect("g-signal", self._signal)
        self._on_ready()

    def _vanished(self, _conn, _name):
        self._proxy = None
        if not self._started_service:
            self._started_service = True
            self.start_service()
        else:
            self._on_lost()

    def start_service(self):
        logger.info("starting %s", _SERVICE_BIN)
        subprocess.Popen(
            [sys.executable, _SERVICE_BIN, "--window=hide"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def _signal(self, _proxy, _sender, signal, params):
        if signal == "DeviceChanged":
            self._on_device_changed(json.loads(params.unpack()[0]))

    def _call(self, method, args, callback=None, error=None):
        if self._proxy is None:
            if error:
                error("O serviço do ZHUB não está rodando")
            return

        def done(proxy, result):
            try:
                value = proxy.call_finish(result).unpack()
            except GLib.Error as e:
                message = Gio.DBusError.strip_remote_error(e) if Gio.DBusError.is_remote_error(e) else e.message
                logger.warning("%s failed: %s", method, message)
                if error:
                    error(message)
                return
            if callback:
                callback(json.loads(value[0]) if value else None)

        self._proxy.call(method, args, Gio.DBusCallFlags.NONE, 30000, None, done)

    def list_devices(self, callback, error=None):
        self._call("ListDevices", None, callback, error)

    def set_setting(self, device_id, name, value, callback=None, error=None):
        self._call("SetSetting", GLib.Variant("(sss)", (device_id, name, json.dumps(value))), callback, error)

    def set_setting_key(self, device_id, name, key, value, callback=None, error=None):
        args = GLib.Variant("(ssss)", (device_id, name, json.dumps(key), json.dumps(value)))
        self._call("SetSettingKey", args, callback, error)

    def reload_actions(self):
        self._call("ReloadActions", None)

    def show_classic_window(self):
        self._call("ShowClassicWindow", None)
