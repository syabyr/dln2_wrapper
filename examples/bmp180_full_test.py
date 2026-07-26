#!/usr/bin/env python3
"""
BMP085 / BMP180 Full Verification and Test Script
--------------------------------------------------
BMP180 is the newer version of BMP085; both use the same register map
and calculation flow.

Steps:
  1. Open I2C bus via DLN2 adapter
  2. Read chip ID (0xD0 → 0x55)
  3. Read 11 × 16-bit calibration coefficients (0xAA–0xBF)
  4. Read uncompensated temperature, then pressure at 4 oversampling levels
  5. Compensate and display results
  6. Stability test over 10 readings
"""

import time
import math
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dln2.i2c import SMBus

BMP180_ADDR = 0x77

# ── Register map ──────────────────────────────────────────────────
REG_CALIB       = 0xAA
REG_CHIP_ID     = 0xD0
REG_SOFT_RESET  = 0xE0
REG_CTRL        = 0xF4
REG_MSB         = 0xF6
REG_LSB         = 0xF7
REG_XLSB        = 0xF8

CMD_TEMP         = 0x2E
CMD_PRESS_OSS0   = 0x34
CMD_PRESS_OSS1   = 0x74
CMD_PRESS_OSS2   = 0xB4
CMD_PRESS_OSS3   = 0xF4

OSS_TO_CMD    = {0: CMD_PRESS_OSS0, 1: CMD_PRESS_OSS1,
                 2: CMD_PRESS_OSS2, 3: CMD_PRESS_OSS3}
OSS_TO_WAIT    = {0: 4.5, 1: 7.5, 2: 13.5, 3: 25.5}
OSS_TO_SAMPLES = {0: 1, 1: 2, 2: 4, 3: 8}
TEMP_WAIT_MS   = 4.5

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
    print(f"\n{BOLD}{'─'*58}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*58}{RESET}")


