#!/usr/bin/env python3
"""
Unified DLN2 wrapper package.

Single USB connection shared by SPI, GPIO, I2C and ADC modules.
Eliminates echo-counter conflicts and USB contention from the
original four independent packages.

Usage:
    from dln2 import Dln2Connection, SpiDev, GPIO, SMBus, ADC, list_devices

    conn = Dln2Connection()          # single USB connection
    spi  = SpiDev(conn)              # all modules share conn
    gpio = GPIO(conn)
    i2c  = SMBus(conn)

See also: dln2_wrapper.py (standalone legacy version)
"""

from ._core import Dln2Connection, list_devices, Dln2DeviceInfo
from .spi import SpiDev
from .gpio import GPIO, \
    GPIO_EVENT_NONE, GPIO_EVENT_CHANGE, \
    GPIO_EVENT_LEVEL_HIGH, GPIO_EVENT_LEVEL_LOW
from .i2c import SMBus, i2c_msg
from .adc import ADC
from .bme280 import BME280
