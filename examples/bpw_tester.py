#!/usr/bin/env python3
"""
DLN2 SPI bits-per-word tester.

Cycles bpw 4..16 sending a test pattern at each setting.
Use with a logic analyzer or scope to verify frame sizes.
"""

import time
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dln2.spi import SpiDev


def main():
    try:
        with SpiDev() as dev:
            dev.open(0, 0)
            dev.max_speed_hz = 1_000_000
            dev.mode = 0

            print("Sending one transfer for each BPW 4..16")
            for bpw in range(4, 17):
                dev.bits_per_word = bpw

                if bpw <= 8:
                    pattern = 0xAA & ((1 << bpw) - 1)
                else:
                    pattern = 0xAAAA & ((1 << bpw) - 1)

                try:
                    rx = dev.xfer2([pattern])
                    print(f"bpw={bpw:2d}  tx={pattern:#06x}  rx={rx}")
                except Exception as e:
                    print(f"bpw={bpw:2d}  tx={pattern:#06x}  FAILED: {e}")

                time.sleep(0.1)

            print("Done.")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
