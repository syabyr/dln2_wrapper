#!/usr/bin/env python3
"""DLN2 GPIO wrapper."""

from ._core import GPIO_EVENT_NONE, GPIO_EVENT_CHANGE, \
    GPIO_EVENT_LEVEL_HIGH, GPIO_EVENT_LEVEL_LOW


class GPIO:
    DIRECTION_IN = "in"
    DIRECTION_OUT = "out"

    def __init__(self, connection=None):
        if connection is None:
            from ._core import Dln2Connection
            connection = Dln2Connection()
        self._conn = connection

    def get_pin_count(self):
        return self._conn.gpio_get_pin_count()

    def enable_pin(self, pin):
        self._conn.gpio_pin_enable(pin)

    def disable_pin(self, pin):
        self._conn.gpio_pin_disable(pin)

    def set_direction(self, pin, direction):
        if direction not in (self.DIRECTION_IN, self.DIRECTION_OUT):
            raise ValueError("direction must be 'in' or 'out'")
        self._conn.gpio_pin_set_direction(pin, direction == self.DIRECTION_OUT)

    def get_direction(self, pin):
        is_out = self._conn.gpio_pin_get_direction(pin)
        return self.DIRECTION_OUT if is_out else self.DIRECTION_IN

    def read(self, pin):
        return self._conn.gpio_get(pin)

    def write(self, pin, value):
        self._conn.gpio_set(pin, value)

    def toggle(self, pin):
        v = self.read_output(pin)
        new = 0 if v else 1
        self.write(pin, new)
        return new

    def read_output(self, pin):
        return self._conn.gpio_get_out_val(pin)

    def set_event(self, pin, event_type=GPIO_EVENT_CHANGE, period=0):
        self._conn.gpio_set_event_cfg(pin, event_type, period)

    def clear_event(self, pin):
        self._conn.gpio_set_event_cfg(pin, GPIO_EVENT_NONE, 0)

    def poll_event(self, timeout_ms=0):
        return self._conn.gpio_poll_event(timeout_ms)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass
