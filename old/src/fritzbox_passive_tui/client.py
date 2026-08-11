from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import requests

from .auth import login_response
from .models import Device, ResetResult
from .parser import build_device, extract_passive_rows, sort_devices
from .requests import build_reset_payload

TIMEOUT = 180


class FritzBoxError(RuntimeError):
    pass


class FritzBoxClient:
    def __init__(self, base_url: str = "https://fritz.box", timeout: int = TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.sid: str | None = None
        self.session = requests.Session()
        self.session.verify = False

    def _url(self, path: str) -> str:
        return self.base_url + path

    def login(self, username: str, password: str) -> None:
        response = self.session.get(self._url("/login_sid.lua?version=2"), timeout=self.timeout)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        sid = root.findtext("SID") or ""
        if sid != "0000000000000000":
            self.sid = sid
            return

        challenge = root.findtext("Challenge") or ""
        payload: dict[str, str] = {"response": login_response(challenge, password)}
        if username:
            payload["username"] = username
        response = self.session.post(self._url("/login_sid.lua?version=2"), data=payload, timeout=self.timeout)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        sid = root.findtext("SID") or ""
        if sid == "0000000000000000":
            raise FritzBoxError("Login fehlgeschlagen.")
        self.sid = sid

    def post_data(self, form: dict[str, Any]) -> dict[str, Any]:
        if not self.sid:
            raise FritzBoxError("Nicht eingeloggt.")
        payload = {"sid": self.sid, "lang": "de", **form}
        response = self.session.post(self._url("/data.lua"), data=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def fetch_netdev(self) -> dict[str, Any]:
        return self.post_data(
            {
                "xhr": "1",
                "page": "netDev",
                "xhrId": "cleanup",
                "useajax": "1",
                "no_sidrenew": "",
            }
        )

    def fetch_detail(self, uid: str) -> dict[str, Any]:
        return self.post_data(
            {
                "xhr": "1",
                "page": "edit_device",
                "xhrId": "all",
                "backToPage": "netDev",
                "dev": uid,
                "no_sidrenew": "",
            }
        )

    def load_passive_devices(self, progress: Any | None = None) -> list[Device]:
        netdev = self.fetch_netdev()
        rows = extract_passive_rows(netdev)
        devices: list[Device] = []
        total = len(rows)
        for index, row in enumerate(rows, start=1):
            uid = str(row.get("UID") or "")
            if not uid:
                continue
            if progress:
                progress(index, total, row)
            detail = self.fetch_detail(uid)
            devices.append(build_device(row, detail))
        return sort_devices(devices)

    def reset_device(self, device: Device) -> ResetResult:
        try:
            data = self.post_data(
                {
                    "xhr": "1",
                    "page": "edit_device",
                    "back_to_page": "netDev",
                    "dev": device.uid,
                    "btn_reset_dev": "",
                }
            )
            status = data.get("data", {}).get("btn_reset_dev")
            if status == "confirm":
                data = self.post_data(
                    {
                        "xhr": "1",
                        "page": "edit_device",
                        "back_to_page": "netDev",
                        "dev": device.uid,
                        "btn_reset_dev": "",
                        "confirmed": "",
                    }
                )
                status = data.get("data", {}).get("btn_reset_dev")
            if status in ("ok", None):
                return ResetResult(device.uid, device.name, True, "OK")
            return ResetResult(device.uid, device.name, False, f"FRITZ!Box Status: {status!r}")
        except Exception as exc:
            return ResetResult(device.uid, device.name, False, str(exc))
