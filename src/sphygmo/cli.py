"""Command line entry point."""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from .drivers.transtek_7809 import Transtek7809
from .hub import listen
from .model import Measurement
from .sinks.jsonl import JsonlSink
from .trust import TrustStore, default_path


def main() -> None:
    ap = argparse.ArgumentParser(prog="sphygmo", description="Receive blood pressure readings over BLE.")
    ap.add_argument("--jsonl", type=Path, default=Path("measurements.jsonl"),
                    help="file to append readings to (default: %(default)s)")
    ap.add_argument("--transtek-bind-id", default="ff000001",
                    help="4-byte ID (hex) sent when pairing a Transtek device (default: %(default)s)")
    ap.add_argument("--transtek-password", help="4-byte password (hex); default: derived from the serial number")
    ap.add_argument("--pair", action="store_true",
                    help="accept devices that ask to pair and remember them; without it only paired devices are served")
    ap.add_argument("--devices", type=Path, default=default_path(),
                    help="paired devices file (default: %(default)s)")
    ap.add_argument("-v", "--verbose", action="store_true", help="log every packet")
    a = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("bleak").setLevel(logging.WARNING)

    sink = JsonlSink(a.jsonl)

    async def emit(m: Measurement) -> None:
        await sink.write(m)
        print(f"{m.measured_at}  user {m.user}  {m.systolic}/{m.diastolic} {m.unit}  pulse {m.pulse}")

    drivers = [Transtek7809(
        bind_id=bytes.fromhex(a.transtek_bind_id),
        password=bytes.fromhex(a.transtek_password) if a.transtek_password else None,
    )]
    try:
        asyncio.run(listen(drivers, emit, TrustStore(a.devices), a.pair))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
