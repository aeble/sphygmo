# Transtek / Lifesense, service 0x7809

Reverse-engineered from a PacketLogger capture of the MedM app (pairing and one reading,
see [capture](../captures/transtek-7809-medm.txt)) and from about a dozen sessions with
sphygmo. Serial number, password and readings in this document are replaced by fake
values.

## Advertising

The device advertises only shortly before and after a measurement. While idle it is
invisible and cannot be connected to.

| State | Name |
|---|---|
| unbound or pairing mode | `1802A0` |
| bound | `0802A0` + bind ID, e.g. `0802A0FF000001` |

Holding the Bluetooth button enters pairing mode. A short press triggers nothing on a bound
device.

## GATT

Service `0x7809`:

| Char | Properties | Use |
|---|---|---|
| 0x8a81 | write | commands, app to device |
| 0x8a82 | indicate | `A0` / `A1`, device to app |
| 0x8a90 | read | returns `00 00`, meaning unknown |
| 0x8a91 | indicate | readings |
| 0x8a92 | notify | silent, even when subscribed |

Device Information (0x180A) carries manufacturer `Transtek` and the serial number (0x2A25).

## Messages

All times are seconds since 2010-01-01 00:00 **local time**.

| Dir | Bytes | Meaning |
|---|---|---|
| ← 8a82 | `a0` + password(4) + zeros | pairing mode only |
| → 8a81 | `21` + bind ID(4) | bind |
| ← 8a82 | `a1` + challenge(4, big-endian) + zeros | every connection; the challenge is the device clock |
| → 8a81 | `20` + (challenge XOR password) | verify |
| → 8a81 | `02` + time(uint32 little-endian) | set device clock |
| ← 8a91 | reading, 17 bytes | see below |
| → 8a81 | `22` | after each reading, and to finish pairing; the device disconnects |

On the one device examined, the password equals the first four bytes of the serial number
(serial `A1B2C3D4E5F6`, password `a1 b2 c3 d4`). sphygmo derives it that way unless one is
given.

## Sequences

Pairing:

1. subscribe 0x8a91 and 0x8a82
2. ← `a0 a1 b2 c3 d4`
3. → `21 ff 00 00 01`
4. ← `a1 1f ca e9 60`
5. → `20 be 78 2a b4`
6. → `02 60 e9 ca 1f`
7. → `22` about 1.5 s later; the device shows "connected"

Without step 7 the device gives up after about 40 s and shows `E1`.

A measurement causes two connections:

1. At the start: handshake (`A1`, `20`, `02`), then every reading not yet transferred, each
   followed by `22`. Four buffered readings arrived within one second in a test.
2. At the end: handshake, the new reading 25 to 30 s later, `22`.

## Transfer semantics

A reading counts as transferred once its indication is confirmed. That confirmation comes
from the receiver's Bluetooth stack, not from the app. In a test, a reading left without
`22` was not sent again. A receiver must therefore store each reading before doing anything
else with it.

Re-pairing with a different bind ID does not resend old readings either. Neither the vendor
manual nor the open implementations below know a command to fetch the stored history.

## Reading

```
3e  79 00  4f 00  5d 00  8e e9 ca 1f  44 00  00  00 00 00
fl  sys    dia    map    time         pulse  usr rest
```

| Offset | Size | Field |
|---|---|---|
| 0 | 1 | flags, always `0x3e` so far |
| 1 | 2 | systolic, uint16 LE |
| 3 | 2 | diastolic, uint16 LE |
| 5 | 2 | probably mean arterial pressure |
| 7 | 4 | measurement time, uint32 LE |
| 11 | 2 | pulse, uint16 LE |
| 13 | 1 | user: `00` = user 1, `01` = user 2 |
| 14 | 3 | always zero so far |

Flag bits 1 to 4 match the standard Blood Pressure Measurement characteristic (0x2A35):
time, pulse, user, status. Bit 5 is set in addition. Unlike the standard, values are plain
integers, not SFLOAT. A reading taken with the arm moving still had all status bytes zero.

## Device clock

The challenge in `A1` is the device clock. In one session it lagged almost two hours behind
after the device had been idle, while in others it was exact. sphygmo sets the clock on
every connection; buffered readings may still carry a wrong time.

## Open points

- meaning of flag bit 5 and the three trailing bytes
- whether `02` (time) is required
- kPa unit (flag bit 0), if any device offers it
- the vendor app might know more opcodes; it has not been decompiled

## Related implementations

Both agree on `21`, `20`, `02` and `22` (named "disconnect" there).

- "Phulukisa BLE protocols for blood pressure monitors", section v3 Lifesense:
  https://gist.github.com/NecoHorne/2dd9713fbaf94d1d74259f554351975f
- `openble-lifesense` (scales), `packages/openble-lifesense/src/openble/lifesense/link.py` in
  https://github.com/kadima-tech/open-ble-hub. Adds scale-only commands `03` (user name)
  and `51` (user profile) and device packets `83` and `C0`. Not seen on blood pressure
  monitors; do not send them.
