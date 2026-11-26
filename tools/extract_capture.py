#!/usr/bin/env python3
"""Turn a raw Bluetooth capture into a text log that is safe to publish.

A PacketLogger (.pklg) or Android btsnoop capture holds all Bluetooth traffic of the phone:
other devices, their names and addresses. This keeps only the ATT traffic of one connection
and overwrites the serial number (and any extra secrets you name) wherever it appears.

Requires tshark (Wireshark). Usage:

    tools/extract_capture.py capture.pklg                      # list connections
    tools/extract_capture.py capture.pklg --conn 0x0051 --conn 0x0053 --serial A1B2C3D4E5F6 > capture.txt

Each connection gets a new handle, so pairing and a later measurement are separate --conn values.

Blood pressure readings stay in the output; they are needed to decode the format.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from sphygmo.redact import redact_bytes  # noqa: E402

OPS = {"0x01": "error", "0x02": "mtu req", "0x03": "mtu rsp", "0x08": "read type req",
       "0x09": "read type rsp", "0x10": "read group req", "0x11": "read group rsp",
       "0x0a": "read req", "0x0b": "read rsp", "0x12": "write req", "0x13": "write rsp",
       "0x52": "write cmd", "0x1b": "notification", "0x1d": "indication", "0x1e": "confirmation"}
FROM_DEVICE = {"0x01", "0x03", "0x09", "0x0b", "0x11", "0x13", "0x1b", "0x1d"}


def tshark(capture: Path, display_filter: str, fields: list[str]) -> list[list[str]]:
    exe = shutil.which("tshark") or "/Applications/Wireshark.app/Contents/MacOS/tshark"
    cmd = [exe, "-r", str(capture), "-Y", display_filter, "-T", "fields", "-E", "separator=\t"]
    for f in fields:
        cmd += ["-e", f]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture", type=Path)
    ap.add_argument("--conn", action="append", default=[], help="ACL connection handle, e.g. 0x0051 (repeatable)")
    ap.add_argument("--serial", action="append", default=[], help="serial number to overwrite (repeatable)")
    ap.add_argument("--secret", action="append", default=[], help="further hex value to overwrite, e.g. a password")
    a = ap.parse_args()

    if not a.conn:
        rows = tshark(a.capture, "btatt", ["bthci_acl.chandle", "frame.time_relative", "btatt.opcode", "btatt.value"])
        print("Connections with ATT traffic (pick the monitor with --conn):")
        texts: dict[str, list[str]] = {}
        for handle, _, op, value in ((r + ["", "", ""])[:4] for r in rows):
            if op == "0x0b" and value:
                try:
                    text = bytes.fromhex(value).decode("ascii")
                except UnicodeDecodeError:
                    continue
                if text.isprintable() and len(texts.setdefault(handle, [])) < 4:
                    texts[handle].append(text)
        for handle, n in Counter(r[0] for r in rows).most_common():
            start = min(float(r[1]) for r in rows if r[0] == handle)
            print(f"  {handle}  {n:4} packets  from {start:8.1f} s  strings read: {texts.get(handle, [])}")
        print("Strings may include the serial number; pass it with --serial.")
        return

    secrets = a.serial + a.secret
    print("# ATT traffic extracted with sphygmo tools/extract_capture.py")
    print("# Columns: seconds since first packet, direction (-> phone to device), ATT op, handle, value")
    rows = tshark(a.capture, "btatt && (" + " || ".join(f"bthci_acl.chandle == {c}" for c in a.conn) + ")",
                  ["bthci_acl.chandle", "frame.time_relative", "btatt.opcode", "btatt.handle", "btatt.value"])
    if not rows:
        sys.exit(f"no ATT packets on {a.conn}")
    t0 = float(rows[0][1])
    current = None
    for row in rows:
        conn, row = row[0], row[1:]
        if conn != current:
            print(f"#\n# Connection {conn}")
            current = conn
        t, op, handle, value = (row + ["", "", ""])[:4]
        data = redact_bytes(bytes.fromhex(value), secrets) if value else b""
        direction = "<-" if op in FROM_DEVICE else "->"
        print(f"{float(t) - t0:8.3f}  {direction} {OPS.get(op, op):<12} {handle or '':<7} {data.hex(' ')}")


if __name__ == "__main__":
    main()
