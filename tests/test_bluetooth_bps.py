"""Bluetooth Blood Pressure Service driver, with readings built from the specification."""
import asyncio
from datetime import datetime, timezone

import pytest

from sphygmo.drivers import bluetooth_bps as b
from sphygmo.drivers.base import Refused
from sphygmo.trust import TrustStore

# flags 0x1e: timestamp, pulse, user, status; 121/79 MAP 93, 2026-11-26 12:22:38, pulse 68,
# user index 0, status irregular pulse
FULL = bytes.fromhex("1e" "7900" "4f00" "5d00" "ea070b1a0c1626" "4400" "00" "0400")
# flags 0x01: kPa, no options; 16.1/10.5 kPa, MAP NaN
KPA = bytes.fromhex("01" "a1f0" "69f0" "ff07")
NO_TIME = bytes.fromhex("00" "7900" "4f00" "5d00")


def test_sfloat():
    assert b.sfloat(0x0079) == 121
    assert b.sfloat(0xF0A1) == pytest.approx(16.1)
    assert b.sfloat(0x0FFF) == -1
    assert b.sfloat(0x07FF) is None


def test_parse_full():
    m = b.parse_measurement(FULL, datetime.now(timezone.utc))
    assert (m.systolic, m.diastolic, m.mean_arterial, m.pulse, m.user) == (121, 79, 93, 68, 1)
    assert m.measured_at == datetime(2026, 11, 26, 12, 22, 38)
    assert m.status["irregular_pulse"] and not m.status["body_movement"]
    assert m.unit == "mmHg"


def test_parse_kpa_converted():
    m = b.parse_measurement(KPA, datetime.now(timezone.utc))
    assert (m.systolic, m.diastolic, m.mean_arterial) == (121, 79, None)
    assert m.measured_at is None and m.pulse is None


def test_parse_rejects_short_and_missing():
    with pytest.raises(ValueError):
        b.parse_measurement(FULL[:10], datetime.now(timezone.utc))
    with pytest.raises(ValueError):
        b.parse_measurement(bytes.fromhex("00ff07ff075d00"), datetime.now(timezone.utc))


def test_unknown_timestamp_is_none():
    data = bytearray(FULL)
    data[7:9] = b"\x00\x00"  # year 0 = unknown
    assert b.parse_measurement(bytes(data), datetime.now(timezone.utc)).measured_at is None


class FakeClient:
    address = "AA:BB:CC:DD:EE:FF"

    def __init__(self, serial=b"BM81-0001"):
        self.serial = serial
        self.callback = None
        self.paired = False

    async def read_gatt_char(self, char):
        assert char == b.SERIAL_NUMBER
        if self.serial is None:
            raise RuntimeError("no such characteristic")
        return self.serial

    async def pair(self):
        self.paired = True

    async def start_notify(self, char, cb):
        assert char == b.MEASUREMENT
        self.callback = cb


async def _session(packets, trust, pair=False, client=None):
    client, disconnected, emitted = client or FakeClient(), asyncio.Event(), []

    async def emit(m):
        emitted.append(m)

    task = asyncio.create_task(b.BluetoothBPS().run(client, disconnected, emit, trust, pair))
    await asyncio.sleep(0)
    for data in packets:
        client.callback(None, bytearray(data))
        await asyncio.sleep(0.01)
    disconnected.set()
    await task
    return emitted


def test_unknown_device_refused(tmp_path):
    client = FakeClient()

    async def emit(m):
        raise AssertionError("must not emit")

    with pytest.raises(Refused):
        asyncio.run(b.BluetoothBPS().run(client, asyncio.Event(), emit, TrustStore(tmp_path / "d.json"), False))
    # Refused before subscribing: the device never gets to deliver readings
    assert client.callback is None and not client.paired


def test_pair_then_resent_memory_is_deduplicated(tmp_path):
    path = tmp_path / "d.json"
    client = FakeClient()
    first = asyncio.run(_session([FULL, NO_TIME], TrustStore(path), pair=True, client=client))
    assert client.paired and len(first) == 2
    assert first[0].device_id == "BM81-0001"
    # Next connection: device resends its memory plus one new reading
    newer = bytearray(FULL)
    newer[13] = 0x27  # second 38 -> 39
    second = asyncio.run(_session([FULL, NO_TIME, bytes(newer)], TrustStore(path)))
    assert [m.raw for m in second] == [NO_TIME.hex(), bytes(newer).hex()]


def test_malformed_packet_skipped(tmp_path):
    trust = TrustStore(tmp_path / "d.json")
    trust.add("bluetooth_bps", "BM81-0001")
    emitted = asyncio.run(_session([b"\x1e\x79", FULL], trust))
    assert [m.systolic for m in emitted] == [121]


@pytest.mark.parametrize("serial", [None, b"bad\nserial"])
def test_address_when_serial_missing_or_odd(tmp_path, serial):
    trust = TrustStore(tmp_path / "d.json")
    emitted = asyncio.run(_session([FULL], trust, pair=True, client=FakeClient(serial)))
    assert emitted[0].device_id == FakeClient.address
    assert trust.is_known("bluetooth_bps", FakeClient.address)
