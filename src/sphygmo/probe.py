"""Read-only survey of an unknown blood pressure monitor, for device reports.

Never writes to the device. The report leaves out the Bluetooth address and overwrites the
serial number and system ID wherever they appear.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from bleak import BleakClient, BleakScanner

from . import __version__
from .hub import printable
from .redact import redact_bytes, redact_text

BPS_SERVICE = "00001810-0000-1000-8000-00805f9b34fb"
SERIAL_NUMBER = "00002a25-0000-1000-8000-00805f9b34fb"
SYSTEM_ID = "00002a23-0000-1000-8000-00805f9b34fb"


async def choose_device(scan_seconds: float, match: str | None = None):
    if match:
        print(f"Waiting up to {scan_seconds:.0f} s for a device named *{match}*.")
        seen: dict = {}

        def wanted(d, a) -> bool:
            if match.lower() in (a.local_name or d.name or "").lower():
                seen["adv"] = a
                return True
            return False

        device = await BleakScanner.find_device_by_filter(wanted, timeout=scan_seconds)
        if device is None:
            print("Nothing found.")
            return None, None
        return device, seen["adv"]
    print(f"Scanning {scan_seconds:.0f} s. Start a measurement or press the Bluetooth button now.")
    found = await BleakScanner.discover(timeout=scan_seconds, return_adv=True)
    devices = sorted(found.values(), key=lambda t: -(t[1].rssi or -999))
    devices = [(d, a) for d, a in devices if a.local_name or a.service_uuids]
    if not devices:
        print("Nothing found.")
        return None, None
    for n, (d, a) in enumerate(devices):
        tag = "  <- standard blood pressure service" if BPS_SERVICE in a.service_uuids else ""
        print(f"[{n:2}] RSSI {a.rssi:4}  {printable(a.local_name)}  {a.service_uuids}{tag}")
    choice = input("Number of your monitor (empty to quit): ").strip()
    if not choice:
        return None, None
    return devices[int(choice)]


def _text(value: bytes) -> str | None:
    try:
        s = value.decode("ascii")
    except UnicodeDecodeError:
        return None
    return s if s.isprintable() else None


async def survey(device, adv, listen_seconds: float) -> dict:
    report: dict = {
        "sphygmo": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "advertisement": {
            "local_name": adv.local_name,
            "service_uuids": adv.service_uuids,
            "manufacturer_data": {str(k): v.hex() for k, v in adv.manufacturer_data.items()},
            "service_data": {k: v.hex() for k, v in adv.service_data.items()},
        },
        "services": [],
        "packets": [],
    }
    secrets: list[str] = []
    t0 = time.monotonic()
    disconnected = asyncio.Event()
    async with BleakClient(device, timeout=20, disconnected_callback=lambda _: disconnected.set()) as c:
        subscribe = []
        for svc in c.services:
            entry = {"uuid": svc.uuid, "description": svc.description, "characteristics": []}
            for ch in svc.characteristics:
                item = {"uuid": ch.uuid, "description": ch.description, "properties": ch.properties}
                if "read" in ch.properties:
                    try:
                        value = bytes(await c.read_gatt_char(ch))
                        item["value"] = value.hex()
                        item["text"] = _text(value)
                        if ch.uuid in (SERIAL_NUMBER, SYSTEM_ID):
                            secrets.append(_text(value) or value.hex())
                    except Exception as e:
                        item["read_error"] = str(e)
                if {"notify", "indicate"} & set(ch.properties):
                    subscribe.append(ch)
                entry["characteristics"].append(item)
            report["services"].append(entry)

        def on_packet(ch, data: bytearray) -> None:
            report["packets"].append({"t": round(time.monotonic() - t0, 3), "uuid": ch.uuid,
                                      "value": bytes(data).hex()})
            print(f"  {ch.uuid[4:8]}  {bytes(data).hex(' ')}")

        for ch in subscribe:
            try:
                await c.start_notify(ch, on_packet)
            except Exception as e:
                report.setdefault("subscribe_errors", {})[ch.uuid] = str(e)
        print(f"Connected, listening up to {listen_seconds:.0f} s. Take a measurement if you have not yet.")
        try:
            await asyncio.wait_for(disconnected.wait(), listen_seconds)
            report["disconnected_by_device_after"] = round(time.monotonic() - t0, 1)
        except asyncio.TimeoutError:
            pass
    return redact_report(report, [s for s in secrets if s])


def redact_report(report: dict, secrets: list[str]) -> dict:
    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            if node and len(node) % 2 == 0 and all(c in "0123456789abcdef" for c in node):
                return redact_bytes(bytes.fromhex(node), secrets).hex()
            return redact_text(node, secrets)
        return node
    return walk(report)


def run(out: Path, scan_seconds: float, listen_seconds: float, match: str | None = None) -> None:
    device, adv = asyncio.run(choose_device(scan_seconds, match))
    if device is None:
        return
    report = asyncio.run(survey(device, adv, listen_seconds))
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nReport written to {out}.")
    print("Serial number and system ID are overwritten with 'ee' bytes; the Bluetooth address is not")
    print("included. Packets may contain your blood pressure readings: check the file before you")
    print("attach it to a public issue.")
