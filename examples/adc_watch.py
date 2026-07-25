#!/usr/bin/env python3
"""
Watch one ADC channel continuously.
"""

import argparse
import time
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dln2.adc import ADC


def parse_int(value):
    return int(value, 0)


def main():
    parser = argparse.ArgumentParser(description="Watch a DLN2 ADC channel")
    parser.add_argument("--channel", type=parse_int, default=0, help="ADC channel 0..2")
    parser.add_argument("--interval", type=float, default=0.5, help="Read interval in seconds")
    parser.add_argument("--count", type=int, default=0, help="Number of samples, 0 means forever")
    args = parser.parse_args()

    with ADC() as adc:
        adc.enable_channel(args.channel)
        remaining = args.count
        while True:
            raw = adc.read_channel(args.channel)
            volts = adc.to_voltage(raw)
            print(f"ch{args.channel}: raw={raw:4d} voltage={volts:.4f} V")
            if remaining:
                remaining -= 1
                if remaining <= 0:
                    break
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
