"""Remove identifiers from data that users are asked to publish."""
from __future__ import annotations

import re

MARK = 0xEE


def secret_forms(secret: str) -> list[bytes]:
    """A serial number may appear as ASCII or, if it is hex, as raw bytes."""
    forms = [secret.encode()]
    if re.fullmatch(r"(?:[0-9A-Fa-f]{2}){2,}", secret):
        raw = bytes.fromhex(secret)
        forms += [raw, raw[::-1]]
    return [f for f in forms if len(f) >= 2]


def redact_bytes(data: bytes, secrets: list[str]) -> bytes:
    """Overwrite every occurrence of each secret, and of its first 4 bytes, with 0xEE."""
    out = bytearray(data)
    for secret in secrets:
        for form in secret_forms(secret):
            for needle in {form, form[:4]}:
                if len(needle) < 3:
                    continue
                start = 0
                while (i := out.find(needle, start)) >= 0:
                    out[i:i + len(needle)] = bytes([MARK]) * len(needle)
                    start = i + len(needle)
    return bytes(out)


def redact_text(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = re.sub(re.escape(secret), "<redacted>", text, flags=re.IGNORECASE)
    return text
