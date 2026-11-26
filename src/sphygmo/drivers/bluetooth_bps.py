"""Standard Bluetooth Blood Pressure Service (0x1810).

Many monitors implement it, e.g. Beurer, Sanitas, A&D, some Omron models. Protocol:
docs/protocols/bluetooth-bps.md
"""
from __future__ import annotations

import asyncio
import logging
import re
import struct
from datetime import datetime, timezone

from ..model import Measurement
from ..trust import TrustStore
from .base import Driver, Emit, Refused

log = logging.getLogger(__name__)

_U = lambda x: f"0000{x:04x}-0000-1000-8000-00805f9b34fb"
SERVICE = _U(0x1810)
MEASUREMENT = _U(0x2A35)
SERIAL_NUMBER = _U(0x2A25)
MAX_QUEUED = 64
KPA_TO_MMHG = 7.50062

# IEEE 11073 SFLOAT special values: NaN, NRes, +INF, -INF, reserved
SFLOAT_SPECIAL = {0x07FF, 0x0800, 0x07FE, 0x0802, 0x0801}

STATUS_BITS = {
    0: "body_movement",
    1: "cuff_loose",
    2: "irregular_pulse",
    5: "improper_position",
}


def sfloat(raw: int) -> float | None:
    if raw in SFLOAT_SPECIAL:
        return None
    mantissa = raw & 0x0FFF
    if mantissa >= 0x0800:
        mantissa -= 0x1000
    exponent = raw >> 12
    if exponent >= 8:
        exponent -= 16
    return mantissa * 10.0 ** exponent


def parse_measurement(data: bytes, received_at: datetime, device_id: str | None = None) -> Measurement:
    if len(data) < 7:
        raise ValueError(f"reading too short: {len(data)} bytes")
    flags = data[0]
    needed = 7 + (7 if flags & 0x02 else 0) + (2 if flags & 0x04 else 0) \
        + (1 if flags & 0x08 else 0) + (2 if flags & 0x10 else 0)
    if len(data) < needed:
        raise ValueError(f"reading too short for flags 0x{flags:02x}: {len(data)} bytes")
    u16 = lambda off: struct.unpack_from("<H", data, off)[0]
    kpa = bool(flags & 0x01)

    def pressure(off: int) -> int | None:
        value = sfloat(u16(off))
        if value is None:
            return None
        return round(value * KPA_TO_MMHG) if kpa else round(value)

    systolic, diastolic, mean_arterial = pressure(1), pressure(3), pressure(5)
    if systolic is None or diastolic is None:
        raise ValueError("reading without systolic or diastolic value")
    i = 7
    measured_at = pulse = user = None
    status: dict[str, bool] = {}
    if flags & 0x02:
        year, month, day, hour, minute, second = struct.unpack_from("<HBBBBB", data, i)
        try:
            measured_at = datetime(year, month, day, hour, minute, second)
        except ValueError:
            # Year 0 or month 0 mean "unknown" in the spec
            measured_at = None
        i += 7
    if flags & 0x04:
        value = sfloat(u16(i))
        pulse = round(value) if value is not None else None
        i += 2
    if flags & 0x08:
        # 0xFF = unknown user
        user = data[i] + 1 if data[i] != 0xFF else None
        i += 1
    if flags & 0x10:
        bits = u16(i)
        status = {name: bool(bits & (1 << b)) for b, name in STATUS_BITS.items()}
        status["pulse_out_of_range"] = bool(bits & 0x18)
    return Measurement(
        systolic=systolic, diastolic=diastolic, pulse=pulse, mean_arterial=mean_arterial,
        user=user, measured_at=measured_at, received_at=received_at,
        driver="bluetooth_bps", device_id=device_id, status=status, raw=data.hex(),
    )


class BluetoothBPS(Driver):
    name = "bluetooth_bps"

    def matches(self, device, adv) -> bool:
        return SERVICE in (adv.service_uuids or [])

    async def device_id(self, client) -> str:
        """Serial number if the device has one, else the address (a per-host UUID on macOS)."""
        try:
            serial = (await client.read_gatt_char(SERIAL_NUMBER)).decode("ascii", "replace").strip("\x00 ")
        except Exception:
            serial = ""
        return serial if re.fullmatch(r"[0-9A-Za-z._-]{4,32}", serial) else client.address

    async def run(self, client, disconnected: asyncio.Event, emit: Emit,
                  trust: TrustStore, pair: bool) -> None:
        device_id = await self.device_id(client)
        if not trust.is_known(self.name, device_id):
            if not pair:
                raise Refused(f"unknown device {device_id}; pair it first with --pair")
            try:
                # Linux and Windows bond here; macOS bonds by itself when indications start
                await client.pair()
            except NotImplementedError:
                pass

        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=MAX_QUEUED)

        def enqueue(data: bytearray) -> None:
            try:
                queue.put_nowait(bytes(data))
            except asyncio.QueueFull:
                log.warning("dropping packet, queue full")

        await client.start_notify(MEASUREMENT, lambda _, d: enqueue(d))
        if not trust.is_known(self.name, device_id):
            trust.add(self.name, device_id)
            log.info("paired %s", device_id)

        wait_disconnect = asyncio.ensure_future(disconnected.wait())
        try:
            while True:
                get = asyncio.ensure_future(queue.get())
                done, _ = await asyncio.wait({get, wait_disconnect}, return_when=asyncio.FIRST_COMPLETED)
                if get not in done:
                    get.cancel()
                    return
                data = get.result()
                log.debug("<- 2a35 %s", data.hex(" "))
                try:
                    m = parse_measurement(data, datetime.now(timezone.utc), device_id)
                except ValueError as e:
                    log.warning("%s: %s", e, data.hex(" "))
                    continue
                # Monitors often resend their whole memory; without a timestamp there is no
                # telling a repeat from a new reading with the same values, so those pass
                if m.measured_at is not None and trust.seen(self.name, device_id, m.raw):
                    log.debug("already delivered: %s", m.raw)
                    continue
                await emit(m)
                if m.measured_at is not None:
                    trust.remember(self.name, device_id, m.raw)
        finally:
            wait_disconnect.cancel()
