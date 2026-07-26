#!/usr/bin/env python3
"""DLN2 ADC wrapper."""


class ADC:
    MAX_CHANNELS = 3
    DEFAULT_VREF = 3.3
    DEFAULT_BITS = 10
    DEFAULT_MAX_VALUE = (1 << DEFAULT_BITS) - 1

    def __init__(self, connection=None, port=0, resolution_bits=10,
                 vref=3.3):
        if connection is None:
            from ._core import Dln2Connection
            connection = Dln2Connection()
            self._owns_conn = True
        else:
            self._owns_conn = False
        self._conn = connection
        self.port = int(port)
        self.resolution_bits = int(resolution_bits)
        self.vref = float(vref)
        self._enabled = False

    def open(self):
        if self._enabled:
            return self
        self._conn.adc_enable(self.port)
        self._conn.adc_set_resolution(self.resolution_bits, self.port)
        self._enabled = True
        return self

    def close(self):
        if not self._enabled:
            return
        try:
            self._conn.adc_disable(self.port)
        except Exception:
            pass
        self._enabled = False

    def _require(self):
        if not self._enabled:
            self.open()
        return self._conn

    def get_channel_count(self):
        return self._require().adc_get_channel_count(self.port)

    def enable_channel(self, channel):
        self._validate(channel)
        try:
            self._require().adc_channel_enable(channel, self.port)
        except RuntimeError as e:
            # Error 165: channel already usable (firmware may not support
            # per-channel enable, but the ADC master is already enabled).
            if "165" not in str(e):
                raise

    def disable_channel(self, channel):
        self._validate(channel)
        self._require().adc_channel_disable(channel, self.port)

    def set_resolution(self, bits):
        self.resolution_bits = int(bits)
        self._require().adc_set_resolution(self.resolution_bits, self.port)

    def read_channel(self, channel, enable=False):
        self._validate(channel)
        c = self._require()
        if enable:
            try:
                c.adc_channel_enable(channel, self.port)
            except RuntimeError as e:
                if "165" not in str(e):
                    raise
        return c.adc_read_channel(channel, self.port)

    def read_all(self):
        data = self._require().adc_read_all(self.port)
        return {
            "channel_mask": data["channel_mask"],
            "values": data["values"][:self.MAX_CHANNELS],
        }

    def read_volts(self, channel, enable=False):
        raw = self.read_channel(channel, enable=enable)
        return float(raw) * self.vref / self.DEFAULT_MAX_VALUE

    def to_voltage(self, raw):
        return float(raw) * self.vref / self.DEFAULT_MAX_VALUE

    def _validate(self, channel):
        channel = int(channel)
        if channel < 0 or channel >= self.MAX_CHANNELS:
            raise ValueError(f"ADC channel must be in range 0..{self.MAX_CHANNELS - 1}")

    def __enter__(self):
        return self.open()

    def __exit__(self, *a):
        self.close()
        try:
            self._conn.close()
        except Exception:
            pass
