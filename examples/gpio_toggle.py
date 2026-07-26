#!/usr/bin/env python3
"""
Toggle a DLN2 GPIO pin, defaulting to the Pico onboard LED.
"""

import argparse
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dln2.gpio import GPIO


def parse_int(value):
    return int(value, 0)


def main():
    parser = argparse.ArgumentParser(description="Toggle a DLN2 GPIO pin")
    parser.add_argument(
        "--pin",
        type=parse_int,
        default=25,
        help="GPIO pin number to toggle, default is Pico onboard LED pin 25",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of toggles to perform",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Delay between toggles in seconds",
    )
    args = parser.parse_args()

    try:
        with GPIO() as gpio:
            gpio.enable_pin(args.pin)
            gpio.set_direction(args.pin, GPIO.DIRECTION_OUT)

            try:
                for index in range(args.count):
                    value = gpio.toggle(args.pin)
                    print(f"toggle {index + 1}: pin={args.pin} value={value}")
                    if index != args.count - 1:
                        time.sleep(args.interval)
            except KeyboardInterrupt:
                print(file=sys.stderr)

            gpio.disable_pin(args.pin)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        print("Stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
