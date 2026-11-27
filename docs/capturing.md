# Help add your blood pressure monitor

Every supported device started with someone recording what their monitor says. You do not
need to write code. Three levels, pick what you can:

1. **Survey** with `sphygmo probe` (5 minutes, no vendor app needed)
2. **Capture** the vendor app talking to the monitor (30 minutes)
3. **Confirm** that a supported device works for you

Then open an issue with the matching template.

## 1. Survey: `sphygmo probe`

```bash
uvx sphygmo probe
```

`uvx` runs it without installing anything permanently ([uv](https://docs.astral.sh/uv/)).
Without uv:

```bash
python3 -m venv ~/.venvs/sphygmo && ~/.venvs/sphygmo/bin/pip install sphygmo
~/.venvs/sphygmo/bin/sphygmo probe
```

Start a measurement (most monitors only advertise around a measurement), pick your monitor
from the list, then let the measurement finish. The probe connects, lists all services and
characteristics, reads what is readable and records every packet for two minutes. It never
writes to the device.

If the monitor disappears before you have picked it, start the probe with a filter first and
then the measurement. The probe connects to the first device that matches:

```bash
sphygmo probe --match 02A0          # part of the advertised name
sphygmo probe --company 0x03FF      # Bluetooth company ID from the manufacturer data
sphygmo probe --service 1810        # an advertised service UUID, short or full
```

Many monitors send their name in only some packets; `--company` or `--service` then works
better. Some devices stop advertising after the first connection attempt, even a failed one,
so start the probe before the device (`--scan 120` waits two minutes for it) and give slow
ones more time with `--connect-timeout 60`.

The operating system may ask to pair the monitor when the probe connects. Accept it: some
devices refuse service discovery or subscriptions without it.

If connecting fails, the report is still written. It keeps the advertisement and names the
stage that failed (`connect`, `read`, `subscribe` or `listen`).

The report `sphygmo-probe.json` contains no Bluetooth address, and the serial number and
system ID are overwritten with `ee` bytes wherever they appear. It **may contain your
readings**; see [privacy](#privacy).

For a monitor that implements the standard Blood Pressure Service (0x1810) the probe often
records complete readings already. For vendor protocols it shows the structure, and a
capture is the next step.

## 2. Capture the vendor app

Close sphygmo while capturing, or it will compete with the app.

### iPhone

1. On developer.apple.com, under Profiles and Logs, install the **Bluetooth for iOS** profile
   on the iPhone (free Apple account is enough). **Restart the iPhone.**
2. On a Mac install **PacketLogger** from "Additional Tools for Xcode" (developer.apple.com,
   Downloads).
3. Connect the iPhone by cable, unlock it, trust the computer.
4. PacketLogger: **File, New iOS Trace**. Plain "New" records the Mac instead; if nothing
   scrolls by, that is the usual reason.
5. In the vendor app, remove the monitor, then pair it again. Take one or two measurements
   and let the app sync them.
6. File, Save, as `.pklg`.

### Android

1. Enable Developer options, then **Enable Bluetooth HCI snoop log**. Toggle Bluetooth off
   and on.
2. Remove the monitor in the vendor app, pair again, measure, sync.
3. Create a bug report (Developer options, Take bug report) and copy it to a computer. The
   log is inside the zip, usually under `FS/data/log/bt/btsnoop_hci.log` or
   `FS/data/misc/bluetooth/logs/`.
4. Switch the snoop log off again.

### Write down

The capture is hard to decode without these notes:

- every value the display showed (systolic, diastolic, pulse, any symbols), with the time
- which user slot was selected
- what you did and when: pair, measure, sync, error codes on the display

### Extract before sharing

A raw capture holds **all** Bluetooth traffic of the phone: your watch, headphones, their
names and addresses. Do not attach it publicly. Extract the monitor's connections instead
(needs Wireshark):

```bash
tools/extract_capture.py capture.pklg                       # lists connections
tools/extract_capture.py capture.pklg --conn 0x0051 --conn 0x0053 \
    --serial <serial number> > my-monitor.txt
```

Pairing and each later sync are separate connections; include them all. The serial number
shows up in the connection list if the app read it.

Some protocols derive a password from the serial number and use it in a handshake. The tool
overwrites the serial number and its first bytes, but values computed from it (for example
a challenge response) remain. If you are unsure, share the capture privately with a
maintainer instead.

## 3. Confirm a device

If your device is listed as supported, a short "it works" report with the model, firmware
(the probe shows it) and what you tested helps others.

## Privacy

Blood pressure readings are health data. Decoding a format needs real readings that match
the display, so they stay in reports and captures. If you do not want your own readings in
a public issue, take a few throwaway measurements just for the report, or ask in the issue
to share the files privately.
