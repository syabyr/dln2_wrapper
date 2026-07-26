#!/usr/bin/env python3
"""
Scan the I2C bus exposed by the DLN2 I2C wrapper.
"""

import argparse
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dln2 import Dln2Connection
from dln2.i2c import SMBus


def parse_int(value):
    return int(value, 0)


def is_expected_nack(exc):
    return "failed: 186" in str(exc)


def format_table(found):
    header = ["    "] + [f"{col:x}" for col in range(16)]
    lines = [" ".join(header)]
    found_set = set(found)

    for base in range(0x00, 0x80, 0x10):
        row = [f"{base:02x}:"]
        for offset in range(16):
            addr = base + offset
            if addr < 0x03 or addr > 0x77:
                row.append("  ")
            elif addr in found_set:
                row.append(f"{addr:02x}")
            else:
                row.append("--")
        lines.append(" ".join(row))
    return "\n".join(lines)


def probe_address(bus, addr, read_len, register=None):
    if register is None:
        bus.read_byte(addr)
        return
    bus.read_i2c_block_data(addr, register, read_len)


def scan_bus(start, end, read_len, register=None, debug=False):
    found = []
    errors = {}

    conn = Dln2Connection(debug=debug)
    try:
        with SMBus(conn) as bus:
            for addr in range(start, end + 1):
                try:
                    probe_address(bus, addr, read_len, register=register)
                    found.append(addr)
                except RuntimeError as exc:
                    if is_expected_nack(exc):
                        continue
                    msg = str(exc)
                    # Normalise addresses to group identical error types
                    key = re.sub(r'0x[0-9A-Fa-f]{2}', '0xXX', msg)
                    errors.setdefault(key, 0)
                    errors[key] += 1
    finally:
        conn.close()

    return found, errors


def main():
    parser = argparse.ArgumentParser(description="Scan the DLN2 I2C bus")
    parser.add_argument(
        "--start",
        type=parse_int,
        default=0x03,
        help="First 7-bit address to probe",
    )
    parser.add_argument(
        "--end",
        type=parse_int,
        default=0x77,
        help="Last 7-bit address to probe",
    )
    parser.add_argument(
        "--read-len",
        type=int,
        default=1,
        help="Probe length in bytes; default 1 is safest for this firmware",
    )
    parser.add_argument(
        "--register",
        type=parse_int,
        default=None,
        help="Optional register address for register-based probing",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable raw DLN2 USB debug output",
    )
    args = parser.parse_args()

    found, errors = scan_bus(
        args.start,
        args.end,
        args.read_len,
        register=args.register,
        debug=args.debug,
    )

    print(format_table(found))
    if found:
        print("\nResponding addresses:", " ".join(f"0x{addr:02x}" for addr in found))
    else:
        print("\nResponding addresses: <none>")

    if errors:
        print("\nProbe errors:")
        for message, count in sorted(errors.items()):
            if count > 1:
                print(f"  {count}x {message}")
            else:
                print(f"  {message}")


if __name__ == "__main__":
    main()
