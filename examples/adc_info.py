#!/usr/bin/env python3
"""
Print one snapshot of DLN2 ADC channel values.
"""

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dln2.adc import ADC


def main():
    with ADC() as adc:
        count = adc.get_channel_count()
        for channel in range(count):
            adc.enable_channel(channel)
        snapshot = adc.read_all()

    payload = {
        "channel_count": count,
        "values": [
            {
                "channel": channel,
                "raw": raw,
                "voltage": raw * ADC.DEFAULT_VREF / ADC.DEFAULT_MAX_VALUE,
            }
            for channel, raw in enumerate(snapshot["values"])
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
