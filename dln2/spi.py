#!/usr/bin/env python3
"""DLN2 SpiDev-compatible SPI wrapper."""

import struct
import time


class SpiDev:
    """spidev-compatible API backed by a shared Dln2Connection."""

    def __init__(self, connection=None):
        if connection is None:
            from ._core import Dln2Connection
            connection = Dln2Connection()
            self._owns_conn = True
        else:
            self._owns_conn = False
        self._conn = connection
        self.debug = False
        self._max_speed_hz = 1_000_000
        self._mode = 0
        self._bits_per_word = 8
        self.cshigh = False
        self.lsbfirst = False
        self.host_hold_cs = False

    @property
    def max_speed_hz(self):
        return self._max_speed_hz

    @max_speed_hz.setter
    def max_speed_hz(self, v):
        self._max_speed_hz = int(v)

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, v):
        self._mode = int(v) & 3

    @property
    def bits_per_word(self):
        return self._bits_per_word

    @bits_per_word.setter
    def bits_per_word(self, v):
        v = int(v)
        # RP2040 PIO SPI only reliably supports 8 and 16 bit frames.
        # Other values (4-7, 9-15) can trigger firmware DMA/PIO bugs.
        if v not in (8, 16):
            raise ValueError(
                f"bits_per_word must be 8 or 16, got {v}. "
                f"The Pico firmware does not support other frame sizes."
            )
        self._bits_per_word = v

    def open(self, bus=0, device=0):
        """Enable the SPI module. For spidev compatibility."""
        self._conn.spi_enable()
        self._configure()
        return self

    def close(self):
        """Disable the SPI module so the firmware releases its PIO/DMA state."""
        try:
            self._conn.spi_disable()
        except Exception:
            pass

    def _configure(self):
        """Sync current settings to the hardware."""
        self._conn.spi_configure(self._mode, self._max_speed_hz,
                                  self._bits_per_word)

    def xfer2(self, data):
        """Full-duplex transfer. Returns MISO data."""
        bpw = self._bits_per_word
        if bpw <= 8:
            tx = bytes(b & 0xFF for b in data)
        else:
            out = bytearray()
            for w in data:
                out += struct.pack("<H", int(w) & 0xFFFF)
            tx = bytes(out)
        return list(self._conn.spi_read_write(
            tx, leave_ss_low=self.host_hold_cs))

    def xfer(self, data):
        return self.xfer2(data)

    def writebytes(self, data):
        self.xfer2(data)

    def readbytes(self, length):
        return self.xfer2([0] * length)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        try:
            self._conn.close()
        except Exception:
            pass
