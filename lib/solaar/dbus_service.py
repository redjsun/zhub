## Copyright (C) 2026  ZHUB contributors
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

"""D-Bus interface used by the ZHUB GTK4 panel to talk to this service.

All values cross the bus as JSON strings so the panel never needs to import
any of the HID++ code: the service is the only process talking to devices.
"""

import json
import logging

from gi.repository import Gio
from gi.repository import GLib

from logitech_receiver import diversion
from logitech_receiver import settings
from logitech_receiver.common import NamedInt

from solaar.ui.common import ui_async

logger = logging.getLogger(__name__)

OBJECT_PATH = "/io/github/zhub/Service"
INTERFACE = "io.github.zhub.Service1"

_XML = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="ListDevices"><arg type="s" direction="out" name="devices_json"/></method>
    <method name="GetDevice">
      <arg type="s" direction="in" name="device_id"/>
      <arg type="s" direction="out" name="device_json"/>
    </method>
    <method name="SetSetting">
      <arg type="s" direction="in" name="device_id"/>
      <arg type="s" direction="in" name="setting"/>
      <arg type="s" direction="in" name="value_json"/>
      <arg type="s" direction="out" name="device_json"/>
    </method>
    <method name="SetSettingKey">
      <arg type="s" direction="in" name="device_id"/>
      <arg type="s" direction="in" name="setting"/>
      <arg type="s" direction="in" name="key_json"/>
      <arg type="s" direction="in" name="value_json"/>
      <arg type="s" direction="out" name="device_json"/>
    </method>
    <method name="ReloadActions"/>
    <method name="ShowClassicWindow"/>
    <signal name="DeviceChanged"><arg type="s" name="device_json"/></signal>
  </interface>
</node>
"""

_devices = {}  # device id -> Device
_connection = None
_show_classic = None

_KIND_NAMES = {
    settings.Kind.TOGGLE: "toggle",
    settings.Kind.CHOICE: "choice",
    settings.Kind.RANGE: "range",
    settings.Kind.MAP_CHOICE: "map",
}


def device_id(device):
    return str(device.unitId or device.serial or device.path)


def _named(value):
    return [int(value), str(value)]


def _describe_setting(setting):
    kind = _KIND_NAMES.get(setting.kind)
    if kind is None:
        return None
    try:
        value = setting.read()
    except Exception as e:
        logger.warning("%s: could not read %s: %r", setting._device, setting.name, e)
        value = None
    info = {"name": setting.name, "label": setting.label, "description": setting.description, "kind": kind}
    if kind == "toggle":
        info["value"] = bool(value) if value is not None else None
    elif kind == "choice":
        info["choices"] = [_named(c) for c in setting.choices]
        info["value"] = int(value) if value is not None else None
    elif kind == "range":
        info["range"] = list(setting.range)
        info["value"] = int(value) if value is not None else None
    elif kind == "map":
        info["keys"] = {str(int(k)): {"name": str(k), "choices": [_named(c) for c in v]} for k, v in setting.choices.items()}
        info["value"] = {str(int(k)): int(v) for k, v in (value or {}).items()}
    return info


def _describe_device(device):
    battery = None
    if device.battery_info is not None and device.battery_info.level is not None:
        level = device.battery_info.level
        battery = {
            "level": int(level) if not isinstance(level, NamedInt) else None,
            "text": str(level),
            "charging": bool(device.battery_info.charging()),
        }
    info = {
        "id": device_id(device),
        "name": device.name,
        "codename": device.codename,
        "kind": str(device.kind),
        "online": bool(device.online),
        "battery": battery,
        "serial": device.serial,
        "firmware": [str(f.version) for f in (device.firmware or []) if f.version] if device.online else [],
        "settings": [],
    }
    if device.online:
        for s in device.settings or []:
            described = _describe_setting(s)
            if described:
                info["settings"].append(described)
    return info


def _find_choice(choices, value):
    return next((c for c in choices if int(c) == int(value)), None)


def _write(device, name, key, value):
    setting = next((s for s in device.settings if s.name == name), None)
    if setting is None:
        raise ValueError(f"{device.name} has no setting {name}")
    if setting.kind == settings.Kind.TOGGLE:
        result = setting.write(bool(value))
    elif setting.kind == settings.Kind.CHOICE:
        result = setting.write(_find_choice(setting.choices, value))
    elif setting.kind == settings.Kind.RANGE:
        result = setting.write(int(value))
    elif setting.kind == settings.Kind.MAP_CHOICE:
        k = next(c for c in setting.choices if int(c) == int(key))
        result = setting.write_key_value(k, _find_choice(setting.choices[k], value))
    else:
        raise ValueError(f"setting {name} cannot be changed from ZHUB")
    if result is None:
        raise RuntimeError(f"{device.name}: failed to write {name}")
    if device.persister:  # unlock the setting in the classic Solaar window too
        device.persister.set_sensitivity(name, True)


def _reply(invocation, function, *args):
    """Run function in the background task thread and return its JSON result over D-Bus."""

    def run():
        try:
            result = function(*args)
            variant = GLib.Variant("(s)", (json.dumps(result),))
            GLib.idle_add(invocation.return_value, variant)
        except Exception as e:
            logger.exception("D-Bus call failed")
            GLib.idle_add(invocation.return_dbus_error, f"{INTERFACE}.Error", str(e))

    ui_async(run)


def _get_device(dev_id):
    device = _devices.get(dev_id)
    if device is None:
        raise KeyError(f"unknown device {dev_id}")
    return device


def _set_and_describe(dev_id, name, key, value):
    device = _get_device(dev_id)
    _write(device, name, key, value)
    info = _describe_device(device)
    GLib.idle_add(_emit, info)
    return info


def _method_call(_conn, _sender, _path, _iface, method, params, invocation):
    args = params.unpack()
    if method == "ListDevices":
        _reply(invocation, lambda: [_describe_device(d) for d in list(_devices.values())])
    elif method == "GetDevice":
        _reply(invocation, lambda i: _describe_device(_get_device(i)), args[0])
    elif method == "SetSetting":
        _reply(invocation, _set_and_describe, args[0], args[1], None, json.loads(args[2]))
    elif method == "SetSettingKey":
        _reply(invocation, _set_and_describe, args[0], args[1], json.loads(args[2]), json.loads(args[3]))
    elif method == "ReloadActions":
        diversion.load_config_rule_file()
        invocation.return_value(None)
    elif method == "ShowClassicWindow":
        if _show_classic:
            _show_classic()
        invocation.return_value(None)


def _emit(info):
    if _connection is not None:
        _connection.emit_signal(None, OBJECT_PATH, INTERFACE, "DeviceChanged", GLib.Variant("(s)", (json.dumps(info),)))
    return False


def device_changed(device):
    """Called from the UI thread on every device status change."""
    if device is None or device.kind is None:  # receivers are not shown in ZHUB
        return
    _devices[device_id(device)] = device

    def run():
        try:
            info = _describe_device(device)
        except Exception:
            logger.exception("failed to describe %s", device)
            return
        GLib.idle_add(_emit, info)

    ui_async(run)


def register(application, show_classic):
    global _connection, _show_classic
    _show_classic = show_classic
    _connection = application.get_dbus_connection()
    if _connection is None:
        logger.warning("no D-Bus connection, ZHUB panel will not be able to reach the service")
        return
    node = Gio.DBusNodeInfo.new_for_xml(_XML)
    _connection.register_object(OBJECT_PATH, node.interfaces[0], _method_call, None, None)
    logger.info("ZHUB D-Bus service exported at %s", OBJECT_PATH)
