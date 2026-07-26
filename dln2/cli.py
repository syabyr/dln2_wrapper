#!/usr/bin/env python3
"""DLN2 CLI commands — installed as console entry points."""

import argparse
import json
import re
import sys
import time


def _parse_int(value):
    return int(value, 0)


# ═══════════════════════════════════════════════════════════════
# GPIO
# ═══════════════════════════════════════════════════════════════

OUTPUT_ONLY_PINS = {23, 24, 25, 29}


def gpio_info():
    """Print GPIO pin count and current state for one pin."""
    from dln2.gpio import GPIO

    parser = argparse.ArgumentParser(description="Read one DLN2 GPIO pin")
    parser.add_argument("--pin", type=_parse_int, default=2, help="GPIO pin number")
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


def gpio_toggle():
    """Toggle a DLN2 GPIO pin, defaulting to the Pico onboard LED."""
    from dln2.gpio import GPIO

    parser = argparse.ArgumentParser(description="Toggle a DLN2 GPIO pin")
    parser.add_argument("--pin", type=_parse_int, default=25, help="GPIO pin number (default: Pico LED pin 25)")
    parser.add_argument("--count", type=int, default=10, help="Number of toggles")
    parser.add_argument("--interval", type=float, default=0.5, help="Delay between toggles in seconds")
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


def gpio_watch():
    """Watch GPIO events for one pin."""
    from dln2.gpio import GPIO, GPIO_EVENT_CHANGE

    parser = argparse.ArgumentParser(description="Watch DLN2 GPIO events")
    parser.add_argument("--pin", type=_parse_int, default=2, help="GPIO pin number (default: 2)")
    parser.add_argument("--count", type=int, default=0, help="Number of events, 0 means forever")
    parser.add_argument("--timeout-ms", type=int, default=1000, help="Poll timeout in milliseconds")
    args = parser.parse_args()

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


# ═══════════════════════════════════════════════════════════════
# ADC
# ═══════════════════════════════════════════════════════════════

def adc_info():
    """Print one snapshot of DLN2 ADC channel values as JSON."""
    from dln2.adc import ADC

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


