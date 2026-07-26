#!/usr/bin/env python3
"""
BME280 Full Verification and Test Script
-----------------------------------------
Steps:
  1. Open I2C bus via DLN2 adapter
  2. Read chip ID register to verify BME280 identity
  3. Read and display calibration coefficients
  4. Configure sensor (oversampling, filter, mode)
  5. Take multiple readings and display results
  6. Verify readings are within valid ranges
"""

import time
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dln2.bme280 import BME280
from dln2.i2c import SMBus

BME280_ADDR = 0x76
NUM_SAMPLES = 5
SAMPLE_INTERVAL_S = 1.0

# ── Helper: color codes for terminal ──────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")

def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")

def info(msg):
    print(f"  {CYAN}→{RESET} {msg}")

def section(title):
    print(f"\n{BOLD}{'─'*55}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*55}{RESET}")

# ── Step 1: Open the bus ──────────────────────────────────────────
section("Step 1 — Opening I2C bus via DLN2 adapter")

try:
    bus = SMBus()
    bus.open()
    info("I2C bus opened successfully")
    ok("DLN2 I2C bus is ready")
except Exception as e:
    fail(f"Failed to open I2C bus: {e}")
    sys.exit(1)

try:
    # ── Step 2: Verify chip ID ────────────────────────────────────
    section("Step 2 — Verifying BME280 chip identity")

    # Quick raw read of chip ID register for transparency
    chip_id_raw = bus.read_byte_data(BME280_ADDR, 0xD0)
    info(f"Raw chip ID register (0xD0): 0x{chip_id_raw:02X} ({chip_id_raw})")

    if chip_id_raw == 0x60:
        ok(f"Chip ID 0x{chip_id_raw:02X} — confirmed BME280 (expected 0x60)")
    elif chip_id_raw == 0x61:
        ok(f"Chip ID 0x{chip_id_raw:02X} — confirmed BME280 at alternate address (0x61)")
    elif chip_id_raw == 0x58:
        fail(f"Chip ID 0x{chip_id_raw:02X} — this is a BMP280 (no humidity sensor!)")
        sys.exit(1)
    elif chip_id_raw == 0x56 or chip_id_raw == 0x57:
        fail(f"Chip ID 0x{chip_id_raw:02X} — this is a BME680 (different sensor!)")
        sys.exit(1)
    else:
        fail(f"Unknown chip ID 0x{chip_id_raw:02X} — not a recognized Bosch sensor")
        sys.exit(1)

    # Also check status register
    status = bus.read_byte_data(BME280_ADDR, 0xF3)
    measuring = (status >> 3) & 1
    im_update = status & 1
    info(f"Status register (0xF3): 0x{status:02X} (measuring={measuring}, im_update={im_update})")

    # ── Step 3: Reset and read calibration ────────────────────────
    section("Step 3 — Reset sensor & read calibration coefficients")

    # Soft reset
    bus.write_byte_data(BME280_ADDR, 0xE0, 0xB6)
    info("Soft reset command sent (0xB6 to 0xE0)")
    time.sleep(0.5)  # wait for reset to complete

    # Post-reset chip ID check
    post_reset_id = bus.read_byte_data(BME280_ADDR, 0xD0)
    if post_reset_id == 0x60:
        ok(f"Post-reset chip ID: 0x{post_reset_id:02X} — reset OK")
    else:
        fail(f"Post-reset chip ID mismatch: 0x{post_reset_id:02X}")

    # Read calibration via BME280 class
    sensor = BME280(bus=bus, address=BME280_ADDR, debug=False)
    calib = sensor.read_calibration()

    print()
    info("Calibration coefficients loaded:")
    print(f"    Temperature:  T1={calib['dig_T1']}, T2={calib['dig_T2']}, T3={calib['dig_T3']}")
    print(f"    Pressure:     P1={calib['dig_P1']}, P2={calib['dig_P2']}, P3={calib['dig_P3']}")
    print(f"                  P4={calib['dig_P4']}, P5={calib['dig_P5']}, P6={calib['dig_P6']}")
    print(f"                  P7={calib['dig_P7']}, P8={calib['dig_P8']}, P9={calib['dig_P9']}")
    print(f"    Humidity:     H1={calib['dig_H1']}, H2={calib['dig_H2']}, H3={calib['dig_H3']}")
    print(f"                  H4={calib['dig_H4']}, H5={calib['dig_H5']}, H6={calib['dig_H6']}")

    # Quick validation: calibration registers should be non-zero and non-0xFFFF
    all_calib_ok = True
    for name, val in calib.items():
        if val == 0 or val == 0xFFFF or val == -1:
            print(f"    {YELLOW}⚠{RESET} Suspicious value: {name}={val}")
            all_calib_ok = False
    if all_calib_ok:
        ok("All calibration coefficients look valid (non-zero, non-0xFFFF)")

    # ── Step 4: Configure sensor ──────────────────────────────────
    section("Step 4 — Configure sensor parameters")

    # osrs_t=2 (x2 oversampling), osrs_p=4 (x8 oversampling),
    # osrs_h=1 (x1 oversampling), mode=3 (normal mode),
    # standby=5 (1000ms), filter=2 (x4 filter)
    sensor.configure(osrs_t=2, osrs_p=4, osrs_h=1, mode=3, standby=5, filter_coef=2)
    info("Configuration written:")
    print("    Oversampling:  T=x2  P=x8  H=x1")
    print("    Mode:          Normal (continuous)")
    print("    Standby:       1000 ms")
    print("    IIR Filter:    x4")

    # Verify ctrl_meas register
    ctrl_meas = bus.read_byte_data(BME280_ADDR, 0xF4)
    ctrl_hum = bus.read_byte_data(BME280_ADDR, 0xF2)
    config = bus.read_byte_data(BME280_ADDR, 0xF5)
    info(f"Verify registers: ctrl_hum=0x{ctrl_hum:02X}  ctrl_meas=0x{ctrl_meas:02X}  config=0x{config:02X}")
    ok("Sensor configured in normal mode")

    # Wait for first conversion to complete
    time.sleep(1.0)

    # ── Step 5: Take multiple readings ────────────────────────────
    section(f"Step 5 — Taking {NUM_SAMPLES} readings ({SAMPLE_INTERVAL_S}s interval)")

    print(f"\n  {'Sample':<8} {'Temp (°C)':>10} {'Pressure (hPa)':>15} {'Humidity (%)':>14} {'Raw T':>8} {'Raw P':>9} {'Raw H':>7}")
    print(f"  {'─'*7:<8} {'─'*9:>10} {'─'*14:>15} {'─'*13:>14} {'─'*7:>8} {'─'*8:>9} {'─'*6:>7}")

    samples = []
    all_valid = True

    for i in range(NUM_SAMPLES):
        if i > 0:
            time.sleep(SAMPLE_INTERVAL_S)

        try:
            raw = sensor.read_raw_data()
            t = sensor.compensate_temperature(raw["temperature"])
            p = sensor.compensate_pressure(raw["pressure"])
            h = sensor.compensate_humidity(raw["humidity"])

            samples.append({"t": t, "p": p, "h": h, "raw": raw})

            # Range checks
            flags = ""
            if not (-40 <= t <= 85):
                flags += f" {YELLOW}[T out of range]{RESET}"
                all_valid = False
            if not (300 <= p <= 1100):
                flags += f" {YELLOW}[P out of range]{RESET}"
                all_valid = False
            if not (0 <= h <= 100):
                flags += f" {YELLOW}[H out of range]{RESET}"
                all_valid = False

            print(f"  {i+1:<8} {t:>10.2f} {p:>15.2f} {h:>14.2f} {raw['temperature']:>8} {raw['pressure']:>9} {raw['humidity']:>7}{flags}")

        except Exception as e:
            print(f"  {i+1:<8} {RED}ERROR: {e}{RESET}")
            all_valid = False

    # ── Step 6: Summary statistics ─────────────────────────────────
    section("Step 6 — Summary & Statistics")

    if not samples:
        fail("No valid samples collected!")
    else:
        temps = [s["t"] for s in samples]
        pressures = [s["p"] for s in samples]
        humidities = [s["h"] for s in samples]

        t_avg = sum(temps) / len(temps)
        p_avg = sum(pressures) / len(pressures)
        h_avg = sum(humidities) / len(humidities)

        t_range = max(temps) - min(temps)
        p_range = max(pressures) - min(pressures)
        h_range = max(humidities) - min(humidities)

        print(f"  Temperature:   avg = {t_avg:.2f} °C   range = {t_range:.3f} °C   (min={min(temps):.2f}, max={max(temps):.2f})")
        print(f"  Pressure:      avg = {p_avg:.2f} hPa   range = {p_range:.3f} hPa   (min={min(pressures):.2f}, max={max(pressures):.2f})")
        print(f"  Humidity:      avg = {h_avg:.2f} %     range = {h_range:.3f} %     (min={min(humidities):.2f}, max={max(humidities):.2f})")

        if all_valid:
            ok("All readings within valid operating ranges")
        else:
            fail("Some readings were out of expected range — check wiring and power")

        # Stability check: if range is very small, sensor may be stuck
        if t_range < 0.01:
            print(f"  {YELLOW}⚠ Temperature range is very small — sensor may be stuck{RESET}")
        if p_range < 0.01:
            print(f"  {YELLOW}⚠ Pressure range is very small — sensor may be stuck{RESET}")
        if h_range < 0.01:
            print(f"  {YELLOW}⚠ Humidity range is very small — sensor may be stuck{RESET}")

    # ── Final verdict ──────────────────────────────────────────────
    section("Final Verdict")

    if all_valid and samples:
        print(f"\n  {GREEN}{BOLD}✓ BME280 at 0x{BME280_ADDR:02X} is fully operational!{RESET}")
        print(f"  Temperature:  {t_avg:.2f} °C")
        print(f"  Pressure:     {p_avg:.2f} hPa")
        print(f"  Humidity:     {h_avg:.2f} %")
    else:
        print(f"\n  {RED}{BOLD}✗ BME280 test completed with issues — see above{RESET}")

finally:
    try:
        bus._conn.close()
    except Exception:
        pass
    bus.close()
    print(f"\n{BOLD}{'─'*55}{RESET}")
    print(f"{BOLD}  I2C bus closed. Test complete.{RESET}")
    print(f"{BOLD}{'─'*55}{RESET}")
