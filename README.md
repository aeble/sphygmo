# sphygmo

Receive readings from Bluetooth LE blood pressure monitors without the vendor app, and
store them somewhere you control.

sphygmo has two halves:

- **Drivers** speak a device protocol and turn packets into a common `Measurement`.
- **Sinks** store or export measurements. Today there is one: a JSON Lines file.

Planned next: a driver for the standard Bluetooth Blood Pressure Service (0x1810, with
record access for stored history), and sinks for Home Assistant, FHIR and Apple Health
(via an iOS shortcut).

## Supported devices

| Device | Driver | Notes |
|---|---|---|
| visomat cardiovision (= iProven BPM-2244 BT) | `transtek_7809` | [device notes](docs/devices/visomat-cardiovision.md) |

Other Transtek/Lifesense monitors that advertise a name like `1802A0` and expose service
`0x7809` probably work too. Reports welcome.

## Usage

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/sphygmo --jsonl measurements.jsonl
```

Then take a measurement. The device connects on its own around each measurement and also
sends any readings it buffered while nobody was listening. Each reading is appended to the
file before it is acknowledged.

Pair each device once:

```bash
.venv/bin/sphygmo --pair
```

then put the device into pairing mode (visomat: hold the Bluetooth button). Paired devices
are remembered in `~/.config/sphygmo/devices.json`; run without `--pair` afterwards. Devices
that are not paired get no response and their readings are ignored.

On macOS the terminal needs Bluetooth permission (System Settings, Privacy & Security,
Bluetooth).

## Security

Anything in radio range can advertise a matching name and send bytes. sphygmo serves only
paired devices, accepts pairing only with `--pair`, bounds each session to 120 s, skips
malformed packets, keeps control characters out of the log and creates its files readable
by the owner only. The protocols have no authentication, though: a device that copies the
serial number of a paired one is still accepted. Pair in a quiet moment and review readings
before exporting them.

## Adding a device

Implement `sphygmo.drivers.base.Driver`: `matches()` decides from the advertisement,
`run()` drives one connection, serves only devices in the trust store and awaits `emit()`
for every reading. Treat every packet as hostile input. Document the protocol
under `docs/protocols/`, with an anonymised capture under `docs/captures/` and tests built
from it.

## Status

Early. Protocols are reverse-engineered from captures and may be incomplete; see the open
points in each protocol document. Not a medical device, no warranty.

## License

Apache-2.0
