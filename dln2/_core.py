#!/usr/bin/env python3
"""DLN2 unified USB connection — single client for SPI + GPIO + I2C + ADC."""

import struct
import time
import usb.core
import usb.util

VID = 0x1D50
PID = 0x6170

# ═══════════════════════════════════════════════════════════════
# DLN2 protocol constants
# ═══════════════════════════════════════════════════════════════

DLN2_MODULE_GENERIC = 0x00
DLN2_MODULE_GPIO    = 0x01
DLN2_MODULE_SPI     = 0x02
DLN2_MODULE_I2C     = 0x03
DLN2_MODULE_ADC     = 0x06

DLN2_HANDLE_CTRL = 1
DLN2_HANDLE_GPIO = 2
DLN2_HANDLE_I2C  = 3
DLN2_HANDLE_SPI  = 4
DLN2_HANDLE_ADC  = 5
DLN2_HANDLE_EVENT = 0

def DLN2_CMD(cmd, module):
    return (cmd & 0xFF) | ((module & 0xFF) << 8)

# ── SPI ───────────────────────────────────────────────────────
DLN2_SPI_ENABLE         = DLN2_CMD(0x11, DLN2_MODULE_SPI)
DLN2_SPI_DISABLE        = DLN2_CMD(0x12, DLN2_MODULE_SPI)
DLN2_SPI_SET_MODE       = DLN2_CMD(0x14, DLN2_MODULE_SPI)
DLN2_SPI_SET_FRAME_SIZE = DLN2_CMD(0x16, DLN2_MODULE_SPI)
DLN2_SPI_SET_FREQUENCY  = DLN2_CMD(0x18, DLN2_MODULE_SPI)
DLN2_SPI_READ_WRITE     = DLN2_CMD(0x1A, DLN2_MODULE_SPI)
DLN2_SPI_READ           = DLN2_CMD(0x1B, DLN2_MODULE_SPI)
DLN2_SPI_WRITE          = DLN2_CMD(0x1C, DLN2_MODULE_SPI)
DLN2_SPI_GET_SS_COUNT   = DLN2_CMD(0x44, DLN2_MODULE_SPI)
DLN2_SPI_SS_MULTI_ENABLE  = DLN2_CMD(0x38, DLN2_MODULE_SPI)
DLN2_SPI_SS_MULTI_DISABLE = DLN2_CMD(0x39, DLN2_MODULE_SPI)

# ── GPIO ──────────────────────────────────────────────────────
DLN2_GPIO_GET_PIN_COUNT     = DLN2_CMD(0x01, DLN2_MODULE_GPIO)
DLN2_GPIO_PIN_GET_VAL       = DLN2_CMD(0x0B, DLN2_MODULE_GPIO)
DLN2_GPIO_PIN_SET_OUT_VAL   = DLN2_CMD(0x0C, DLN2_MODULE_GPIO)
DLN2_GPIO_PIN_GET_OUT_VAL   = DLN2_CMD(0x0D, DLN2_MODULE_GPIO)
DLN2_GPIO_CONDITION_MET_EV  = DLN2_CMD(0x0F, DLN2_MODULE_GPIO)
DLN2_GPIO_PIN_ENABLE        = DLN2_CMD(0x10, DLN2_MODULE_GPIO)
DLN2_GPIO_PIN_DISABLE       = DLN2_CMD(0x11, DLN2_MODULE_GPIO)
DLN2_GPIO_PIN_SET_DIRECTION = DLN2_CMD(0x13, DLN2_MODULE_GPIO)
DLN2_GPIO_PIN_GET_DIRECTION = DLN2_CMD(0x14, DLN2_MODULE_GPIO)
DLN2_GPIO_PIN_SET_EVENT_CFG = DLN2_CMD(0x1E, DLN2_MODULE_GPIO)

GPIO_EVENT_NONE        = 0
GPIO_EVENT_CHANGE      = 1
GPIO_EVENT_LEVEL_HIGH  = 2
GPIO_EVENT_LEVEL_LOW   = 3

