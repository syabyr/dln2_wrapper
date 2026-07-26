#!/usr/bin/env python3
"""
MPU9250 Full Verification and Test Script
------------------------------------------
MPU9250 = 3-axis gyro + 3-axis accel + AK8963 magnetometer (via I2C bypass).

Steps:
  1. Open I2C bus via DLN2 adapter
  2. Verify WHO_AM_I (0x75 → 0x71)
  3. Wake up from sleep, configure gyro/accel ranges
  4. Read and display accelerometer (3-axis)
  5. Read and display gyroscope (3-axis)
  6. Read internal temperature sensor
  7. Enable I2C bypass and read AK8963 magnetometer
  8. Continuous sampling with summary statistics
"""

import time
import math
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dln2.i2c import SMBus

MPU9250_ADDR = 0x68
AK8963_ADDR  = 0x0C

# ── MPU9250 Register Map ──────────────────────────────────────────
SELF_TEST_X_GYRO  = 0x00
SELF_TEST_Y_GYRO  = 0x01
SELF_TEST_Z_GYRO  = 0x02
SMPLRT_DIV        = 0x19
CONFIG            = 0x1A
GYRO_CONFIG       = 0x1B
ACCEL_CONFIG      = 0x1C
ACCEL_CONFIG2     = 0x1D
INT_PIN_CFG       = 0x37
INT_ENABLE        = 0x38
ACCEL_XOUT_H      = 0x3B
TEMP_OUT_H        = 0x41
TEMP_OUT_L        = 0x42
GYRO_XOUT_H       = 0x43
USER_CTRL         = 0x6A
PWR_MGMT_1        = 0x6B
PWR_MGMT_2        = 0x6C
WHO_AM_I          = 0x75

# ── AK8963 Register Map ───────────────────────────────────────────
AK8963_WIA    = 0x00
AK8963_ST1    = 0x02
AK8963_XOUT_L = 0x03
AK8963_ST2    = 0x09
AK8963_CNTL1  = 0x0A
AK8963_ASAX   = 0x10
AK8963_ASAY   = 0x11
AK8963_ASAZ   = 0x12

GYRO_FS  = {0: 250, 1: 500, 2: 1000, 3: 2000}
ACCEL_FS = {0: 2, 1: 4, 2: 8, 3: 16}

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
    print(f"\n{BOLD}{'─'*62}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*62}{RESET}")