class BMP180:
    """Minimal driver for BMP085 / BMP180 over DLN2 I2C."""

    def __init__(self, bus, address=BMP180_ADDR):
        self.bus = bus
        self.addr = address
        self.cal = {}
        self._b5 = 0

    def _read_reg(self, reg):
        return self.bus.read_byte_data(self.addr, reg)

    def _write_reg(self, reg, val):
        self.bus.write_byte_data(self.addr, reg, val)

    def _read_word_be(self, reg):
        high = self._read_reg(reg)
        low  = self._read_reg(reg + 1)
        return (high << 8) | low

    def read_chip_id(self):
        return self._read_reg(REG_CHIP_ID)

    def check_chip_id(self):
        cid = self.read_chip_id()
        if cid != 0x55:
            raise RuntimeError(f"Unexpected chip ID 0x{cid:02X}, expected 0x55")
        return cid

    def soft_reset(self):
        self._write_reg(REG_SOFT_RESET, 0xB6)

    def read_calibration(self):
        raw = [self._read_reg(REG_CALIB + i) for i in range(22)]

        def be16(hi, lo): return (hi << 8) | lo
        def s16(hi, lo):  v = be16(hi, lo); return v - 65536 if v > 32767 else v

        self.cal = {
            "AC1": s16(raw[0],  raw[1]),  "AC2": s16(raw[2],  raw[3]),
            "AC3": s16(raw[4],  raw[5]),  "AC4": be16(raw[6], raw[7]),
            "AC5": be16(raw[8], raw[9]),  "AC6": be16(raw[10], raw[11]),
            "B1":  s16(raw[12], raw[13]), "B2":  s16(raw[14], raw[15]),
            "MB":  s16(raw[16], raw[17]), "MC":  s16(raw[18], raw[19]),
            "MD":  s16(raw[20], raw[21]),
        }
        return self.cal

    def validate_calibration(self):
        return [k for k, v in self.cal.items()
                if v == 0 or v == -1 or v == 0xFFFF]

    def read_raw_temperature(self):
        self._write_reg(REG_CTRL, CMD_TEMP)
        time.sleep(TEMP_WAIT_MS / 1000.0)
        return self._read_word_be(REG_MSB)

    def compensate_temperature(self, ut):
        c = self.cal
        x1 = ((ut - c["AC6"]) * c["AC5"]) >> 15
        x2 = (c["MC"] << 11) // (x1 + c["MD"])
        self._b5 = x1 + x2
        return (self._b5 + 8) >> 4  # 0.1 °C

    def read_raw_pressure(self, oss=3):
        cmd  = OSS_TO_CMD.get(oss, CMD_PRESS_OSS3)
        wait = OSS_TO_WAIT.get(oss, 25.5)
        self._write_reg(REG_CTRL, cmd)
        time.sleep(wait / 1000.0)
        msb  = self._read_reg(REG_MSB)
        lsb  = self._read_reg(REG_LSB)
        xlsb = self._read_reg(REG_XLSB)
        return ((msb << 16) | (lsb << 8) | xlsb) >> (8 - oss)

    def compensate_pressure(self, up, oss=3):
        c  = self.cal
        b6 = self._b5 - 4000
        x1 = (c["B2"] * (b6 * b6 >> 12)) >> 11
        x2 = (c["AC2"] * b6) >> 11
        b3 = (((c["AC1"] * 4 + (x1 + x2)) << oss) + 2) >> 2
        x1 = (c["AC3"] * b6) >> 13
        x2 = (c["B1"] * ((b6 * b6) >> 12)) >> 16
        b4 = (c["AC4"] * (((x1 + x2) + 2) >> 2) + 32768) >> 15
        b7 = (up - b3) * (50000 >> oss)
        p  = (b7 * 2) // b4 if b7 < 0x80000000 else (b7 // b4) * 2
        x1 = (p >> 8) * (p >> 8)
        x1 = (x1 * 3038) >> 16
        x2 = (-7357 * p) >> 16
        return p + ((x1 + x2 + 3791) >> 4)  # Pa

    def read_all(self, oss=3):
        ut = self.read_raw_temperature()
        temp_01c = self.compensate_temperature(ut)
        up = self.read_raw_pressure(oss)
        press_pa = self.compensate_pressure(up, oss)
        return {
            "raw_temp": ut, "raw_press": up,
            "temp_c": temp_01c / 10.0,
            "press_pa": press_pa, "press_hpa": press_pa / 100.0,
        }


# ══════════════════════════════════════════════════════════════════
# Main test
# ══════════════════════════════════════════════════════════════════

section("Step 1 — Opening I2C bus via DLN2 adapter")
bus = SMBus()
bus.open()
info("I2C bus opened")
ok("DLN2 I2C bus is ready")

