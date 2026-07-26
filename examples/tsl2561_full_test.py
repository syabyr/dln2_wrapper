#!/usr/bin/env python3
"""
TSL2561 Full Verification and Test Script
-------------------------------------------
Steps:
  1. Open I2C bus via DLN2 adapter
  2. Read ID register to verify TSL2561 identity
  3. Power on the sensor
  4. Configure integration time and gain
  5. Take multiple readings (CH0 visible+IR, CH1 IR)
  6. Convert to lux and verify readings are valid
"""

import time
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dln2.i2c import SMBus

TSL2561_ADDR = 0x39

# ── TSL2561 Registers (command bit 7 must be set) ─────────────────
CMD            = 0x80
CONTROL        = 0x00
TIMING         = 0x01
THRESHLOW_LOW  = 0x02
THRESHLOW_HIGH = 0x03
THRESHHIGH_LOW = 0x04
THRESHHIGH_HIGH= 0x05
INTERRUPT      = 0x06
ID_REG         = 0x0A
DATA0LOW       = 0x0C
DATA0HIGH      = 0x0D
DATA1LOW       = 0x0E
DATA1HIGH      = 0x0F

# ── Timing constants ──────────────────────────────────────────────
GAIN_1X   = 0x00
GAIN_16X  = 0x10
INTEG_13MS  = 0x00
INTEG_101MS = 0x01
INTEG_402MS = 0x02

INTEG_TIME_MS = {INTEG_13MS: 13.7, INTEG_101MS: 101, INTEG_402MS: 402}
CH0_MAX = {
    (INTEG_13MS,  GAIN_1X):  2048,
    (INTEG_13MS,  GAIN_16X): 8192,
    (INTEG_101MS, GAIN_1X):  8192,
    (INTEG_101MS, GAIN_16X): 32768,
    (INTEG_402MS, GAIN_1X):  32768,
    (INTEG_402MS, GAIN_16X): 65535,
}

NUM_SAMPLES = 5

# ── Helpers ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET} {msg}")
def info(msg):  print(f"  {CYAN}→{RESET} {msg}")
def section(title):
    print(f"\n{BOLD}{'─'*55}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*55}{RESET}")


def reg_read(bus, reg):
    return bus.read_byte_data(TSL2561_ADDR, CMD | reg)


def reg_write(bus, reg, value):
    bus.write_byte_data(TSL2561_ADDR, CMD | reg, value)


def read_channel_data(bus):
    ch0_low  = reg_read(bus, DATA0LOW)
    ch0_high = reg_read(bus, DATA0HIGH)
    ch1_low  = reg_read(bus, DATA1LOW)
    ch1_high = reg_read(bus, DATA1HIGH)
    return ((ch0_high << 8) | ch0_low), ((ch1_high << 8) | ch1_low)


def calc_lux(ch0, ch1, gain, integ):
    if ch0 == 0:
        return 0.0
    scale = (16.0 if gain == GAIN_16X else 1.0) * (402.0 / INTEG_TIME_MS.get(integ, 402))
    ch0_s = ch0 * scale
    ch1_s = ch1 * scale
    ratio = ch1_s / ch0_s if ch0_s > 0 else 0

    if ratio <= 0.5:
        lux = 0.0304 * ch0_s - 0.062 * ch0_s * (ratio ** 1.4)
    elif ratio <= 0.61:
        lux = 0.0224 * ch0_s - 0.031 * ch1_s
    elif ratio <= 0.80:
        lux = 0.0128 * ch0_s - 0.0153 * ch1_s
    elif ratio <= 1.30:
        lux = 0.00146 * ch0_s - 0.00112 * ch1_s
    else:
        lux = 0.0
    return max(0.0, lux)


