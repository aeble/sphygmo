"""Append one JSON object per measurement to a file."""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..model import Measurement


class JsonlSink:
    def __init__(self, path: Path):
        self.path = path

    async def write(self, m: Measurement) -> None:
        # The device marks a record as sent once the indication is confirmed, so it is
        # never re-sent: persist before returning.
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(m.to_dict(), ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
