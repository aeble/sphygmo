"""Devices the user has paired. Readings from any other device are refused.

BLE gives no authentication here: a device that copies the serial number of a paired one is
still accepted. The store keeps casual and accidental injection out, not a targeted attacker.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Readings remembered per device; more than any monitor's memory
MAX_SEEN = 1000


def default_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "sphygmo" / "devices.json"


class TrustStore:
    def __init__(self, path: Path):
        self.path = path
        try:
            self.devices: dict = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.devices = {}

    @staticmethod
    def _key(driver: str, device_id: str) -> str:
        return f"{driver}:{device_id}"

    def is_known(self, driver: str, device_id: str) -> bool:
        return self._key(driver, device_id) in self.devices

    def add(self, driver: str, device_id: str) -> None:
        self.devices[self._key(driver, device_id)] = {"paired_at": datetime.now(timezone.utc).isoformat()}
        self._save()

    def seen(self, driver: str, device_id: str, reading: str) -> bool:
        """True if this reading was already delivered. For devices that resend their memory."""
        return reading in self.devices.get(self._key(driver, device_id), {}).get("seen", [])

    def remember(self, driver: str, device_id: str, reading: str) -> None:
        entry = self.devices.setdefault(self._key(driver, device_id), {})
        entry["seen"] = (entry.get("seen", []) + [reading])[-MAX_SEEN:]
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.devices, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