# ── I2C ───────────────────────────────────────────────────────
DLN2_I2C_ENABLE  = DLN2_CMD(0x01, DLN2_MODULE_I2C)
DLN2_I2C_DISABLE = DLN2_CMD(0x02, DLN2_MODULE_I2C)
DLN2_I2C_WRITE   = DLN2_CMD(0x06, DLN2_MODULE_I2C)
DLN2_I2C_READ    = DLN2_CMD(0x07, DLN2_MODULE_I2C)

# ── ADC ───────────────────────────────────────────────────────
DLN2_ADC_GET_CHANNEL_COUNT = DLN2_CMD(0x01, DLN2_MODULE_ADC)
DLN2_ADC_ENABLE            = DLN2_CMD(0x02, DLN2_MODULE_ADC)
DLN2_ADC_DISABLE           = DLN2_CMD(0x03, DLN2_MODULE_ADC)
DLN2_ADC_CHANNEL_ENABLE    = DLN2_CMD(0x05, DLN2_MODULE_ADC)
DLN2_ADC_CHANNEL_DISABLE   = DLN2_CMD(0x06, DLN2_MODULE_ADC)
DLN2_ADC_SET_RESOLUTION    = DLN2_CMD(0x08, DLN2_MODULE_ADC)
DLN2_ADC_CHANNEL_GET_VAL   = DLN2_CMD(0x0A, DLN2_MODULE_ADC)
DLN2_ADC_CHANNEL_GET_ALL_VAL = DLN2_CMD(0x0B, DLN2_MODULE_ADC)


class Dln2DeviceInfo:
    """Metadata for one connected DLN2 device."""
    __slots__ = ("dev", "serial", "index")

    def __init__(self, dev, serial, index):
        self.dev = dev
        self.serial = serial
        self.index = index


def list_devices():
    """Return list of all connected DLN2 devices."""
    devices = []
    for i, dev in enumerate(usb.core.find(find_all=True,
                                          idVendor=VID, idProduct=PID)):
        try:
            serial = usb.util.get_string(dev, dev.iSerialNumber)
        except Exception:
            serial = ""
        devices.append(Dln2DeviceInfo(dev=dev, serial=serial, index=i))
    return devices


