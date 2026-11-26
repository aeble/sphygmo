"""Transtek / Lifesense blood pressure monitors, vendor service 0x7809.

Protocol: docs/protocols/transtek-7809.md
"""
from __future__ import annotations

import asyncio
import logging
import struct
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from ..model import Measurement
from .base import Driver, Emit

log = logging.getLogger(__name__)

_U = lambda x: f"0000{x:04x}-0000-1000-8000-00805f9b34fb"
CMD, STATUS, MEASUREMENT = _U(0x8A81), _U(0x8A82), _U(0x8A91)
SERIAL_NUMBER = _U(0x2A25)
EPOCH = datetime(2010, 1, 1)

OP_TIME, OP_VERIFY, OP_BIND, OP_DONE = 0x02, 0x20, 0x21, 0x22
PKT_PASSWORD, PKT_CHALLENGE = 0xA0, 0xA1
# MedM waits this long between the time sync and the closing 0x22 when pairing
PAIRING_DONE_DELAY = 1.5


def device_seconds(now: datetime) -> int:
    return int((now - EPOCH).total_seconds())


def verify_response(challenge: bytes, password: bytes) -> bytes:
    return bytes([OP_VERIFY]) + bytes(a ^ b for a, b in zip(challenge, password))


def time_command(now: datetime) -> bytes:
    return bytes([OP_TIME]) + struct.pack("<I", device_seconds(now))


def parse_measurement(data: bytes, received_at: datetime, device_id: str | None = None) -> Measurement:
    flags = data[0]
    u16 = lambda off: struct.unpack_from("<H", data, off)[0]
    systolic, diastolic, mean_arterial = u16(1), u16(3), u16(5)
    i = 7
    measured_at = pulse = user = None
    if flags & 0x02:
        measured_at = EPOCH + timedelta(seconds=struct.unpack_from("<I", data, i)[0])
        i += 4
    if flags & 0x04:
        pulse = u16(i)
        i += 2
    if flags & 0x08:
        user = data[i] + 1
        i += 1
    return Measurement(
        systolic=systolic, diastolic=diastolic, pulse=pulse, mean_arterial=mean_arterial,
        unit="kPa" if flags & 0x01 else "mmHg", user=user,
        measured_at=measured_at, received_at=received_at,
        driver="transtek_7809", device_id=device_id, raw=data.hex(),
    )


class Transtek7809(Driver):
    name = "transtek_7809"

    def __init__(self, bind_id: bytes = bytes.fromhex("ff000001"), password: bytes | None = None,
                 clock: Callable[[], datetime] = datetime.now):
        self.bind_id = bind_id
        self.password = password
        self.clock = clock

    def matches(self, device, adv) -> bool:
        # Unbound: "1802A0", bound: "0802A0" + bind ID
        name = device.name or adv.local_name or ""
        return name[2:6].upper() == "02A0"

    async def run(self, client, disconnected: asyncio.Event, emit: Emit) -> None:
        queue: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue()
        await client.start_notify(MEASUREMENT, lambda _, d: queue.put_nowait((MEASUREMENT, bytes(d))))
        await client.start_notify(STATUS, lambda _, d: queue.put_nowait((STATUS, bytes(d))))

        serial = (await client.read_gatt_char(SERIAL_NUMBER)).decode("ascii", "replace").strip("\x00 ")
        password = self.password
        if password is None:
            # Observed on one device: the password equals the first 4 bytes of the serial number
            password = bytes.fromhex(serial[:8])
        pairing = False

        async def write(payload: bytes) -> None:
            log.debug("-> 8a81 %s", payload.hex(" "))
            await client.write_gatt_char(CMD, payload, response=True)

        wait_disconnect = asyncio.ensure_future(disconnected.wait())
        try:
            while True:
                get = asyncio.ensure_future(queue.get())
                done, _ = await asyncio.wait({get, wait_disconnect}, return_when=asyncio.FIRST_COMPLETED)
                if get not in done:
                    get.cancel()
                    return
                char, data = get.result()
                log.debug("<- %s %s", char[4:8], data.hex(" "))
                if char == STATUS and data[0] == PKT_PASSWORD:
                    pairing = True
                    password = data[1:5]
                    log.info("pairing, binding as %s", self.bind_id.hex())
                    await write(bytes([OP_BIND]) + self.bind_id)
                elif char == STATUS and data[0] == PKT_CHALLENGE:
                    await write(verify_response(data[1:5], password))
                    await write(time_command(self.clock()))
                    if pairing:
                        await asyncio.sleep(PAIRING_DONE_DELAY)
                        await write(bytes([OP_DONE]))
                        log.info("pairing complete")
                elif char == MEASUREMENT:
                    m = parse_measurement(data, datetime.now(timezone.utc), serial)
                    await emit(m)
                    await write(bytes([OP_DONE]))
                else:
                    log.warning("unknown packet on %s: %s", char[4:8], data.hex(" "))
        finally:
            wait_disconnect.cancel()
