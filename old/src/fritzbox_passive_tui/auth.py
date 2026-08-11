from __future__ import annotations

import hashlib


def login_response(challenge: str, password: str) -> str:
    """Return the FRITZ!Box response for PBKDF2 or legacy challenges."""
    parts = challenge.split("$")
    if len(parts) >= 5 and parts[0].startswith("2"):
        iter1 = int(parts[1])
        salt1 = bytes.fromhex(parts[2])
        iter2 = int(parts[3])
        salt2 = bytes.fromhex(parts[4])
        hash1 = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt1, iter1)
        hash2 = hashlib.pbkdf2_hmac("sha256", hash1, salt2, iter2)
        return f"{parts[4]}${hash2.hex()}"

    legacy = (challenge + "-" + password).encode("utf-16le")
    return challenge + "-" + hashlib.md5(legacy).hexdigest()
