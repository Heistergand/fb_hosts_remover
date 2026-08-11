from datetime import datetime, timedelta

from fritzbox_passive_tui.parser import build_device, extract_passive_rows, sort_devices


def row(uid: str, name: str = "dev", deleteable: bool = True) -> dict:
    return {
        "UID": uid,
        "name": name,
        "mac": "AA:BB",
        "ipv4": {"ip": "192.168.178.10"},
        "options": {"deleteable": deleteable},
    }


def detail(uid: str, lastused: str | None = "1700000000", profile: str = "filtprof1") -> dict:
    dev = {
        "UID": uid,
        "mac": "AA:BB",
        "devType": "lan",
        "state": "INACTIVE",
        "name": {"displayName": "Device"},
        "ipv4": {"current": {"ip": "192.168.178.10"}},
        "page": {"editable": True},
        "reset": {"show": True},
        "netAccess": {
            "kisi": {
                "profiles": {
                    "selected": profile,
                    "list": [{"value": profile, "text": "Standard"}],
                }
            }
        },
    }
    if lastused is not None:
        dev["lastused"] = lastused
    return {"data": {"vars": {"dev": dev}}}


def test_extract_passive_rows() -> None:
    payload = {"data": {"passive": [row("a"), "bad", row("b")]}}
    assert [r["UID"] for r in extract_passive_rows(payload)] == ["a", "b"]


def test_build_device() -> None:
    device = build_device(row("x"), detail("x"))
    assert device.uid == "x"
    assert device.name == "Device"
    assert device.filter_profile == "Standard"
    assert device.removable is True
    assert device.lastused == 1700000000


def test_sort_devices_oldest_then_unknown_then_name() -> None:
    devices = [
        build_device(row("new", "new"), detail("new", "1800000000")),
        build_device(row("unknown", "unknown"), detail("unknown", None)),
        build_device(row("old", "old"), detail("old", "1700000000")),
    ]
    assert [d.uid for d in sort_devices(devices)] == ["old", "new", "unknown"]


def test_autoselect_rule_shape() -> None:
    old_ts = int((datetime.now() - timedelta(days=100)).timestamp())
    new_ts = int((datetime.now() - timedelta(days=10)).timestamp())
    old = build_device(row("old"), detail("old", str(old_ts)))
    new = build_device(row("new"), detail("new", str(new_ts)))
    unknown = build_device(row("unknown"), detail("unknown", None))
    cutoff = datetime.now() - timedelta(days=90)
    marked = [d.uid for d in [old, new, unknown] if d.removable and d.last_seen is not None and d.last_seen < cutoff]
    assert marked == ["old"]