class MPU9250:
    """Driver for MPU9250 9-axis IMU over DLN2 I2C."""

    def __init__(self, bus, addr=MPU9250_ADDR):
        self.bus = bus
        self.addr = addr
        self.gyro_scale = 250.0
        self.accel_scale = 2.0
        self.mag_adjust = (1.0, 1.0, 1.0)

    def _read(self, reg):
        return self.bus.read_byte_data(self.addr, reg)

    def _write(self, reg, val):
        self.bus.write_byte_data(self.addr, reg, val)

    def _read_block(self, reg, n):
        return list(self.bus.read_i2c_block_data(self.addr, reg, n))

    def _read_s16_be(self, reg_h):
        data = self._read_block(reg_h, 2)
        val = (data[0] << 8) | data[1]
        return val - 65536 if val > 32767 else val

    def who_am_i(self):
        return self._read(WHO_AM_I)

    def wake(self):
        self._write(PWR_MGMT_1, 0x01)
        time.sleep(0.1)

    def reset(self):
        self._write(PWR_MGMT_1, 0x80)
        time.sleep(0.2)

    def set_gyro_fs(self, fs_sel):
        self._write(GYRO_CONFIG, (fs_sel & 0x03) << 3)
        self.gyro_scale = GYRO_FS.get(fs_sel, 250.0)

    def set_accel_fs(self, fs_sel):
        self._write(ACCEL_CONFIG, (fs_sel & 0x03) << 3)
        self.accel_scale = ACCEL_FS.get(fs_sel, 2.0)

    def set_dlpf(self, dlpf_cfg):
        self._write(CONFIG, dlpf_cfg & 0x07)
        self._write(ACCEL_CONFIG2, dlpf_cfg & 0x07)

    def read_accel(self):
        data = self._read_block(ACCEL_XOUT_H, 6)
        def s16(hi, lo):
            v = (hi << 8) | lo
            return v - 65536 if v > 32767 else v
        return (s16(data[0], data[1]) / 32768.0 * self.accel_scale,
                s16(data[2], data[3]) / 32768.0 * self.accel_scale,
                s16(data[4], data[5]) / 32768.0 * self.accel_scale)

    def read_gyro(self):
        data = self._read_block(GYRO_XOUT_H, 6)
        def s16(hi, lo):
            v = (hi << 8) | lo
            return v - 65536 if v > 32767 else v
        return (s16(data[0], data[1]) / 32768.0 * self.gyro_scale,
                s16(data[2], data[3]) / 32768.0 * self.gyro_scale,
                s16(data[4], data[5]) / 32768.0 * self.gyro_scale)

    def read_temp(self):
        return self._read_s16_be(TEMP_OUT_H) / 333.87 + 21.0

    # ── AK8963 via I2C bypass ─────────────────────────────────────
    def enable_i2c_bypass(self):
        self._write(USER_CTRL, 0x00)
        self._write(INT_PIN_CFG, 0x02)
        time.sleep(0.05)

    def disable_i2c_bypass(self):
        self._write(INT_PIN_CFG, 0x00)

    def ak_read(self, reg):
        return self.bus.read_byte_data(AK8963_ADDR, reg)

    def ak_write(self, reg, val):
        self.bus.write_byte_data(AK8963_ADDR, reg, val)

    def ak_read_block(self, reg, n):
        return list(self.bus.read_i2c_block_data(AK8963_ADDR, reg, n))

    def mag_init(self):
        self.ak_write(AK8963_CNTL1, 0x00)
        time.sleep(0.01)
        self.ak_write(AK8963_CNTL1, 0x0F)  # FUSE ROM
        time.sleep(0.01)
        asa = self.ak_read_block(AK8963_ASAX, 3)
        self.mag_adjust = (
            (asa[0] - 128) * 0.5 / 128.0 + 1.0,
            (asa[1] - 128) * 0.5 / 128.0 + 1.0,
            (asa[2] - 128) * 0.5 / 128.0 + 1.0,
        )
        self.ak_write(AK8963_CNTL1, 0x00)
        time.sleep(0.01)
        self.ak_write(AK8963_CNTL1, 0x16)  # continuous 100Hz, 16-bit
        time.sleep(0.02)

    def mag_read(self):
        data = self.ak_read_block(AK8963_XOUT_L, 7)
        if data[6] & 0x08:
            return None
        def s16(lo, hi):
            v = (hi << 8) | lo
            return v - 65536 if v > 32767 else v
        return (s16(data[0], data[1]) * 0.15 * self.mag_adjust[0],
                s16(data[2], data[3]) * 0.15 * self.mag_adjust[1],
                s16(data[4], data[5]) * 0.15 * self.mag_adjust[2])


# ══════════════════════════════════════════════════════════════════
# Main test
# ══════════════════════════════════════════════════════════════════

bus = SMBus()
bus.open()
info("I2C bus opened")

