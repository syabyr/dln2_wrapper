#!/usr/bin/env python3
"""
Watch GPIO events for one pin.

Pins that support input/events: 0-22, 26-28
Pins that are output-only (no events): 23, 24, 25, 29
  (Pin 25 is the Pico's onboard LED.)
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
    parser.add_argument("--pin", type=parse_int, default=2, help="GPIO pin number (default: 2)")
    parser.add_argument("--count", type=int, default=0, help="Number of events, 0 means forever")
    parser.add_argument("--timeout-ms", type=int, default=1000, help="Poll timeout in milliseconds")
    args = parser.parse_args()

    OUTPUT_ONLY_PINS = {23, 24, 25, 29}

    if args.pin in OUTPUT_ONLY_PINS:
        print(f"Error: Pin {args.pin} is output-only and does not support input/event detection.",
              file=sys.stderr)
        print("Try a different pin, e.g. --pin 2", file=sys.stderr)
        sys.exit(1)

    try:
        with GPIO() as gpio:
            gpio.enable_pin(args.pin)
            gpio.set_direction(args.pin, GPIO.DIRECTION_IN)
            gpio.set_event(args.pin, GPIO_EVENT_CHANGE)

            remaining = args.count
            try:
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
            except KeyboardInterrupt:
                print(file=sys.stderr)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        print("Stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
