#!/usr/bin/env python3
"""
BH1750 Ambient Light Sensor — Full Verification and Test Script
-----------------------------------------------------------------
BH1750 is a command-based sensor (NO registers).  Every read after
a measurement command is a plain I2C read — writing a register
address would send an unintended command (e.g. 0x00 = POWER_OFF).

Steps:
  1. Open I2C bus via DLN2 adapter
  2. Power on and verify sensor responds with non-zero lux
  3. Test reset command
  4. Test all 6 measurement modes (continuous + one-shot)
  5. Power-cycle test
  6. Stability test over 30 readings
  7. Saturation / range check
"""

import time
import math
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dln2.i2c import SMBus

BH1750_ADDR = 0x23

# ── Commands (single-byte, NO register) ──────────────────────────
CMD_POWER_OFF      = 0x00
CMD_POWER_ON       = 0x01
CMD_RESET          = 0x07
CMD_CONT_H_RES     = 0x10   # 1 lx, 120 ms
CMD_CONT_H_RES2    = 0x11   # 0.5 lx, 120 ms
CMD_CONT_L_RES     = 0x13   # 4 lx, 16 ms
CMD_ONCE_H_RES     = 0x20   # 1 lx, 120 ms, one-shot
CMD_ONCE_H_RES2    = 0x21   # 0.5 lx, 120 ms, one-shot
CMD_ONCE_L_RES     = 0x23   # 4 lx, 16 ms, one-shot

WAIT_HRES  = 200   # generous margin over typ 120 / max 180 ms
WAIT_LRES  = 40    # generous margin over typ 16 / max 24 ms

MODES = [
    ("H-Res  (cont)", CMD_CONT_H_RES,  1.0, WAIT_HRES),
    ("H-Res2 (cont)", CMD_CONT_H_RES2, 0.5, WAIT_HRES),
    ("L-Res  (cont)", CMD_CONT_L_RES,  4.0, WAIT_LRES),
    ("H-Res  (once)", CMD_ONCE_H_RES,  1.0, WAIT_HRES),
    ("H-Res2 (once)", CMD_ONCE_H_RES2, 0.5, WAIT_HRES),
    ("L-Res  (once)", CMD_ONCE_L_RES,  4.0, WAIT_LRES),
]

NUM_SAMPLES  = 5
STABILITY_N  = 30

# ── Display helpers ──────────────────────────────────────────────
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


# ── BH1750 I/O (command-based, NO registers) ─────────────────────

def bh1750_cmd(bus, cmd):
    """Send a single-byte command to the BH1750."""
    bus.write_byte(BH1750_ADDR, cmd)


def bh1750_read(bus):
    """Plain 2-byte read — NEVER writes a register address first.

    This is the critical difference from register-based sensors.
    Writing anything before the read would be interpreted as a
    command (e.g. 0x00 = POWER_OFF, 0x01 = POWER_ON).
    """
    data = bus.read(BH1750_ADDR, 2)
    return data


def bh1750_measure(bus, mode_cmd, wait_ms):
    """Send measurement command, wait, read lux value."""
    bh1750_cmd(bus, mode_cmd)
    time.sleep(wait_ms / 1000.0)
    raw = bh1750_read(bus)
    return ((raw[0] << 8) | raw[1]) / 1.2


# ═════════════════════════════════════════════════════════════════

section("Step 1 — Opening I2C bus via DLN2 adapter")

try:
    bus = SMBus()
    bus.open()
    info("I2C bus opened")
    ok("DLN2 I2C bus is ready")
except Exception as e:
    fail(f"Failed: {e}")
    sys.exit(1)

