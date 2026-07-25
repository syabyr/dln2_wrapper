#!/usr/bin/env python3
"""DLN2 SMBus-compatible I2C wrapper."""


def _to_bytes(data):
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    return bytes(int(v) & 0xFF for v in data)


class i2c_msg:
    I2C_M_RD = 0x0001

    def __init__(self, addr, flags, data=b"", length=0):
        self.addr = int(addr) & 0x7F
        self.flags = int(flags)
        self._data = bytes(data)
        self._length = int(length)

    @classmethod
    def write(cls, addr, data):
        payload = _to_bytes(data)
        return cls(addr, 0, data=payload, length=len(payload))

    @classmethod
    def read(cls, addr, length):
        return cls(addr, cls.I2C_M_RD, length=length)

    @property
    def is_read(self):
        return bool(self.flags & self.I2C_M_RD)

    @property
    def len(self):
        return self._length if self.is_read else len(self._data)

    @property
    def buf(self):
        return self._data

    def set_data(self, data):
        self._data = bytes(data)


class SMBus:
    """SMBus-compatible I2C API backed by Dln2Connection."""

    def __init__(self, connection=None):
        if connection is None:
            from ._core import Dln2Connection
            connection = Dln2Connection()
        self._conn = connection
        self._opened = False

    def open(self, bus=0):
        if self._opened:
            return
        self._conn.i2c_enable()
        self._opened = True

    def close(self):
        if not self._opened:
            return
        try:
            self._conn.i2c_disable()
        except Exception:
            pass
        self._opened = False

    def _require(self):
        if not self._opened:
            self.open()
        return self._conn

    def enable(self, bus=0):
        self.open(bus)

    # ── SMBus API ──────────────────────────────────────

    def write_byte(self, addr, value):
        self._require().i2c_write(addr, [value])

    def write_byte_data(self, addr, cmd, value):
        self._require().i2c_write(addr, [cmd, value])

    def write_word_data(self, addr, cmd, value):
        data = [(cmd & 0xFF), (value & 0xFF), ((value >> 8) & 0xFF)]
        self._require().i2c_write(addr, data)

    def write_block_data(self, addr, cmd, data):
        payload = [cmd] + list(_to_bytes(data))
        self._require().i2c_write(addr, payload)

    def write_i2c_block_data(self, addr, cmd, data):
        self.write_block_data(addr, cmd, data)

    def read_byte(self, addr):
        return self._require().i2c_read(addr, 1)[0]

    def read_byte_data(self, addr, cmd):
        return self._require().i2c_read(addr, 1, mem_addr_len=1,
                                        mem_addr=cmd)[0]

    def read_word_data(self, addr, cmd):
        rx = self._require().i2c_read(addr, 2, mem_addr_len=1, mem_addr=cmd)
        return rx[0] | (rx[1] << 8)

    def read_block_data(self, addr, cmd):
        # Read count byte first, then data
        count = self._require().i2c_read(addr, 1, mem_addr_len=1,
                                         mem_addr=cmd)[0]
        if count == 0:
            return []
        return list(self._require().i2c_read(addr, count))

    def read_i2c_block_data(self, addr, cmd, length=32):
        return list(self._require().i2c_read(addr, length,
                                             mem_addr_len=1, mem_addr=cmd))

    # ── Raw access ─────────────────────────────────────

    def write(self, addr, data):
        self._require().i2c_write(addr, data)

    def read(self, addr, length):
        return self._require().i2c_read(addr, length)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *a):
        self.close()
