"""Scan for supported devices, hand each connection to its driver."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from bleak import BleakClient, BleakScanner

from .drivers.base import Driver, Emit

log = logging.getLogger(__name__)


async def listen(drivers: Sequence[Driver], emit: Emit) -> None:
    """Run forever. Devices typically advertise only around a measurement."""
    while True:
        match: dict = {}

        def wanted(device, adv) -> bool:
            for driver in drivers:
                if driver.matches(device, adv):
                    match["driver"] = driver
                    return True
            return False

        device = await BleakScanner.find_device_by_filter(wanted, timeout=60)
        if device is None:
            continue
        driver: Driver = match["driver"]
        log.info("connecting to %s (%s)", device.name, driver.name)
        disconnected = asyncio.Event()
        try:
            async with BleakClient(device, timeout=20,
                                   disconnected_callback=lambda _: disconnected.set()) as client:
                await driver.run(client, disconnected, emit)
        except Exception:
            log.exception("session with %s failed", device.name)
        log.info("disconnected")
        await asyncio.sleep(1)
