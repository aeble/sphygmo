"""Device-independent data model."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class Measurement:
    systolic: int
    diastolic: int
    pulse: int | None
    # Mean arterial pressure as reported by the device, if any
    mean_arterial: int | None
    # Device clock, local time without zone; may be wrong if the device clock drifted
    measured_at: datetime | None
    # Receiver clock, timezone-aware
    received_at: datetime
    driver: str
    unit: str = "mmHg"
    # 1-based user slot on the device, None if the device has no users
    user: int | None = None
    device_id: str | None = None
    # Decoded status flags (body_movement, irregular_pulse, ...); only keys the driver knows
    status: dict[str, bool] = field(default_factory=dict)
    # Raw payload as hex, kept so records can be re-decoded later
    raw: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        for key in ("measured_at", "received_at"):
            if d[key] is not None:
                d[key] = d[key].isoformat()
        return d
