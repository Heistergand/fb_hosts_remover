from fritzbox_passive_tui.requests import build_reset_payload


def test_build_reset_payload() -> None:
    assert build_reset_payload("sid123", "landevice1") == {
        "sid": "sid123",
        "lang": "de",
        "xhr": "1",
        "page": "edit_device",
        "back_to_page": "netDev",
        "dev": "landevice1",
        "btn_reset_dev": "",
    }


def test_build_reset_payload_confirmed() -> None:
    payload = build_reset_payload("sid123", "landevice1", confirmed=True)
    assert payload["confirmed"] == ""
