# visomat cardiovision

Sold by UEBE as visomat cardiovision; the same device is sold as iProven BPM-2244 BT.
Upper-arm monitor, two users, 31 stored readings per the manual.

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
- A bound device keeps working with sphygmo without re-pairing, as long as you connect with
  the same password; the bind ID is only checked at pairing time.
- Readings stored before sphygmo was used cannot be retrieved over Bluetooth.
