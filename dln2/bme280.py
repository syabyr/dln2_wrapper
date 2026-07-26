#!/usr/bin/env python3
"""
Minimal BME280 helper built on top of the DLN2 SMBus wrapper.
"""

import struct

from .i2c import SMBus


class BME280:
    CHIP_ID_REGISTER = 0xD0
    RESET_REGISTER = 0xE0
    STATUS_REGISTER = 0xF3
    CTRL_HUM_REGISTER = 0xF2
    CTRL_MEAS_REGISTER = 0xF4
    CONFIG_REGISTER = 0xF5
    DATA_REGISTER = 0xF7

    EXPECTED_CHIP_ID = 0x60

    def __init__(self, bus=1, address=0x76, debug=False):
        if isinstance(bus, SMBus):
            self.bus = bus
            self._owns_bus = False
        elif hasattr(bus, 'send_cmd'):   # Dln2Connection passed directly
            self.bus = SMBus(connection=bus)
            self._owns_bus = True
        else:
            self.bus = SMBus()
            self._owns_bus = True

        self.address = int(address) & 0x7F
        self.debug = bool(debug)
        self.calibration = None
        self.t_fine = 0.0

    def close(self):
        if self._owns_bus:
            self.bus.close()
            try:
                self.bus._conn.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def read_chip_id(self):
        return self.bus.read_byte_data(self.address, self.CHIP_ID_REGISTER)

    def check_chip_id(self):
        chip_id = self.read_chip_id()
        if chip_id != self.EXPECTED_CHIP_ID:
            raise RuntimeError(
                f"Unexpected BME280 chip ID: 0x{chip_id:02x} at 0x{self.address:02x}"
            )
        return chip_id

    def reset(self):
        self.bus.write_byte_data(self.address, self.RESET_REGISTER, 0xB6)

    def configure(self, osrs_t=1, osrs_p=1, osrs_h=1, mode=3, standby=5, filter_coef=0):
        self.bus.write_byte_data(self.address, self.CTRL_HUM_REGISTER, osrs_h & 0x07)
        ctrl_meas = ((osrs_t & 0x07) << 5) | ((osrs_p & 0x07) << 2) | (mode & 0x03)
        config = ((standby & 0x07) << 5) | ((filter_coef & 0x07) << 2)
        self.bus.write_byte_data(self.address, self.CONFIG_REGISTER, config)
        self.bus.write_byte_data(self.address, self.CTRL_MEAS_REGISTER, ctrl_meas)

    def read_calibration(self):
        block1 = self.bus.read_i2c_block_data(self.address, 0x88, 26)
        block2 = self.bus.read_i2c_block_data(self.address, 0xE1, 7)

        calib1 = bytes(block1)
        calib2 = bytes(block2)

        self.calibration = {
            "dig_T1": struct.unpack_from("<H", calib1, 0)[0],
            "dig_T2": struct.unpack_from("<h", calib1, 2)[0],
            "dig_T3": struct.unpack_from("<h", calib1, 4)[0],
            "dig_P1": struct.unpack_from("<H", calib1, 6)[0],
            "dig_P2": struct.unpack_from("<h", calib1, 8)[0],
            "dig_P3": struct.unpack_from("<h", calib1, 10)[0],
            "dig_P4": struct.unpack_from("<h", calib1, 12)[0],
            "dig_P5": struct.unpack_from("<h", calib1, 14)[0],
            "dig_P6": struct.unpack_from("<h", calib1, 16)[0],
            "dig_P7": struct.unpack_from("<h", calib1, 18)[0],
            "dig_P8": struct.unpack_from("<h", calib1, 20)[0],
            "dig_P9": struct.unpack_from("<h", calib1, 22)[0],
            "dig_H1": calib1[25],
            "dig_H2": struct.unpack_from("<h", calib2, 0)[0],
            "dig_H3": calib2[2],
            "dig_H4": (calib2[3] << 4) | (calib2[4] & 0x0F),
            "dig_H5": (calib2[5] << 4) | (calib2[4] >> 4),
            "dig_H6": struct.unpack_from("<b", calib2, 6)[0],
        }
        if self.calibration["dig_H4"] & 0x800:
            self.calibration["dig_H4"] -= 4096
        if self.calibration["dig_H5"] & 0x800:
            self.calibration["dig_H5"] -= 4096
        return self.calibration

    def _ensure_calibration(self):
        if self.calibration is None:
            self.read_calibration()
        return self.calibration

    def read_raw_data(self):
        data = self.bus.read_i2c_block_data(self.address, self.DATA_REGISTER, 8)
        raw_press = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_temp = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        raw_hum = (data[6] << 8) | data[7]
        return {
            "pressure": raw_press,
            "temperature": raw_temp,
            "humidity": raw_hum,
        }

    def compensate_temperature(self, adc_t):
        cal = self._ensure_calibration()
        var1 = (adc_t / 16384.0 - cal["dig_T1"] / 1024.0) * cal["dig_T2"]
        var2 = (
            (adc_t / 131072.0 - cal["dig_T1"] / 8192.0)
            * (adc_t / 131072.0 - cal["dig_T1"] / 8192.0)
            * cal["dig_T3"]
        )
        self.t_fine = var1 + var2
        return self.t_fine / 5120.0

    def compensate_pressure(self, adc_p):
        cal = self._ensure_calibration()
        var1 = self.t_fine / 2.0 - 64000.0
        var2 = var1 * var1 * cal["dig_P6"] / 32768.0
        var2 = var2 + var1 * cal["dig_P5"] * 2.0
        var2 = var2 / 4.0 + cal["dig_P4"] * 65536.0
        var1 = (
            cal["dig_P3"] * var1 * var1 / 524288.0 + cal["dig_P2"] * var1
        ) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * cal["dig_P1"]
        if var1 == 0:
            return 0.0

        pressure = 1048576.0 - adc_p
        pressure = (pressure - var2 / 4096.0) * 6250.0 / var1
        var1 = cal["dig_P9"] * pressure * pressure / 2147483648.0
        var2 = pressure * cal["dig_P8"] / 32768.0
        pressure = pressure + (var1 + var2 + cal["dig_P7"]) / 16.0
        return pressure / 100.0

    def compensate_humidity(self, adc_h):
        cal = self._ensure_calibration()
        humidity = self.t_fine - 76800.0
        humidity = (
            adc_h
            - (cal["dig_H4"] * 64.0 + cal["dig_H5"] / 16384.0 * humidity)
        ) * (
            cal["dig_H2"]
            / 65536.0
            * (
                1.0
                + cal["dig_H6"] / 67108864.0 * humidity
                * (1.0 + cal["dig_H3"] / 67108864.0 * humidity)
            )
        )
        humidity = humidity * (1.0 - cal["dig_H1"] * humidity / 524288.0)
        if humidity < 0.0:
            return 0.0
        if humidity > 100.0:
            return 100.0
        return humidity

    def read_measurements(self):
        raw = self.read_raw_data()
        temperature_c = self.compensate_temperature(raw["temperature"])
        pressure_hpa = self.compensate_pressure(raw["pressure"])
        humidity_percent = self.compensate_humidity(raw["humidity"])
        return {
            "temperature_c": temperature_c,
            "pressure_hpa": pressure_hpa,
            "humidity_percent": humidity_percent,
            "raw": raw,
        }
