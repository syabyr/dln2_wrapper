#!/usr/bin/env python3
"""
Read chip ID and one measurement frame from a BME280 over DLN2 I2C.
"""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dln2_i2c_wrapper import BME280


def parse_int(value):
    return int(value, 0)


def main():
    parser = argparse.ArgumentParser(description="Read BME280 values over DLN2 I2C")
    parser.add_argument("--address", type=parse_int, default=0x76, help="BME280 I2C address")
    parser.add_argument("--pretty", action="store_true", help="Print pretty JSON")
    args = parser.parse_args()

    with BME280(bus=1, address=args.address) as sensor:
        chip_id = sensor.check_chip_id()
        sensor.read_calibration()
        sensor.configure()
        measurement = sensor.read_measurements()

    payload = {
        "address": args.address,
        "chip_id": chip_id,
        **measurement,
    }
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
