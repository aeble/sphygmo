"""Behaviour against hostile or broken devices."""
import asyncio
import logging
import os
import stat
from datetime import datetime, timezone

import pytest

from sphygmo import hub
from sphygmo.drivers import transtek_7809 as t
from sphygmo.drivers.base import Refused
from sphygmo.sinks.jsonl import JsonlSink
from sphygmo.trust import TrustStore

from test_transtek_7809 import READING_USER1, SERIAL, FakeClient

# Windows has no POSIX mode bits; there the files are protected by the profile's ACL.
posix_only = pytest.mark.skipif(os.name == "nt", reason="no POSIX file modes on Windows")

A1 = bytes.fromhex("a11fcae970") + bytes(15)
A0 = bytes.fromhex("a0a1b2c3d4") + bytes(15)


async def _run(packets, trust, pair=False, serial=SERIAL, expect_refused=False):
    client, disconnected, emitted = FakeClient(), asyncio.Event(), []
    client.serial = serial

    async def emit(m):
        emitted.append(m)

    driver = t.Transtek7809(clock=lambda: datetime(2026, 11, 26, 12, 22, 9))
    task = asyncio.create_task(driver.run(client, disconnected, emit, trust, pair))
    await asyncio.sleep(0)
    for char, data in packets:
        if char in client.callbacks:
            client.indicate(char, data)
        await asyncio.sleep(0.01)
    disconnected.set()
    if expect_refused:
        try:
            await task
        except Refused:
            return client.writes, emitted
        raise AssertionError("expected Refused")
    await task
    return client.writes, emitted


def test_unknown_device_gets_no_response(tmp_path):
    trust = TrustStore(tmp_path / "devices.json")
    writes, emitted = asyncio.run(_run([(t.STATUS, A1), (t.MEASUREMENT, READING_USER1)], trust,
                                       expect_refused=True))
    assert writes == [] and emitted == []


def test_pairing_refused_without_pair_mode(tmp_path):
    trust = TrustStore(tmp_path / "devices.json")
    writes, _ = asyncio.run(_run([(t.STATUS, A0), (t.STATUS, A1)], trust, expect_refused=True))
    assert writes == []
    assert not trust.is_known("transtek_7809", "A1B2C3D4E5F6")


def test_pairing_in_pair_mode_trusts_device(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "PAIRING_DONE_DELAY", 0)
    path = tmp_path / "devices.json"
    asyncio.run(_run([(t.STATUS, A0), (t.STATUS, A1)], TrustStore(path), pair=True))
    assert TrustStore(path).is_known("transtek_7809", "A1B2C3D4E5F6")
    if os.name != "nt":
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_known_device_is_served(tmp_path):
    trust = TrustStore(tmp_path / "devices.json")
    trust.add("transtek_7809", "A1B2C3D4E5F6")
    writes, emitted = asyncio.run(_run([(t.STATUS, A1), (t.MEASUREMENT, READING_USER1)], trust))
    assert len(emitted) == 1 and writes[-1] == b"\x22"


def test_malformed_packets_are_skipped(tmp_path):
    trust = TrustStore(tmp_path / "devices.json")
    trust.add("transtek_7809", "A1B2C3D4E5F6")
    writes, emitted = asyncio.run(_run([
        (t.STATUS, b""),
        (t.STATUS, b"\xa1\x01"),
        (t.MEASUREMENT, b""),
        (t.MEASUREMENT, READING_USER1[:9]),
        (t.STATUS, A1),
        (t.MEASUREMENT, READING_USER1),
    ], trust))
    assert [m.systolic for m in emitted] == [121]


def test_non_hex_serial_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "PAIRING_DONE_DELAY", 0)
    writes, _ = asyncio.run(_run([(t.STATUS, A0), (t.STATUS, A1)],
                                 TrustStore(tmp_path / "d.json"), pair=True, serial=b"\x1b[2J!!"))
    assert writes == []


def test_session_timeout():
    class Hanging:
        name = "hanging"

        async def run(self, client, disconnected, emit, trust, pair):
            await asyncio.sleep(10)

    async def go():
        await hub.run_session(Hanging(), None, asyncio.Event(), None, None, False, timeout=0.05)

    asyncio.run(asyncio.wait_for(go(), 1))


def test_device_name_is_escaped():
    assert "\x1b" not in hub.printable("\x1b[2Jevil\n")


def test_sink_failure_logs_raw(caplog, tmp_path):
    class Broken:
        async def write(self, m):
            raise OSError("disk full")

    m = t.parse_measurement(READING_USER1, datetime.now(timezone.utc))
    emit = hub.guarded(Broken().write)
    with caplog.at_level(logging.ERROR):
        try:
            asyncio.run(emit(m))
        except OSError:
            pass
    assert READING_USER1.hex() in caplog.text


@posix_only
def test_jsonl_file_is_private(tmp_path):
    path = tmp_path / "m.jsonl"
    asyncio.run(JsonlSink(path).write(t.parse_measurement(READING_USER1, datetime.now(timezone.utc))))
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_cooldown_blocks_refused_device_but_not_its_pairing_mode():
    now = [1000.0]
    c = hub.Cooldown(seconds=300, clock=lambda: now[0])
    c.block("AA", "0802A0FF000002")
    assert c.blocked("AA", "0802A0FF000002")
    assert not c.blocked("AA", "1802A0")  # same device, now in pairing mode
    now[0] += 301
    assert not c.blocked("AA", "0802A0FF000002")
