from __future__ import annotations

from typing import Any

from .models import Device


def _as_bool(value: Any) -> bool:
    return bool(value)


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_text(*values: Any) -> str:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return ""


def extract_passive_rows(netdev_payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = netdev_payload.get("data", {})
    passive = data.get("passive", [])
    if not isinstance(passive, list):
        return []
    return [row for row in passive if isinstance(row, dict)]


def build_device(list_row: dict[str, Any], detail_payload: dict[str, Any]) -> Device:
    vars_ = detail_payload.get("data", {}).get("vars", {})
    detail_dev = vars_.get("dev", {}) if isinstance(vars_, dict) else {}
    if not isinstance(detail_dev, dict):
        detail_dev = {}

    uid = _first_text(detail_dev.get("UID"), list_row.get("UID"))
    name_info = detail_dev.get("name", {})
    if not isinstance(name_info, dict):
        name_info = {}
    ipv4 = detail_dev.get("ipv4", {})
    if not isinstance(ipv4, dict):
        ipv4 = {}
    current_ipv4 = ipv4.get("current", {})
    if not isinstance(current_ipv4, dict):
        current_ipv4 = {}
    list_ipv4 = list_row.get("ipv4", {})
    if not isinstance(list_ipv4, dict):
        list_ipv4 = {}

    kisi = detail_dev.get("netAccess", {}).get("kisi", {})
    if not isinstance(kisi, dict):
        kisi = {}
    profiles = kisi.get("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
    selected_profile = _first_text(profiles.get("selected"))
    profile_name = selected_profile
    for profile in profiles.get("list", []) if isinstance(profiles.get("list"), list) else []:
        if isinstance(profile, dict) and profile.get("value") == selected_profile:
            profile_name = _first_text(profile.get("text"), selected_profile)
            break

    options = list_row.get("options", {})
    if not isinstance(options, dict):
        options = {}
    page = detail_dev.get("page", {})
    if not isinstance(page, dict):
        page = {}
    reset = detail_dev.get("reset", {})
    if not isinstance(reset, dict):
        reset = {}

    return Device(
        uid=uid,
        name=_first_text(name_info.get("displayName"), list_row.get("name"), uid),
        mac=_first_text(detail_dev.get("mac"), list_row.get("mac")),
        ip=_first_text(current_ipv4.get("ip"), list_ipv4.get("ip")),
        dev_type=_first_text(detail_dev.get("devType"), list_row.get("type")),
        state=_first_text(detail_dev.get("state"), "UNKNOWN"),
        filter_profile=profile_name,
        filter_profile_id=selected_profile,
        deleteable=_as_bool(options.get("deleteable")),
        reset_show=_as_bool(reset.get("show")),
        page_editable=_as_bool(page.get("editable")),
        lastused=_as_int(detail_dev.get("lastused")),
        detail=detail_dev,
        list_row=list_row,
    )


def sort_devices(devices: list[Device]) -> list[Device]:
    def key(device: Device) -> tuple[int, int, str]:
        if device.lastused is None:
            return (1, 0, device.name.casefold())
        return (0, device.lastused, device.name.casefold())

    return sorted(devices, key=key)
