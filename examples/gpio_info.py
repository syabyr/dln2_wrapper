#!/usr/bin/env python3
"""
Print GPIO pin count and current state for one pin.
"""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dln2.gpio import GPIO


def parse_int(value):
    return int(value, 0)


def main():
    parser = argparse.ArgumentParser(description="Read one DLN2 GPIO pin")
    parser.add_argument("--pin", type=parse_int, default=2, help="GPIO pin number")
    args = parser.parse_args()

    with GPIO() as gpio:
        pin_count = gpio.get_pin_count()
        gpio.enable_pin(args.pin)
        direction = gpio.get_direction(args.pin)
        value = gpio.read(args.pin)

    print(
        json.dumps(
            {
                "pin_count": pin_count,
                "pin": args.pin,
                "direction": direction,
                "value": value,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
