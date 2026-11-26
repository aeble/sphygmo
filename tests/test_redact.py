"""Identifiers must not survive into published reports or captures."""
from sphygmo.probe import redact_report
from sphygmo.redact import redact_bytes

SERIAL = "A1B2C3D4E5F6"


def test_serial_ascii_raw_and_prefix_are_overwritten():
    data = SERIAL.encode() + bytes.fromhex("a0a1b2c3d4") + bytes.fromhex("f6e5d4c3b2a1")
    out = redact_bytes(data, [SERIAL])
    assert SERIAL.encode() not in out
    assert bytes.fromhex("a1b2c3d4") not in out
    assert bytes.fromhex("f6e5d4c3b2a1") not in out
    assert out[12] == 0xA0  # unrelated bytes stay


def test_report_is_redacted_everywhere():
    report = {
        "advertisement": {"local_name": "BPM-A1B2C3D4E5F6", "manufacturer_data": {"76": "00a1b2c3d4e5f6"}},
        "services": [{"characteristics": [{"uuid": "00002a25-0000-1000-8000-00805f9b34fb",
                                            "value": SERIAL.encode().hex(), "text": SERIAL}]}],
        "packets": [{"uuid": "x", "value": "a0a1b2c3d40000"}],
    }
    text = str(redact_report(report, [SERIAL])).lower()
    assert SERIAL.lower() not in text
    assert "a1b2c3d4" not in text
    assert SERIAL.encode().hex() not in text
