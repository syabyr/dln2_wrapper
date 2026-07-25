#!/usr/bin/env python3
"""
Watch GPIO events for one pin.
"""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dln2.gpio import GPIO, GPIO_EVENT_CHANGE


def parse_int(value):
    return int(value, 0)


def main():
    parser = argparse.ArgumentParser(description="Watch DLN2 GPIO events")
    parser.add_argument("--pin", type=parse_int, default=2, help="GPIO pin number")
    parser.add_argument("--count", type=int, default=0, help="Number of events, 0 means forever")
    parser.add_argument("--timeout-ms", type=int, default=1000, help="Poll timeout in milliseconds")
    args = parser.parse_args()

    with GPIO() as gpio:
        gpio.enable_pin(args.pin)
        gpio.set_direction(args.pin, GPIO.DIRECTION_IN)
        gpio.set_event(args.pin, GPIO_EVENT_CHANGE)

        remaining = args.count
        while True:
            event = gpio.poll_event(timeout_ms=args.timeout_ms)
            if event is None:
                print("timeout")
            else:
                print(json.dumps(event, sort_keys=True))
            if remaining:
                remaining -= 1
                if remaining <= 0:
                    break


if __name__ == "__main__":
    main()
