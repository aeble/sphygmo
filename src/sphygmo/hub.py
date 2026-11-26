"""Scan for supported devices, hand each connection to its driver."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence

from bleak import BleakClient, BleakScanner

from .drivers.base import Driver, Emit, Refused
from .model import Measurement
from .trust import TrustStore

log = logging.getLogger(__name__)

# Longest session seen: ~30 s from measurement start to reading. Anything holding the
# connection much longer blocks every other device.
SESSION_TIMEOUT = 120


# A refused device keeps reconnecting every few seconds; leave it alone for a while.
REFUSED_COOLDOWN = 300


class Cooldown:
    """Keyed by address and advertised name, so a device switching to pairing mode
    (which changes its name) is not held back."""

    def __init__(self, seconds: float = REFUSED_COOLDOWN, clock=time.monotonic):
        self.seconds, self.clock, self.until = seconds, clock, {}

    def block(self, address: str, name: str | None) -> None:
        self.until[(address, name)] = self.clock() + self.seconds

    def blocked(self, address: str, name: str | None) -> bool:
        return self.until.get((address, name), 0) > self.clock()


def printable(text: str | None) -> str:
    """Advertised names are attacker-controlled; keep control characters out of logs."""
    return repr(text or "")


def guarded(emit: Emit) -> Emit:
    """Log the raw payload if storing fails: the device will not send the reading again."""
    async def wrapper(m: Measurement) -> None:
        try:
            await emit(m)
        except Exception:
            log.error("could not store reading, raw payload %s from %s", m.raw, m.device_id)
            raise
    return wrapper


async def run_session(driver: Driver, client, disconnected: asyncio.Event, emit: Emit,
                      trust: TrustStore, pair: bool, timeout: float = SESSION_TIMEOUT) -> None:
    try:
        await asyncio.wait_for(driver.run(client, disconnected, emit, trust, pair), timeout)
    except asyncio.TimeoutError:
        log.warning("session exceeded %s s, disconnecting", timeout)


async def listen(drivers: Sequence[Driver], emit: Emit, trust: TrustStore, pair: bool = False) -> None:
    """Run forever. Devices typically advertise only around a measurement."""
    emit = guarded(emit)
    cooldown = Cooldown()
    while True:
        match: dict = {}

        def wanted(device, adv) -> bool:
            # macOS caches device.name; the advertised name tells pairing mode apart
            name = adv.local_name or device.name
            if cooldown.blocked(device.address, name):
                return False
            for driver in drivers:
                if driver.matches(device, adv):
                    match["driver"], match["name"] = driver, name
                    return True
            return False

        device = await BleakScanner.find_device_by_filter(wanted, timeout=60)
        if device is None:
            continue
        driver: Driver = match["driver"]
        log.info("connecting to %s (%s)", printable(device.name), driver.name)
        disconnected = asyncio.Event()
        name = match["name"]
        try:
            async with BleakClient(device, timeout=20,
                                   disconnected_callback=lambda _: disconnected.set()) as client:
                await run_session(driver, client, disconnected, emit, trust, pair)
        except Refused as e:
            log.warning("%s; ignoring %s for %s s", e, printable(name), REFUSED_COOLDOWN)
            cooldown.block(device.address, name)
        except Exception:
            log.exception("session with %s failed", printable(device.name))
        log.info("disconnected")
        await asyncio.sleep(1)