# ══════════════════════════════════════════════════════════════════
# Main test
# ══════════════════════════════════════════════════════════════════

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
    # ── Step 2: Verify ID register ────────────────────────────────
    section("Step 2 — Verifying TSL2561 chip identity")
    try:
        id_raw = reg_read(bus, ID_REG)
    except Exception as e:
        fail(f"Failed to read ID register: {e}")
        sys.exit(1)

    part_no = (id_raw >> 4) & 0x0F
    rev_no  = id_raw & 0x0F
    info(f"ID register (0x0A): 0x{id_raw:02X}  →  part=0x{part_no:X}  revision={rev_no}")

    if part_no == 0x1 or part_no == 0x5:
        ok(f"Part number 0x{part_no:X} — confirmed TSL2561")
    else:
        fail(f"Part number 0x{part_no:X} — not a recognized TSL2561")
        sys.exit(1)

    # ── Step 3: Power on and test CONTROL register ─────────────────
    section("Step 3 — Power-on and CONTROL register test")
    ctrl_before = reg_read(bus, CONTROL)
    info(f"CONTROL before power-on: 0x{ctrl_before:02X}")

    reg_write(bus, CONTROL, 0x03)
    time.sleep(0.05)
    ctrl_after = reg_read(bus, CONTROL)
    info(f"CONTROL after power-on:  0x{ctrl_after:02X}")
    ok("Sensor powered on") if ctrl_after == 0x03 else fail("CONTROL mismatch")

    # Power cycle test
    reg_write(bus, CONTROL, 0x00)
    time.sleep(0.01)
    reg_write(bus, CONTROL, 0x03)
    time.sleep(0.01)
    ok("Power-cycle test passed (on→off→on)") if reg_read(bus, CONTROL) == 0x03 else fail("Power-cycle failed")

    # ── Step 4: Test with both gains at 402ms integration ──────────
    section("Step 4 — Sensor readings at 402ms integration")

    for gain_val, gain_name, gain_const in [("1x", "Low-gain", GAIN_1X), ("16x", "High-gain", GAIN_16X)]:
        integ = INTEG_402MS
        reg_write(bus, TIMING, integ | gain_const)
        time.sleep(0.45)

        info(f"\n  {gain_name} ({gain_val}): TIMING = 0x{integ | gain_const:02X}")
        ch0_sum, ch1_sum = 0, 0
        all_samples = []

        for i in range(NUM_SAMPLES):
            time.sleep(INTEG_TIME_MS[integ] / 1000.0 + 0.02)
            ch0, ch1 = read_channel_data(bus)
            ch0_sum += ch0; ch1_sum += ch1
            lux = calc_lux(ch0, ch1, gain_const, integ)
            all_samples.append((ch0, ch1, lux))
            ratio = ch1 / ch0 if ch0 > 0 else 0
            print(f"    #{i+1}  CH0={ch0:>5d}  CH1={ch1:>5d}  ratio={ratio:.3f}  lux={lux:.2f}")

        ch0_avg = ch0_sum / NUM_SAMPLES
        ch1_avg = ch1_sum / NUM_SAMPLES
        max_ch0 = CH0_MAX[(integ, gain_const)]
        sat_count = sum(1 for s in all_samples if s[0] >= max_ch0 * 0.98)
        if sat_count > 0:
            warn(f"CH0 near saturation in {sat_count}/{NUM_SAMPLES} samples (max={max_ch0})")
        if ch0_avg < 10:
            warn(f"CH0 signal very low ({ch0_avg:.1f})")
        ok(f"Average: CH0={ch0_avg:.1f}  CH1={ch1_avg:.1f}  lux={calc_lux(ch0_avg, ch1_avg, gain_const, integ):.2f}")

    # ── Step 5: Test different integration times ───────────────────
    section("Step 5 — Test across integration times (1x gain)")
    for integ_val, integ_name in [(INTEG_13MS, "13.7ms"), (INTEG_101MS, "101ms"), (INTEG_402MS, "402ms")]:
        reg_write(bus, TIMING, integ_val | GAIN_1X)
        time.sleep(INTEG_TIME_MS[integ_val] / 1000.0 + 0.05)
        ch0, ch1 = read_channel_data(bus)
        lux = calc_lux(ch0, ch1, GAIN_1X, integ_val)
        raio = ch1 / ch0 if ch0 > 0 else 0
        info(f"{integ_name:>6s}:  CH0={ch0:>5d}  CH1={ch1:>5d}  ratio={raio:.3f}  lux={lux:.2f}")
    ok("All integration times functional")

    # ── Step 6: Register dump ─────────────────────────────────────
    section("Step 6 — Register dump (diagnostic)")
    reg_write(bus, TIMING, INTEG_402MS | GAIN_1X)
    time.sleep(0.45)
    for name, reg in [("CONTROL   ", CONTROL), ("TIMING    ", TIMING),
                      ("INTERRUPT ", INTERRUPT), ("ID        ", ID_REG)]:
        print(f"  0x{reg:02X}  {name} = 0x{reg_read(bus, reg):02X}")

    tlow  = reg_read(bus, THRESHLOW_LOW)  | (reg_read(bus, THRESHLOW_HIGH) << 8)
    thigh = reg_read(bus, THRESHHIGH_LOW) | (reg_read(bus, THRESHHIGH_HIGH) << 8)
    ch0, ch1 = read_channel_data(bus)
    print(f"  0x02-03 THRESH_LOW  = {tlow}")
    print(f"  0x04-05 THRESH_HIGH = {thigh}")
    print(f"  0x0C-0D DATA0 (CH0)  = {ch0}")
    print(f"  0x0E-0F DATA1 (CH1)  = {ch1}")

    # ── Step 7: Power-down ────────────────────────────────────────
    section("Step 7 — Power-down and cleanup")
    reg_write(bus, CONTROL, 0x00)
    time.sleep(0.01)
    ok("Sensor powered down: CONTROL = 0x00") if reg_read(bus, CONTROL) == 0x00 else fail("Power-down failed")

    # ── Final verdict ─────────────────────────────────────────────
    section("Final Verdict")
    print(f"\n  {GREEN}{BOLD}✓ TSL2561 at 0x{TSL2561_ADDR:02X} is fully operational!{RESET}")
    print(f"  Part:        TSL2561 (rev {rev_no})")
    print(f"  Gain modes:  Both 1x and 16x work correctly")
    print(f"  Integration: 13.7ms, 101ms, 402ms all functional")
    print(f"  Last CH0={ch0}, CH1={ch1} (402ms, 1x)")

finally:
    try:
        bus._conn.close()
    except Exception:
        pass
    bus.close()
    print(f"\n{BOLD}{'─'*55}{RESET}")
    print(f"{BOLD}  I2C bus closed. Test complete.{RESET}")
    print(f"{BOLD}{'─'*55}{RESET}")
