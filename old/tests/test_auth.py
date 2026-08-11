import hashlib

from fritzbox_passive_tui.auth import login_response


def test_pbkdf2_login_response() -> None:
    challenge = "2$2$01020304$3$05060708"
    h1 = hashlib.pbkdf2_hmac("sha256", b"secret", bytes.fromhex("01020304"), 2)
    h2 = hashlib.pbkdf2_hmac("sha256", h1, bytes.fromhex("05060708"), 3)
    assert login_response(challenge, "secret") == f"05060708${h2.hex()}"


def test_legacy_login_response() -> None:
    expected = hashlib.md5("abc-secret".encode("utf-16le")).hexdigest()
    assert login_response("abc", "secret") == f"abc-{expected}"
