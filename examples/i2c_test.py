#!/usr/bin/env python3
"""
Small command-line I2C read/write example for the DLN2 I2C wrapper.
"""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dln2.i2c import SMBus


def parse_int(value):
    return int(value, 0)


def main():
    parser = argparse.ArgumentParser(description="DLN2 I2C wrapper test")
    parser.add_argument("--address", required=True, type=parse_int, help="7-bit I2C address")
    parser.add_argument("--register", type=parse_int, default=0, help="Register offset")
    parser.add_argument("--read", type=int, default=1, help="Number of bytes to read")
    parser.add_argument(
        "--write",
        nargs="*",
        type=parse_int,
        default=None,
        help="Optional byte values to write after the register",
    )
    args = parser.parse_args()

    with SMBus(1) as bus:
        if args.write is not None:
            bus.write_i2c_block_data(args.address, args.register, args.write)
            print("write ok")

        data = bus.read_i2c_block_data(args.address, args.register, args.read)
        print("read:", " ".join(f"0x{value:02x}" for value in data))


if __name__ == "__main__":
    main()
