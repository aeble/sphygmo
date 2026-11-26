"""Interface every device driver implements."""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from ..model import Measurement

Emit = Callable[[Measurement], Awaitable[None]]


class Driver(ABC):
    name: str

    @abstractmethod
    def matches(self, device: BLEDevice, adv: AdvertisementData) -> bool:
        """True if this driver handles the advertising device."""

    @abstractmethod
    async def run(self, client, disconnected: asyncio.Event, emit: Emit) -> None:
        """Drive one connection until the device disconnects.

        `client` is a connected BleakClient (or a stand-in with the same methods).
        `emit` must be awaited for every measurement; it returns once the record is stored.
        """
