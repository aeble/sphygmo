# Bluetooth Blood Pressure Service (0x1810)

The standard profile from the Bluetooth SIG (Blood Pressure Profile 1.1, GATT Specification
Supplement). Monitors from Beurer, Sanitas, A&D, Medisana and some Omron models implement it,
often next to vendor services. Driver: `bluetooth_bps`.

## Detection

The monitor advertises the service UUID 0x1810, usually only around a measurement or after
the transfer button is pressed. sphygmo tries the vendor drivers first, so a monitor that
offers both a vendor protocol and 0x1810 is handled by the vendor driver.

## Characteristics

| UUID | Name | Properties | Use |
|---|---|---|---|
| 0x2A35 | Blood Pressure Measurement | indicate | one reading per indication |
| 0x2A36 | Intermediate Cuff Pressure | notify | live cuff pressure, ignored |
| 0x2A49 | Blood Pressure Feature | read | supported status bits, ignored |
| 0x2A25 | Serial Number String (Device Information 0x180A) | read | device ID, if present |

## Session

1. Connect. Most monitors require an encrypted link (bonding) before they send indications.
   On Linux and Windows the driver calls `pair()`; macOS bonds by itself when the driver
   subscribes, and may show a pairing dialog.
2. Subscribe to indications on 0x2A35.
3. The monitor sends its stored readings, one per indication, then disconnects.

There is no acknowledgement beyond the link-layer confirmation of each indication. Many
monitors send **all** stored readings on every connection, not only new ones.

## Measurement (0x2A35)

All values little-endian.

| Bytes | Field | Present if |
|---|---|---|
| 1 | flags | always |
| 2 | systolic, SFLOAT | always |
| 2 | diastolic, SFLOAT | always |
| 2 | mean arterial pressure, SFLOAT | always |
| 7 | timestamp: year u16, month, day, hours, minutes, seconds | flags bit 1 |
| 2 | pulse rate, SFLOAT | flags bit 2 |
| 1 | user ID (0xFF = unknown) | flags bit 3 |
| 2 | measurement status | flags bit 4 |

Flags bit 0: unit, 0 = mmHg, 1 = kPa. sphygmo converts kPa to mmHg.

The timestamp is the monitor's local time without a time zone. Year 0 or month 0 means
unknown.

SFLOAT (IEEE 11073-20601): 4-bit signed exponent in the top bits, 12-bit signed mantissa,
value = mantissa × 10^exponent. Special values: 0x07FF NaN, 0x0800 NRes, 0x07FE +INF,
0x0802 −INF, 0x0801 reserved. sphygmo reads all of them as "no value".

Measurement status bits:

| Bit | Meaning | sphygmo key |
|---|---|---|
| 0 | body movement detected | `body_movement` |
| 1 | cuff fit too loose | `cuff_loose` |
| 2 | irregular pulse | `irregular_pulse` |
| 3–4 | pulse rate out of range (01 above, 10 below) | `pulse_out_of_range` |
| 5 | improper measurement position | `improper_position` |

## Repeated readings

Because the memory is resent, sphygmo remembers the raw payload of every delivered reading
with a timestamp (the last 1000 per device, in the paired devices file) and skips repeats.
Readings without a timestamp cannot be told apart from a new reading with the same values
and are always delivered.

## Not handled

- Setting the monitor's clock through the Current Time Service (0x1805). Some monitors,
  Omron in particular, expect it from the app.
- Record Access Control Point for selecting stored records; blood pressure monitors rarely
  implement it.
- Vendor-specific user selection or consent codes (Omron requires a user index and consent
  code on its own service before data flows).

## Example

```
1e 79 00 4f 00 5d 00 ea 07 0b 1a 0c 16 26 44 00 00 04 00
```

Flags 0x1e (timestamp, pulse, user, status), 121/79 mmHg, MAP 93, 2026-11-26 12:22:38,
pulse 68, user 1, irregular pulse. Synthetic, built from the specification.