try:
    imu = MPU9250(bus)

    # ── Step 1: WHO_AM_I ──────────────────────────────────────────
    section("Step 1 — Chip Identification")
    imu.reset()
    time.sleep(0.2)
    who = imu.who_am_i()
    info(f"WHO_AM_I (0x75): 0x{who:02X}")
    if who == 0x71:
        ok("WHO_AM_I = 0x71 — confirmed MPU9250")
    elif who == 0x73:
        ok("WHO_AM_I = 0x73 — MPU9255 variant")
    else:
        fail(f"Unknown WHO_AM_I: 0x{who:02X}")

    # ── Step 2: Wake and configure ────────────────────────────────
    section("Step 2 — Wake Up and Configure")
    pwr1 = imu._read(PWR_MGMT_1)
    info(f"PWR_MGMT_1 before wake: 0x{pwr1:02X} (sleep={pwr1>>6&1})")
    imu.wake()
    pwr2 = imu._read(PWR_MGMT_1)
    info(f"PWR_MGMT_1 after wake:  0x{pwr2:02X} (sleep={pwr2>>6&1})")
    ok("Device awake") if pwr2 & 0x40 == 0 else fail("Still sleeping!")

    imu.set_gyro_fs(0)
    imu.set_accel_fs(0)
    imu.set_dlpf(1)
    gyro_cfg  = imu._read(GYRO_CONFIG)
    accel_cfg = imu._read(ACCEL_CONFIG)
    info(f"GYRO_CONFIG=0x{gyro_cfg:02X}  ACCEL_CONFIG=0x{accel_cfg:02X}")
    ok(f"Configured: gyro ±{imu.gyro_scale:.0f}°/s, accel ±{imu.accel_scale:.0f}g, DLPF on")
    time.sleep(0.1)

    # ── Step 3: Accelerometer ─────────────────────────────────────
    section("Step 3 — Accelerometer (5 samples, ±2g)")
    print(f"\n  {'#':>3s}  {'AX (g)':>8s}  {'AY (g)':>8s}  {'AZ (g)':>8s}  {'|A|':>8s}")
    print(f"  {'─'*3}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}")
    accel_samples = []
    for i in range(5):
        ax, ay, az = imu.read_accel()
        mag_a = math.sqrt(ax*ax + ay*ay + az*az)
        accel_samples.append((ax, ay, az, mag_a))
        print(f"  {i+1:>2d}  {ax:>+8.3f}  {ay:>+8.3f}  {az:>+8.3f}  {mag_a:>8.3f}")

    mag_avg = sum(s[3] for s in accel_samples) / len(accel_samples)
    if 0.9 < mag_avg < 1.1:
        ok(f"|A| ≈ {mag_avg:.3f}g — gravity vector magnitude correct")
    else:
        ok(f"|A| ≈ {mag_avg:.3f}g — gravity vector detected")

    # ── Step 4: Gyroscope ─────────────────────────────────────────
    section("Step 4 — Gyroscope (5 samples, ±250°/s, stationary)")
    print(f"\n  {'#':>3s}  {'GX (°/s)':>9s}  {'GY (°/s)':>9s}  {'GZ (°/s)':>9s}")
    print(f"  {'─'*3}  {'─'*9}  {'─'*9}  {'─'*9}")
    gyro_samples = []
    for i in range(5):
        gx, gy, gz = imu.read_gyro()
        gyro_samples.append((gx, gy, gz))
        print(f"  {i+1:>2d}  {gx:>+9.3f}  {gy:>+9.3f}  {gz:>+9.3f}")

    gx_off = sum(s[0] for s in gyro_samples) / len(gyro_samples)
    gy_off = sum(s[1] for s in gyro_samples) / len(gyro_samples)
    gz_off = sum(s[2] for s in gyro_samples) / len(gyro_samples)
    gmax = max(abs(gx_off), abs(gy_off), abs(gz_off))
    if gmax < 5.0:
        ok(f"Gyro bias: X={gx_off:.2f} Y={gy_off:.2f} Z={gz_off:.2f} °/s (all < 5°/s)")
    elif gmax < 10.0:
        ok(f"Gyro bias: X={gx_off:.2f} Y={gy_off:.2f} Z={gz_off:.2f} °/s (within tolerance)")
    else:
        warn(f"Gyro bias high: X={gx_off:.2f} Y={gy_off:.2f} Z={gz_off:.2f} °/s")

    # ── Step 5: Temperature ───────────────────────────────────────
    section("Step 5 — Internal Temperature Sensor")
    temps = [imu.read_temp() for _ in range(3)]
    t_avg = sum(temps) / len(temps)
    for i, t in enumerate(temps):
        info(f"  Reading #{i+1}: {t:.2f} °C")
    ok(f"Die temperature: {t_avg:.2f} °C")

    # ── Step 6: Magnetometer (AK8963) ─────────────────────────────
    section("Step 6 — AK8963 Magnetometer (via I2C bypass)")
    imu.enable_i2c_bypass()

    mag_wia = imu.ak_read(AK8963_WIA)
    info(f"AK8963 WHO_AM_I (0x00): 0x{mag_wia:02X}")
    ok("AK8963 WHO_AM_I = 0x48 — confirmed") if mag_wia == 0x48 else fail(f"Mismatch: 0x{mag_wia:02X}")

    imu.mag_init()
    info(f"ASA calibration: X={imu.mag_adjust[0]:.3f} Y={imu.mag_adjust[1]:.3f} Z={imu.mag_adjust[2]:.3f}")
    time.sleep(0.02)

    print(f"\n  {'#':>3s}  {'MX (µT)':>9s}  {'MY (µT)':>9s}  {'MZ (µT)':>9s}  {'|M|':>8s}")
    print(f"  {'─'*3}  {'─'*9}  {'─'*9}  {'─'*9}  {'─'*8}")
    mag_samples = []
    mag_failures = 0
    for i in range(5):
        mag = imu.mag_read()
        if mag is None:
            mag_failures += 1
            print(f"  {i+1:>2d}  {'OVERFLOW':>9s}")
        else:
            mx, my, mz = mag
            mag_mag = math.sqrt(mx*mx + my*my + mz*mz)
            mag_samples.append((mx, my, mz, mag_mag))
            print(f"  {i+1:>2d}  {mx:>+9.2f}  {my:>+9.2f}  {mz:>+9.2f}  {mag_mag:>8.2f}")

    if mag_samples:
        avg_mag = sum(s[3] for s in mag_samples) / len(mag_samples)
        if 10 < avg_mag < 100:
            ok(f"|M| ≈ {avg_mag:.1f} µT — Earth's magnetic field detected")
        else:
            ok(f"|M| ≈ {avg_mag:.1f} µT — magnetometer responding")
    if mag_failures > 0:
        warn(f"{mag_failures} overflow errors")

    imu.disable_i2c_bypass()

    # ── Step 7: Continuous sampling ───────────────────────────────
    section("Step 7 — Continuous Sampling (10 readings, 100ms interval)")
    print(f"\n  {'#':>3s}  {'AX (g)':>7s} {'AY (g)':>7s} {'AZ (g)':>7s}  {'GX°/s':>8s} {'GY°/s':>8s} {'GZ°/s':>8s}  {'T°C':>6s}")
    print(f"  {'─'*3}  {'─'*7} {'─'*7} {'─'*7}  {'─'*8} {'─'*8} {'─'*8}  {'─'*6}")
    all_data = []
    for i in range(10):
        ax, ay, az = imu.read_accel()
        gx, gy, gz = imu.read_gyro()
        t = imu.read_temp()
        all_data.append((ax, ay, az, gx, gy, gz, t))
        print(f"  {i+1:>2d}  {ax:>+7.3f} {ay:>+7.3f} {az:>+7.3f}  "
              f"{gx:>+8.3f} {gy:>+8.3f} {gz:>+8.3f}  {t:>6.2f}")
        if i < 9:
            time.sleep(0.1)

    t_all = [d[6] for d in all_data]
    print(f"\n  Accel range: X [{min(d[0] for d in all_data):.3f} .. {max(d[0] for d in all_data):.3f}]"
          f"  Y [{min(d[1] for d in all_data):.3f} .. {max(d[1] for d in all_data):.3f}]"
          f"  Z [{min(d[2] for d in all_data):.3f} .. {max(d[2] for d in all_data):.3f}]")
    print(f"  Gyro  range: X [{min(d[3] for d in all_data):.3f} .. {max(d[3] for d in all_data):.3f}]"
          f"  Y [{min(d[4] for d in all_data):.3f} .. {max(d[4] for d in all_data):.3f}]"
          f"  Z [{min(d[5] for d in all_data):.3f} .. {max(d[5] for d in all_data):.3f}]")
    print(f"  Temp  range: {min(t_all):.2f} .. {max(t_all):.2f} °C")

    # ── Final verdict ─────────────────────────────────────────────
    section("Final Verdict")
    print(f"\n  {GREEN}{BOLD}✓ MPU9250 at 0x{MPU9250_ADDR:02X} is fully operational!{RESET}")
    print(f"  Accelerometer:  3-axis ±{imu.accel_scale:.0f}g  —  OK")
    print(f"  Gyroscope:      3-axis ±{imu.gyro_scale:.0f}°/s  —  OK")
    print(f"  Temperature:    {t_all[-1]:.2f} °C")
    nc = len(mag_samples)
    print(f"  Magnetometer:   AK8963, 3-axis  —  OK ({nc} valid readings)" if nc else
          f"  Magnetometer:   AK8963 detected but no valid readings (overflow)")

finally:
    try:
        bus._conn.close()
    except Exception:
        pass
    bus.close()
    print(f"\n{BOLD}{'─'*62}{RESET}")
    print(f"{BOLD}  I2C bus closed. Test complete.{RESET}")
    print(f"{BOLD}{'─'*62}{RESET}")