def adc_watch():
    """Watch one ADC channel continuously."""
    from dln2.adc import ADC

    parser = argparse.ArgumentParser(description="Watch a DLN2 ADC channel")
    parser.add_argument("--channel", type=_parse_int, default=0, help="ADC channel 0..2")
    parser.add_argument("--interval", type=float, default=0.5, help="Read interval in seconds")
    parser.add_argument("--count", type=int, default=0, help="Number of samples, 0 means forever")
    args = parser.parse_args()

    try:
        with ADC() as adc:
            adc.enable_channel(args.channel)
            remaining = args.count
            try:
                while True:
                    raw = adc.read_channel(args.channel)
                    volts = adc.to_voltage(raw)
                    print(f"ch{args.channel}: raw={raw:4d} voltage={volts:.4f} V")
                    if remaining:
                        remaining -= 1
                        if remaining <= 0:
                            break
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print(file=sys.stderr)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        print("Stopped.", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════
# I2C
# ═══════════════════════════════════════════════════════════════

def _is_expected_nack(exc):
    return "failed: 186" in str(exc)


def i2c_scan():
    """Scan the I2C bus exposed by the DLN2 I2C wrapper."""
    from dln2 import Dln2Connection
    from dln2.i2c import SMBus

    parser = argparse.ArgumentParser(description="Scan the DLN2 I2C bus")
    parser.add_argument("--start", type=_parse_int, default=0x03, help="First 7-bit address to probe")
    parser.add_argument("--end", type=_parse_int, default=0x77, help="Last 7-bit address to probe")
    parser.add_argument("--read-len", type=int, default=1, help="Probe length in bytes")
    parser.add_argument("--register", type=_parse_int, default=None, help="Optional register address")
    parser.add_argument("--debug", action="store_true", help="Enable raw DLN2 USB debug output")
    args = parser.parse_args()

    found = []
    errors = {}

    conn = Dln2Connection(debug=args.debug)
    try:
        with SMBus(conn) as bus:
            for addr in range(args.start, args.end + 1):
                try:
                    if args.register is None:
                        bus.read_byte(addr)
                    else:
                        bus.read_i2c_block_data(addr, args.register, args.read_len)
                    found.append(addr)
                except RuntimeError as exc:
                    if _is_expected_nack(exc):
                        continue
                    msg = str(exc)
                    key = re.sub(r'0x[0-9A-Fa-f]{2}', '0xXX', msg)
                    errors.setdefault(key, 0)
                    errors[key] += 1
    finally:
        conn.close()

    # Format table
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
    print("\n".join(lines))

    if found:
        print("\nResponding addresses:", " ".join(f"0x{addr:02x}" for addr in found))
    else:
        print("\nResponding addresses: <none>")

    if errors:
        print("\nProbe errors:")
        for message, count in sorted(errors.items()):
            print(f"  {count}x {message}")


def i2c_test():
    """Small command-line I2C read/write test."""
    from dln2.i2c import SMBus

    parser = argparse.ArgumentParser(description="DLN2 I2C wrapper test")
    parser.add_argument("--address", required=True, type=_parse_int, help="7-bit I2C address")
    parser.add_argument("--register", type=_parse_int, default=0, help="Register offset")
    parser.add_argument("--read", type=int, default=1, help="Number of bytes to read")
    parser.add_argument(
        "--write", nargs="*", type=_parse_int, default=None,
        help="Optional byte values to write after the register",
    )
    args = parser.parse_args()

    try:
        with SMBus() as bus:
            if args.write is not None:
                bus.write_i2c_block_data(args.address, args.register, args.write)
                print("write ok")

            data = bus.read_i2c_block_data(args.address, args.register, args.read)
            print("read:", " ".join(f"0x{value:02x}" for value in data))
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# BME280
# ═══════════════════════════════════════════════════════════════

def bme280():
    """Read BME280 sensor values (chip ID + measurements)."""
    from dln2.bme280 import BME280

    parser = argparse.ArgumentParser(description="Read BME280 values over DLN2 I2C")
    parser.add_argument("--address", type=_parse_int, default=0x76, help="BME280 I2C address")
    parser.add_argument("--pretty", action="store_true", help="Print pretty JSON")
    args = parser.parse_args()

    try:
        with BME280(address=args.address) as sensor:
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
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# SPI
# ═══════════════════════════════════════════════════════════════

def spi_test():
    """Send SPI JEDEC ID command and print response."""
    from dln2.spi import SpiDev

    parser = argparse.ArgumentParser(description="DLN2 SPI test (JEDEC ID read)")
    parser.add_argument("--host-cs", action="store_true", help="Hold CS across transfers")
    parser.add_argument("--verbose", action="store_true", help="Show verbose debug output")
    args = parser.parse_args()

    try:
        dev = SpiDev()
        dev.host_hold_cs = bool(args.host_cs)
        dev.debug = bool(args.verbose)
    except Exception as e:
        print(f"Error: Failed to open DLN2 device: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        print("Opening SpiDev (DLN backend)...")
        dev.max_speed_hz = 1_000_000
        dev.mode = 0
        dev.bits_per_word = 8
        dev.open(0, 0)
        tx = [0x9F, 0x00, 0x00, 0x00]
        print("Sending JEDEC (0x9F) via DLN wrapper... host_hold_cs=", dev.host_hold_cs)
        rx = dev.xfer2(tx)
        print("RX bytes:", rx)
        print("RX hex :", "".join(f"{b:02x}" for b in rx))
    except Exception as e:
        print(f"Test failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            dev.close()
        except Exception:
            pass


def bpw_test():
    """Cycle SPI bits-per-word 8 and 16 sending a test pattern at each setting."""
    from dln2.spi import SpiDev

    print("Sending one transfer for BPW 8 and 16")
    try:
        with SpiDev() as dev:
            dev.max_speed_hz = 1_000_000
            dev.mode = 0

            for bpw in (8, 16):
                dev.bits_per_word = bpw
                dev.open(0, 0)

                mask = (1 << bpw) - 1
                pattern = 0xAA if bpw <= 8 else 0xAAAA
                pattern &= mask

                try:
                    rx = dev.xfer2([pattern])
                    print(f"bpw={bpw:2d}  tx={pattern:#06x}  rx={rx}")
                except Exception as e:
                    print(f"bpw={bpw:2d}  tx={pattern:#06x}  FAILED: {e}")

                dev.close()
                time.sleep(0.2)

            print("Done.")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
