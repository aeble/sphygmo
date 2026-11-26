"""Driver tests against the anonymised capture in docs/captures/transtek-7809-medm.txt."""
import asyncio
from datetime import datetime, timezone

from sphygmo.drivers import transtek_7809 as t

PASSWORD = bytes.fromhex("a1b2c3d4")
SERIAL = b"A1B2C3D4E5F6"
READING_USER1 = bytes.fromhex("3e79004f005d008ee9ca1f440000000000")
READING_USER2 = bytes.fromhex("3e76004c005a008ee9ca1f480001000000")


def test_parse_measurement():
    m = t.parse_measurement(READING_USER1, datetime.now(timezone.utc))
    assert (m.systolic, m.diastolic, m.mean_arterial, m.pulse, m.user) == (121, 79, 93, 68, 1)
    assert m.measured_at == datetime(2026, 11, 26, 12, 22, 38)
    assert m.unit == "mmHg"
    assert t.parse_measurement(READING_USER2, datetime.now(timezone.utc)).user == 2


def test_verify_response():
    # Capture: challenge a1 1f ca e9 70 -> 20 be 78 2a a4
    assert t.verify_response(bytes.fromhex("1fcae970"), PASSWORD) == bytes.fromhex("20be782aa4")


def test_time_command():
    assert t.time_command(datetime(2026, 11, 26, 12, 22, 9)) == bytes.fromhex("0271e9ca1f")


class FakeClient:
    def __init__(self):
        self.callbacks = {}
        self.writes = []

    async def start_notify(self, char, cb):
        self.callbacks[char] = cb

    async def read_gatt_char(self, char):
        assert char == t.SERIAL_NUMBER
        return SERIAL

    async def write_gatt_char(self, char, data, response=True):
        assert char == t.CMD
        self.writes.append(bytes(data))

    def indicate(self, char, data):
        self.callbacks[char](None, bytearray(data))


async def _session(packets, monkeypatch=None):
    client, disconnected, emitted = FakeClient(), asyncio.Event(), []

    async def emit(m):
        emitted.append(m)

    driver = t.Transtek7809(clock=lambda: datetime(2026, 11, 26, 12, 22, 9))
    task = asyncio.create_task(driver.run(client, disconnected, emit))
    await asyncio.sleep(0)
    for char, data in packets:
        client.indicate(char, data)
        await asyncio.sleep(0.01)
    disconnected.set()
    await task
    return client.writes, emitted


def test_sync_session():
    writes, emitted = asyncio.run(_session([
        (t.STATUS, bytes.fromhex("a11fcae970") + bytes(15)),
        (t.MEASUREMENT, READING_USER1),
    ]))
    assert writes == [bytes.fromhex("20be782aa4"), bytes.fromhex("0271e9ca1f"), b"\x22"]
    assert [m.systolic for m in emitted] == [121]
    assert emitted[0].device_id == "A1B2C3D4E5F6"


def test_pairing_session(monkeypatch):
    monkeypatch.setattr(t, "PAIRING_DONE_DELAY", 0)
    writes, emitted = asyncio.run(_session([
        (t.STATUS, bytes.fromhex("a0a1b2c3d4") + bytes(15)),
        (t.STATUS, bytes.fromhex("a11fcae960") + bytes(15)),
    ]))
    assert writes == [bytes.fromhex("21ff000001"), bytes.fromhex("20be782ab4"),
                      bytes.fromhex("0271e9ca1f"), b"\x22"]
    assert emitted == []