class Dln2Connection:
    """Unified DLN2 client — SPI + GPIO + I2C + ADC share one USB connection."""

    def __init__(self, index=None, serial=None, debug=False):
        self.debug = bool(debug)
        self._echo = 1
        self._event_queue = []

        devices = list_devices()
        if not devices:
            raise ValueError(f"No DLN2 device found ({VID:04X}:{PID:04X})")

        if serial is not None:
            match = next((d for d in devices if d.serial == serial), None)
            if not match:
                raise ValueError(f"No DLN2 with serial {serial}")
            self._dev = match.dev
        elif index is not None:
            if index >= len(devices):
                raise ValueError(
                    f"DLN2 index {index} out of range ({len(devices)} found)")
            self._dev = devices[index].dev
        else:
            self._dev = devices[0].dev

        self._setup()

    def _setup(self):
        # NOTE: Do NOT call self._dev.reset() here.
        # A USB bus reset only resets the USB peripheral on the RP2040 —
        # SPI PIO/DMA state machines survive it. Commands that hit a
        # half-configured PIO cause a hard fault that kills the firmware
        # and requires a physical replug. Instead, just set configuration.

        try:
            self._dev.set_configuration()
        except Exception:
            pass

        try:
            cfg = self._dev.get_active_configuration()
        except Exception:
            raise RuntimeError(
                "DLN2 device is not responding — "
                "the Pico firmware may have crashed.\n"
                "Please replug the USB cable to power-cycle the board."
            )
        intf = cfg[(0, 0)]

        ep_out = ep_in = None
        for ep in intf.endpoints():
            d = usb.util.endpoint_direction(ep.bEndpointAddress)
            t = usb.util.endpoint_type(ep.bmAttributes)
            if d == usb.util.ENDPOINT_OUT and t == usb.util.ENDPOINT_TYPE_BULK:
                ep_out = ep
            if d == usb.util.ENDPOINT_IN and t == usb.util.ENDPOINT_TYPE_BULK:
                ep_in = ep
        if not ep_out or not ep_in:
            raise RuntimeError("No bulk endpoints found on DLN2")
        self._ep_out = ep_out.bEndpointAddress
        self._ep_in = ep_in.bEndpointAddress
        self._interface = intf.bInterfaceNumber

        if self._dev.is_kernel_driver_active(self._interface):
            try:
                self._dev.detach_kernel_driver(self._interface)
            except Exception:
                pass
        usb.util.claim_interface(self._dev, self._interface)

    # ─── USB raw ──────────────────────────────────────────────
    def _send_raw(self, data: bytes):
        self._dev.write(self._ep_out, data, timeout=2000)

    def _read_raw(self, size=1024, timeout_ms=2000):
        return bytes(self._dev.read(self._ep_in, size, timeout=timeout_ms))

    # ─── Unified command dispatch ──────────────────────────
    def send_cmd(self, cmd_id, payload=b"", handle=DLN2_HANDLE_SPI):
        hdr_size = 8
        size = hdr_size + len(payload)
        pkt = struct.pack("<HHHH", size, cmd_id, self._echo & 0xFFFF,
                          handle & 0xFFFF) + payload
        expected = self._echo & 0xFFFF
        self._echo = (self._echo + 1) & 0xFFFF

        if self.debug:
            print(f"[DLN2] OUT echo={expected} cmd=0x{cmd_id:04X} "
                  f"handle={handle} len={len(payload)}")

        self._send_raw(pkt)

        # Read — retry for large payloads
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            try:
                raw = self._read_raw(1024, timeout_ms=3000)
            except Exception:
                time.sleep(0.05)
                continue

            if len(raw) < 10:
                time.sleep(0.05)
                continue

            sz, rid, echo, hnd, result = struct.unpack("<HHHHH", raw[:10])
            data = raw[10:sz]

            if self.debug:
                print(f"  IN echo={echo} result={result} data={data[:16].hex()}")

            if hnd == DLN2_HANDLE_EVENT:
                # Queue event for GPIO.poll_event()
                self._queue_event(raw)
                continue  # read next response

            if echo != expected:
                raise RuntimeError(
                    f"Echo mismatch: got {echo}, expected {expected}")

            return {"result": result, "data": data, "echo": echo}

        raise RuntimeError("Timeout waiting for DLN2 response")

    def _queue_event(self, raw):
        """Decode and queue a GPIO event packet."""
        if len(raw) < 16:
            return
        try:
            # Event packet: size, id, echo, handle(0), result
            # Followed by event_type(2B) + pin(2B) + ?
            _, _, _, _, _ = struct.unpack("<HHHHH", raw[:10])
            ev_type = struct.unpack("<H", raw[10:12])[0]
            ev_data = raw[12:14]  # variable
            self._event_queue.append({
                "type": ev_type,
                "pin": ev_data[0],
                "value": ev_data[1] if len(ev_data) > 1 else 0,
            })
        except Exception:
            pass

    def close(self):
        try:
            usb.util.release_interface(self._dev, self._interface)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    # SPI raw
    # ═══════════════════════════════════════════════════════════

    def spi_configure(self, mode, freq_hz, bpw=8):
        self.send_cmd(DLN2_SPI_SET_FRAME_SIZE,
                      struct.pack("<BB", 0, bpw),
                      handle=DLN2_HANDLE_SPI)
        self.send_cmd(DLN2_SPI_SET_FREQUENCY,
                      struct.pack("<BI", 0, freq_hz),
                      handle=DLN2_HANDLE_SPI)
        self.send_cmd(DLN2_SPI_SET_MODE,
                      struct.pack("<BB", 0, mode & 3),
                      handle=DLN2_HANDLE_SPI)

    def spi_enable(self):
        self.send_cmd(DLN2_SPI_ENABLE, struct.pack("<B", 0),
                      handle=DLN2_HANDLE_SPI)

    def spi_disable(self):
        self.send_cmd(DLN2_SPI_DISABLE, struct.pack("<BB", 0, 0),
                      handle=DLN2_HANDLE_SPI)

    def spi_read_write(self, tx_bytes, leave_ss_low=False):
        attr = 1 if leave_ss_low else 0
        payload = struct.pack("<BHB", 0, len(tx_bytes) & 0xFFFF,
                              attr & 0xFF) + tx_bytes
        resp = self.send_cmd(DLN2_SPI_READ_WRITE, payload,
                             handle=DLN2_HANDLE_SPI)
        if resp["result"] != 0:
            raise RuntimeError(f"SPI transfer failed: result={resp['result']}")
        if len(resp["data"]) < 2:
            raise RuntimeError("SPI response too short")
        rx_len = struct.unpack("<H", resp["data"][:2])[0]
        return resp["data"][2:2 + rx_len]

    def spi_write(self, data, leave_ss_low=False):
        attr = 1 if leave_ss_low else 0
        for i in range(0, len(data), 128):
            chunk = data[i:i + 128]
            pkt = struct.pack("<BHB", 0, len(chunk), attr) + chunk
            self.send_cmd(DLN2_SPI_WRITE, pkt, handle=DLN2_HANDLE_SPI)

    # ═══════════════════════════════════════════════════════════
    # GPIO raw
    # ═══════════════════════════════════════════════════════════

    def gpio_get_pin_count(self):
        resp = self.send_cmd(DLN2_GPIO_GET_PIN_COUNT, b"",
                             handle=DLN2_HANDLE_GPIO)
        if resp["result"] != 0:
            raise RuntimeError(f"GPIO get_pin_count failed: {resp['result']}")
        if len(resp["data"]) < 2:
            raise RuntimeError("GPIO get_pin_count response too short")
        return struct.unpack("<H", resp["data"][:2])[0]

    def gpio_pin_enable(self, pin):
        resp = self.send_cmd(DLN2_GPIO_PIN_ENABLE,
                             struct.pack("<H", int(pin)),
                             handle=DLN2_HANDLE_GPIO)
        if resp["result"] != 0:
            raise RuntimeError(f"GPIO pin_enable({pin}) failed: {resp['result']}")

    def gpio_pin_disable(self, pin):
        resp = self.send_cmd(DLN2_GPIO_PIN_DISABLE,
                             struct.pack("<H", int(pin)),
                             handle=DLN2_HANDLE_GPIO)
        if resp["result"] != 0:
            raise RuntimeError(f"GPIO pin_disable({pin}) failed: {resp['result']}")

    def gpio_pin_set_direction(self, pin, is_output):
        resp = self.send_cmd(DLN2_GPIO_PIN_SET_DIRECTION,
                             struct.pack("<HB", int(pin), 1 if is_output else 0),
                             handle=DLN2_HANDLE_GPIO)
        if resp["result"] != 0:
            raise RuntimeError(
                f"GPIO set_direction({pin}) failed: {resp['result']}")

    def gpio_pin_get_direction(self, pin):
        resp = self.send_cmd(DLN2_GPIO_PIN_GET_DIRECTION,
                             struct.pack("<H", int(pin)),
                             handle=DLN2_HANDLE_GPIO)
        if resp["result"] != 0:
            raise RuntimeError(
                f"GPIO get_direction({pin}) failed: {resp['result']}")
        if len(resp["data"]) < 3:
            raise RuntimeError("GPIO get_direction response too short")
        _, direction = struct.unpack("<HB", resp["data"][:3])
        return bool(direction)

    def gpio_get(self, pin):
        resp = self.send_cmd(DLN2_GPIO_PIN_GET_VAL,
                             struct.pack("<H", int(pin)),
                             handle=DLN2_HANDLE_GPIO)
        if resp["result"] != 0:
            raise RuntimeError(f"GPIO get_val({pin}) failed: {resp['result']}")
        if len(resp["data"]) < 3:
            raise RuntimeError("GPIO get_val response too short")
        _, value = struct.unpack("<HB", resp["data"][:3])
        return value

    def gpio_set(self, pin, value):
        resp = self.send_cmd(DLN2_GPIO_PIN_SET_OUT_VAL,
                             struct.pack("<HB", int(pin), 1 if value else 0),
                             handle=DLN2_HANDLE_GPIO)
        if resp["result"] != 0:
            raise RuntimeError(f"GPIO set_out_val({pin}) failed: {resp['result']}")

    def gpio_get_out_val(self, pin):
        resp = self.send_cmd(DLN2_GPIO_PIN_GET_OUT_VAL,
                             struct.pack("<H", int(pin)),
                             handle=DLN2_HANDLE_GPIO)
        if resp["result"] != 0:
            raise RuntimeError(
                f"GPIO get_out_val({pin}) failed: {resp['result']}")
        if len(resp["data"]) < 3:
            raise RuntimeError("GPIO get_out_val response too short")
        _, value = struct.unpack("<HB", resp["data"][:3])
        return value

    def gpio_set_event_cfg(self, pin, event_type, period=0):
        resp = self.send_cmd(DLN2_GPIO_PIN_SET_EVENT_CFG,
                             struct.pack("<HBH", int(pin), int(event_type),
                                         int(period)),
                             handle=DLN2_HANDLE_GPIO)
        if resp["result"] != 0:
            raise RuntimeError(
                f"GPIO set_event_cfg({pin}) failed: {resp['result']}")

    def gpio_poll_event(self, timeout_ms=0):
        if self._event_queue:
            return self._event_queue.pop(0)
        try:
            raw = self._read_raw(1024, timeout_ms=timeout_ms)
            if len(raw) < 10:
                return None
            # Parse as event
            self._queue_event(raw)
            if self._event_queue:
                return self._event_queue.pop(0)
        except Exception:
            pass
        return None

    # ═══════════════════════════════════════════════════════════
    # I2C raw
    # ═══════════════════════════════════════════════════════════

    def i2c_enable(self):
        return self.send_cmd(DLN2_I2C_ENABLE, struct.pack("<B", 0),
                            handle=DLN2_HANDLE_I2C)

    def i2c_disable(self):
        return self.send_cmd(DLN2_I2C_DISABLE, struct.pack("<B", 0),
                            handle=DLN2_HANDLE_I2C)

    def i2c_write(self, addr, data, mem_addr_len=0, mem_addr=0):
        tx = bytes(data)
        payload = struct.pack("<BBBIH", 0, int(addr) & 0x7F,
                              int(mem_addr_len) & 0xFF,
                              int(mem_addr) & 0xFFFFFFFF,
                              len(tx) & 0xFFFF) + tx
        resp = self.send_cmd(DLN2_I2C_WRITE, payload,
                             handle=DLN2_HANDLE_I2C)
        if resp["result"] != 0:
            raise RuntimeError(f"I2C write(0x{addr:02X}) failed: {resp['result']}")
        return resp

    def i2c_read(self, addr, length, mem_addr_len=0, mem_addr=0):
        payload = struct.pack("<BBBIH", 0, int(addr) & 0x7F,
                              int(mem_addr_len) & 0xFF,
                              int(mem_addr) & 0xFFFFFFFF,
                              int(length) & 0xFFFF)
        resp = self.send_cmd(DLN2_I2C_READ, payload,
                             handle=DLN2_HANDLE_I2C)
        if resp["result"] != 0:
            raise RuntimeError(f"I2C read(0x{addr:02X}) failed: {resp['result']}")
        if len(resp["data"]) < 2:
            raise RuntimeError("I2C response too short")
        rx_len = struct.unpack("<H", resp["data"][:2])[0]
        rx = resp["data"][2:2 + rx_len]
        if len(rx) != rx_len:
            raise RuntimeError("Short I2C read payload")
        return rx

    # ═══════════════════════════════════════════════════════════
    # ADC raw
    # ═══════════════════════════════════════════════════════════

    def adc_get_channel_count(self, port=0):
        resp = self.send_cmd(DLN2_ADC_GET_CHANNEL_COUNT,
                             struct.pack("<B", port & 0xFF),
                             handle=DLN2_HANDLE_ADC)
        if resp["result"] != 0:
            raise RuntimeError(f"ADC get_channel_count failed: {resp['result']}")
        if len(resp["data"]) != 1:
            raise RuntimeError("ADC channel count response size mismatch")
        return resp["data"][0]

    def adc_enable(self, port=0):
        resp = self.send_cmd(DLN2_ADC_ENABLE,
                             struct.pack("<B", port & 0xFF),
                             handle=DLN2_HANDLE_ADC)
        if resp["result"] != 0:
            raise RuntimeError(f"ADC enable failed: {resp['result']}")
        if len(resp["data"]) < 2:
            raise RuntimeError("ADC enable response too short")
        return struct.unpack("<H", resp["data"][:2])[0]

    def adc_disable(self, port=0):
        resp = self.send_cmd(DLN2_ADC_DISABLE,
                             struct.pack("<B", port & 0xFF),
                             handle=DLN2_HANDLE_ADC)
        if resp["result"] != 0:
            raise RuntimeError(f"ADC disable failed: {resp['result']}")
        if len(resp["data"]) < 2:
            raise RuntimeError("ADC disable response too short")
        return struct.unpack("<H", resp["data"][:2])[0]

    def adc_channel_enable(self, channel, port=0):
        resp = self.send_cmd(DLN2_ADC_CHANNEL_ENABLE,
                             struct.pack("<BB", port & 0xFF, int(channel) & 0xFF),
                             handle=DLN2_HANDLE_ADC)
        if resp["result"] != 0:
            raise RuntimeError(
                f"ADC channel_enable({channel}) failed: {resp['result']}")

    def adc_channel_disable(self, channel, port=0):
        resp = self.send_cmd(DLN2_ADC_CHANNEL_DISABLE,
                             struct.pack("<BB", port & 0xFF, int(channel) & 0xFF),
                             handle=DLN2_HANDLE_ADC)
        if resp["result"] != 0:
            raise RuntimeError(
                f"ADC channel_disable({channel}) failed: {resp['result']}")

    def adc_set_resolution(self, bits, port=0):
        resp = self.send_cmd(DLN2_ADC_SET_RESOLUTION,
                             struct.pack("<BB", port & 0xFF, int(bits) & 0xFF),
                             handle=DLN2_HANDLE_ADC)
        if resp["result"] != 0:
            raise RuntimeError(f"ADC set_resolution failed: {resp['result']}")

    def adc_read_channel(self, channel, port=0):
        resp = self.send_cmd(DLN2_ADC_CHANNEL_GET_VAL,
                             struct.pack("<BB", port & 0xFF, int(channel) & 0xFF),
                             handle=DLN2_HANDLE_ADC)
        if resp["result"] != 0:
            raise RuntimeError(f"ADC read_channel failed: {resp['result']}")
        if len(resp["data"]) < 2:
            raise RuntimeError("ADC read_channel response too short")
        return struct.unpack("<H", resp["data"][:2])[0]

    def adc_read_all(self, port=0):
        resp = self.send_cmd(DLN2_ADC_CHANNEL_GET_ALL_VAL,
                             struct.pack("<B", port & 0xFF),
                             handle=DLN2_HANDLE_ADC)
        if resp["result"] != 0:
            raise RuntimeError(f"ADC read_all failed: {resp['result']}")
        if len(resp["data"]) < 18:
            raise RuntimeError("ADC read_all response too short")
        channel_mask = struct.unpack("<H", resp["data"][:2])[0]
        values = list(struct.unpack("<8H", resp["data"][2:18]))
        return {"channel_mask": channel_mask, "values": values}