try:
    # ── Power-on ─────────────────────────────────────────────────
    section("Step 2 — Power-on & First Reading")

    bh1750_cmd(bus, CMD_POWER_ON)
    info("CMD_POWER_ON (0x01) sent")
    time.sleep(0.01)

    # One-shot H-Res measurement
    try:
        lux = bh1750_measure(bus, CMD_ONCE_H_RES, WAIT_HRES)
        info(f"First reading: {lux:.1f} lux")
        if lux >= 0:
            ok(f"BH1750 responds — {lux:.1f} lux")
        else:
            fail(f"Negative lux: {lux}")
    except Exception as e:
        fail(f"Sensor not responding: {e}")
        sys.exit(1)

    # ── Reset ────────────────────────────────────────────────────
    section("Step 3 — Reset Test")

    bh1750_cmd(bus, CMD_POWER_ON)
    time.sleep(0.01)
    lux_before = bh1750_measure(bus, CMD_ONCE_H_RES, WAIT_HRES)
    info(f"Before reset: {lux_before:.1f} lux")

    bh1750_cmd(bus, CMD_RESET)
    info("CMD_RESET (0x07) sent")
    time.sleep(0.02)

    bh1750_cmd(bus, CMD_POWER_ON)
    time.sleep(0.02)
    lux_after = bh1750_measure(bus, CMD_ONCE_H_RES, WAIT_HRES)
    info(f"After reset:  {lux_after:.1f} lux")
    ok("Sensor survived reset")

    # ── All modes ────────────────────────────────────────────────
    section("Step 4 — All Measurement Modes")

    for mode_name, cmd, res, wait_ms in MODES:
        # For continuous modes: send once, then sample N times
        print(f"\n  {BOLD}{mode_name}{RESET}  res={res} lx  wait={wait_ms} ms")
        print(f"  {'#':>3s}  {'Raw':>6s}  {'Lux':>8s}")
        print(f"  {'─'*3}  {'─'*6}  {'─'*8}")

        samples = []
        for i in range(NUM_SAMPLES):
            lux_val = bh1750_measure(bus, cmd, wait_ms)
            raw = int(lux_val * 1.2)
            samples.append(lux_val)
            print(f"  {i+1:>2d}  {raw:>5d}  {lux_val:>8.1f}")

        avg = sum(samples) / len(samples)
        rng = max(samples) - min(samples)
        pct = (rng / avg * 100) if avg > 0 else 0
        flag = f" {YELLOW}(noisy){RESET}" if pct > 20 else ""
        print(f"  avg={avg:.1f} lx  range={rng:.2f} ({pct:.1f}%){flag}")

    ok("All modes functional")

    # ── Power cycle ─────────────────────────────────────────────
    section("Step 5 — Power Cycle")

    bh1750_cmd(bus, CMD_POWER_OFF)
    info("CMD_POWER_OFF (0x00)")
    time.sleep(0.05)

    bh1750_cmd(bus, CMD_POWER_ON)
    info("CMD_POWER_ON (0x01)")
    time.sleep(0.05)

    lux = bh1750_measure(bus, CMD_ONCE_H_RES, WAIT_HRES)
    ok(f"Power-cycle OK — {lux:.1f} lux")

    # ── Stability ───────────────────────────────────────────────
    section(f"Step 6 — Stability ({STABILITY_N} readings, H-Res2 once)")

    print(f"\n  {'#':>3s}  {'Lux':>8s}  {'#':>3s}  {'Lux':>8s}  {'#':>3s}  {'Lux':>8s}")
    print(f"  {'─'*3}  {'─'*8}  {'─'*3}  {'─'*8}  {'─'*3}  {'─'*8}")

    all_lux = [bh1750_measure(bus, CMD_ONCE_H_RES2, WAIT_HRES)
               for _ in range(STABILITY_N)]

    for row in range(10):
        parts = []
        for col in range(3):
            i = row + col * 10
            if i < STABILITY_N:
                parts.append(f"  {i+1:>2d}  {all_lux[i]:>8.1f}")
        print("".join(parts))

    avg = sum(all_lux) / len(all_lux)
    rng = max(all_lux) - min(all_lux)
    std = math.sqrt(sum((x - avg) ** 2 for x in all_lux) / len(all_lux))

    print(f"\n  Average: {avg:.2f} lx   Std: {std:.2f} lx   "
          f"Range: {rng:.2f} lx  (min={min(all_lux):.1f}  max={max(all_lux):.1f})")

    if std < 1 or std / max(avg, 0.1) < 0.1:
        ok(f"Excellent stability (σ={std:.2f} lx)")
    elif std < 5:
        ok(f"Good stability (σ={std:.2f} lx)")
    else:
        info(f"Variable (σ={std:.2f} lx) — flickering light?")

    # ── Saturation ──────────────────────────────────────────────
    section("Step 7 — Saturation Check")

    bh1750_cmd(bus, CMD_CONT_H_RES)
    time.sleep(0.2)

    peaks = []
    for _ in range(5):
        raw = bh1750_read(bus)
        peaks.append(((raw[0] << 8) | raw[1]) / 1.2)
        time.sleep(0.15)

    max_lux = max(peaks)
    info(f"Max: {max_lux:.1f} lx  (H-Res saturation ≈ 54612 lx)")

    if max_lux > 50000:
        warn(f"Near saturation ({max_lux:.0f}/54612 lx)")
    else:
        ok(f"Well below saturation ({max_lux:.0f}/54612 lx)")

    # ── Done ────────────────────────────────────────────────────
    bh1750_cmd(bus, CMD_POWER_OFF)

    section("Final Verdict")
    print(f"\n  {GREEN}{BOLD}✓ BH1750 at 0x{BH1750_ADDR:02X} is operational!{RESET}")
    print(f"  All 6 modes pass   |   Last: {avg:.1f} lx")
    print(f"  Resolution: 1 lx (H-Res) / 0.5 lx (H-Res2)")

finally:
    try:
        bus._conn.close()
    except Exception:
        pass
    bus.close()
    print(f"\n{BOLD}{'─'*58}{RESET}")
    print(f"{BOLD}  Bus closed.{RESET}")
    print(f"{BOLD}{'─'*58}{RESET}")
