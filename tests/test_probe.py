"""Device filters and partial reports of `sphygmo probe`."""
import asyncio
from types import SimpleNamespace

import pytest

from sphygmo import probe

WITHINGS_SERVICE = "00000020-5749-5448-002d-000000000000"


def adv(name=None, services=(), manufacturer=None):
    return SimpleNamespace(local_name=name, service_uuids=list(services),
                           manufacturer_data=manufacturer or {}, service_data={}, rssi=-50)


DEVICE = SimpleNamespace(name=None, address="AA:BB")
NAMELESS = adv(services=[WITHINGS_SERVICE], manufacturer={0x03FF: b"\0\0\0\0"})


@pytest.mark.parametrize("filters, expected", [
    ({"company": 0x03FF}, True),
    ({"company": 0x004C}, False),
    ({"service": WITHINGS_SERVICE.upper()}, True),
    ({"service": "1810"}, False),
    ({"match": "BPM"}, False),  # most packets of this device carry no name
    ({"company": 0x03FF, "service": WITHINGS_SERVICE}, True),
    ({"company": 0x03FF, "match": "BPM"}, False),
])
def test_filters_must_all_hold(filters, expected):
    assert probe.wanted(DEVICE, NAMELESS, **filters) is expected


def test_short_service_uuid_is_expanded():
    assert probe.wanted(DEVICE, adv(services=["00001810-0000-1000-8000-00805f9b34fb"]), service="1810")


class FailingClient:
    def __init__(self, *args, **kwargs):
        self.timeout = kwargs["timeout"]

    async def __aenter__(self):
        raise OSError("[WinError -2147418113] Catastrophic failure")

    async def __aexit__(self, *exc):
        return False


def test_failed_connection_still_gives_a_report(monkeypatch):
    seen = {}

    def client(*args, **kwargs):
        c = FailingClient(*args, **kwargs)
        seen["timeout"] = c.timeout
        return c

    monkeypatch.setattr(probe, "BleakClient", client)
    report = asyncio.run(probe.survey(DEVICE, NAMELESS, listen_seconds=1, connect_timeout=60))
    assert seen["timeout"] == 60
    assert report["error"] == {"stage": "connect", "type": "OSError",
                               "message": "[WinError -2147418113] Catastrophic failure"}
    assert report["advertisement"]["service_uuids"] == [WITHINGS_SERVICE]
    assert report["advertisement"]["manufacturer_data"] == {"1023": "00000000"}
