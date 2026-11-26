# visomat cardiovision / iProven BPM-2244 BT

Upper-arm blood pressure monitor by UEBE (visomat), also sold as iProven BPM-2244 BT
(BPM2244, BPM-2244BT). Made by Transtek. Two users, 31 stored readings per the manual.
Normally read with the MedM app; sphygmo reads it directly over Bluetooth LE, without MedM
or MedM Premium.

> **Deutsch:** Das Blutdruckmessgerät visomat cardiovision lässt sich mit sphygmo per
> Bluetooth ohne die MedM-App auslesen. Kopplung, Live-Messung, nachgelieferte Messwerte und
> beide Benutzer funktionieren. Ältere, bereits übertragene Werte aus dem Gerätespeicher
> lassen sich nicht abrufen.

| Identifier | Value |
|---|---|
| Advertised name | `1802A0` (pairing mode), `0802A0` + bind ID when bound, e.g. `0802A0FF000001` |
| Service | `0x7809` (`00007809-0000-1000-8000-00805f9b34fb`) |
| Display errors | `E1` after a failed pairing |

| Item | Value |
|---|---|
| Manufacturer (Device Information) | Transtek |
| Hardware / firmware / software | `B2` / `2.2` / `A2` |
| Radio | BLE only, no OS-level bonding |
| Standard Blood Pressure Service 0x1810 | no |
| Protocol | [transtek-7809](../protocols/transtek-7809.md) |
| Driver | `transtek_7809` |

## Notes

- The vendor app is MedM. Uninstall it, or switch Bluetooth off on the phone, while sphygmo
  is listening; whichever side connects first gets the readings.
- A device already bound to MedM works with sphygmo too, the bind ID is only exchanged at
  pairing time. sphygmo still wants to see one pairing (`--pair`) before it serves the device.
- Readings stored before sphygmo was used cannot be retrieved over Bluetooth.