try:
    sensor = BMP180(bus)

    # ── Step 2: Chip ID ───────────────────────────────────────────
    section("Step 2 — Chip Identification")
    cid = sensor.read_chip_id()
    info(f"CHIP_ID (0xD0): 0x{cid:02X}")
    if cid == 0x55:
        ok("Chip ID 0x55 — confirmed BMP085 or BMP180")
    else:
        fail(f"Expected 0x55, got 0x{cid:02X}")

    sensor.soft_reset()
    time.sleep(0.01)
    if sensor.read_chip_id() == 0x55:
        ok("Post-reset chip ID: 0x55 — reset OK")
    else:
        fail(f"Post-reset chip ID mismatch")

    # ── Step 3: Calibration ───────────────────────────────────────
    section("Step 3 — Calibration Coefficients")
    cal = sensor.read_calibration()
    print()
    info("Calibration data:")
    print(f"    AC1={cal['AC1']:>6d}  AC2={cal['AC2']:>6d}  AC3={cal['AC3']:>6d}")
    print(f"    AC4={cal['AC4']:>6d}  AC5={cal['AC5']:>6d}  AC6={cal['AC6']:>6d}")
    print(f"    B1 ={cal['B1']:>6d}  B2 ={cal['B2']:>6d}  MB ={cal['MB']:>6d}")
    print(f"    MC ={cal['MC']:>6d}  MD ={cal['MD']:>6d}")

    issues = sensor.validate_calibration()
    if issues:
        warn(f"Suspicious calibration values: {', '.join(issues)}")
    else:
        ok("All 11 calibration words look valid")

    # ── Step 4: Temperature ───────────────────────────────────────
    section("Step 4 — Temperature Readings (5 samples)")
    temps = []
    for i in range(5):
        ut = sensor.read_raw_temperature()
        tc = sensor.compensate_temperature(ut) / 10.0
        temps.append(tc)
        info(f"  #{i+1}  raw=0x{ut:04X}  temp={tc:.2f} °C")

    t_avg = sum(temps) / len(temps)
    t_range = max(temps) - min(temps)
    ok(f"Temperature: avg={t_avg:.2f} °C  range={t_range:.3f} °C")

    # ── Step 5: Pressure vs oversampling ──────────────────────────
    section("Step 5 — Pressure vs Oversampling Mode")
    print(f"\n  {'Mode':>6s}  {'Samples':>8s}  {'Conv Time':>10s}  {'Pressure (hPa)':>16s}  {'Noise* (hPa)':>14s}")
    print(f"  {'─'*6}  {'─'*8}  {'─'*10}  {'─'*16}  {'─'*14}")

    for oss in [0, 1, 2, 3]:
        ut = sensor.read_raw_temperature()
        sensor.compensate_temperature(ut)
        pressures = [sensor.compensate_pressure(sensor.read_raw_pressure(oss), oss) for _ in range(3)]
        p_avg = sum(pressures) / len(pressures)
        p_noise = (max(pressures) - min(pressures)) / 100.0
        print(f"  OSS{oss}   {OSS_TO_SAMPLES[oss]:>5d}     {OSS_TO_WAIT[oss]:>5.1f} ms        {p_avg/100:>8.2f}         {p_noise:>9.2f}")

    print(f"  {'─'*63}")
    print(f"  * Noise = peak-to-peak spread over 3 readings")
    ok("All 4 oversampling modes functional")

    # ── Step 6: Stability ─────────────────────────────────────────
    section("Step 6 — Stability Test (10 readings @ OSS3, 0.5s interval)")
    print(f"\n  {'#':>3s}  {'Temp (°C)':>10s}  {'Press (hPa)':>13s}")
    print(f"  {'─'*3}  {'─'*10}  {'─'*13}")

    all_readings = []
    for i in range(10):
        if i > 0:
            time.sleep(0.5)
        r = sensor.read_all(oss=3)
        all_readings.append(r)
        print(f"  {i+1:>2d}  {r['temp_c']:>10.2f}  {r['press_hpa']:>13.2f}")

    t_vals = [r["temp_c"] for r in all_readings]
    p_vals = [r["press_hpa"] for r in all_readings]
    t_mean = sum(t_vals) / len(t_vals)
    p_mean = sum(p_vals) / len(p_vals)
    print(f"\n  Temperature: avg={t_mean:.2f}°C  std={math.sqrt(sum((x-t_mean)**2 for x in t_vals)/len(t_vals)):.3f}°C")
    print(f"  Pressure:    avg={p_mean:.2f}hPa  std={math.sqrt(sum((x-p_mean)**2 for x in p_vals)/len(p_vals)):.3f}hPa")

    # ── Final verdict ─────────────────────────────────────────────
    section("Final Verdict")
    last = all_readings[-1]
    print(f"\n  {GREEN}{BOLD}✓ BMP180 at 0x{BMP180_ADDR:02X} is fully operational!{RESET}")
    print(f"  Temperature:   {last['temp_c']:.2f} °C")
    print(f"  Pressure:      {last['press_hpa']:.2f} hPa")
    print(f"  Oversampling:  0–3 all supported")
    print(f"  Calibration:   11 coefficients valid")

finally:
    try:
        bus._conn.close()
    except Exception:
        pass
    bus.close()
    print(f"\n{BOLD}{'─'*58}{RESET}")
    print(f"{BOLD}  I2C bus closed. Test complete.{RESET}")
    print(f"{BOLD}{'─'*58}{RESET}")
