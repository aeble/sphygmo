# Related projects

Projects that read blood pressure monitors without the vendor app. Each covers one brand or
the standard profile; none combines pluggable device drivers with several outputs, which is
what sphygmo tries to do. Check each project's license before reusing code: sphygmo is
Apache-2.0, and code without a license or under (A)GPL cannot be copied in.

## Protocol references

| Project | Devices | Notes | License |
|---|---|---|---|
| [Phulukisa BLE protocols](https://gist.github.com/NecoHorne/2dd9713fbaf94d1d74259f554351975f) | Lifesense / Transtek blood pressure (v3) | Same handshake opcodes as [transtek-7809](protocols/transtek-7809.md); reading the data is unfinished there | none stated |
| [open-ble-hub, openble-lifesense](https://github.com/kadima-tech/open-ble-hub) | Lifesense scales | Same characteristic family, adds scale-only commands | MIT |
| [openScale wiki, Medisana BS444](https://github.com/oliexdev/openScale/wiki/Medisana-BS444) | Transtek-made scale | Time sync command on 0x8a81 | GPL-3.0 |

## Bridges and readers

| Project | Devices | Output | License |
|---|---|---|---|
| [omblepy](https://github.com/userx14/omblepy) | Omron, one module per model | CSV | none stated |
| [hass-omron](https://github.com/eigger/hass-omron) | Omron | Home Assistant | MIT |
| [esphome-omron](https://github.com/dzikus/esphome-omron) | Omron | ESPHome | GPL-3.0 |
| [BLE-Vitals-Bridge](https://github.com/ipanalytics/BLE-Vitals-Bridge) | standard blood pressure and weight profiles | SQLite, CSV | MIT |
| [sbm70-mqtt](https://github.com/bandiv/sbm70-mqtt) | Sanitas SBM 70 | MQTT with Home Assistant discovery | MIT |
| [open-pressure](https://github.com/scolastico/open-pressure) | Omron, standard profile | Android app, Health Connect | MIT |
| [Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge) | e.g. Sanitas SBM67 (standard profile) | Android app | AGPL-3.0 |

Several Home Assistant integrations exist for single brands (Medisana, A&D, iHealth, Braun,
Veroval).

Missing something? Open a pull request.
