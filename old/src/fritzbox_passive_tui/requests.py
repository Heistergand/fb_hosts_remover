from __future__ import annotations


def build_reset_payload(sid: str, uid: str, confirmed: bool = False) -> dict[str, str]:
    payload = {
        "sid": sid,
        "lang": "de",
        "xhr": "1",
        "page": "edit_device",
        "back_to_page": "netDev",
        "dev": uid,
        "btn_reset_dev": "",
    }
    if confirmed:
        payload["confirmed"] = ""
    return payload
