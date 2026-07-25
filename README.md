# dln2 — Unified DLN2 USB I/O Board Wrapper

Drop-in replacement for the four independent `dln2_*_wrapper` packages.  
**All modules share a single USB connection** — no echo-counter conflicts, no USB contention.

Originally developed for the [Pico USB I/O Board](https://github.com/syabyr/pico-usb-io-board).

## Installation

```bash
pip install git+https://github.com/syabyr/dln2_wrapper
```

Requires: `pyusb`

## Quick Start

```python
from dln2 import Dln2Connection, SpiDev, GPIO, SMBus, ADC

conn = Dln2Connection()          # one USB connection

# ── SPI ─────────────────────────────────────────────────
spi = SpiDev(conn)
spi.mode = 3
spi.max_speed_hz = 16_000_000
rx = spi.xfer2([0x9F, 0x00, 0x00, 0x00])  # JEDEC ID

# ── GPIO ────────────────────────────────────────────────
gpio = GPIO(conn)
gpio.set_direction(20, "out")
gpio.write(20, 1)                 # set pin HIGH
val = gpio.read(20)               # read pin level

# ── I2C ─────────────────────────────────────────────────
i2c = SMBus(conn)
i2c.open()
devices = []
for addr in range(1, 128):
    try:
        i2c.write_byte(addr, 0)
        devices.append(addr)
    except: pass

# ── ADC ─────────────────────────────────────────────────
adc = ADC(conn, vref=3.3)
volts = adc.read_volts(0)         # read channel 0 voltage

conn.close()
```

## Multi-Device Support

```python
from dln2 import list_devices, Dln2Connection

for d in list_devices():
    print(f"[{d.index}] serial={d.serial}")

lcd_conn = Dln2Connection(index=0)     # first board — ST7789 display
nfc_conn = Dln2Connection(index=1)     # second board — NFC reader
# or by exact serial:
# conn = Dln2Connection(serial="4250304B38353817")
```

## Module API

### SpiDev
spidev-compatible API: `xfer()`, `xfer2()`, `writebytes()`, `readbytes()`,  
`mode`, `max_speed_hz`, `bits_per_word`, `cshigh`, `lsbfirst`, `host_hold_cs`

### GPIO
`set_direction(pin, "in"|"out")`, `write(pin, value)`, `read(pin)`,  
`toggle(pin)`, `get_direction(pin)`, `set_event(pin, type)`, `poll_event()`

### SMBus
smbus-compatible API: `write_byte()`, `read_byte_data()`,  
`write_word_data()`, `read_word_data()`, `read_block_data()`,  
`write_block_data()`, `write_i2c_block_data()`, `read_i2c_block_data()`

### ADC
`read_channel(channel)`, `read_all()`, `read_volts(channel)`,  
`set_resolution(bits)`, `enable_channel(ch)`, `disable_channel(ch)`

### BME280
`read_chip_id()`, `get_temperature()`, `get_humidity()`, `get_pressure()`,  
`get_altitude()`, `get_all()`

## Examples

```bash
# SPI JEDEC ID read
python3 examples/spidev_test.py

# GPIO pin toggle (default: Pico LED)
python3 examples/gpio_toggle.py --pin 25

# I2C bus scan
python3 examples/i2c_scan.py

# ADC monitor
python3 examples/adc_info.py
```

## Why Unified?

| | Old (4 packages) | New (`dln2`) |
|---|---|---|
| USB connections | 4 separate (echo conflicts) | 1 shared |
| Code duplication | ~800 lines (4× Dln2Usb) | 0 lines |
| GPIO events steal SPI responses | Yes | No (proper event queue) |
| Multi-device | Manual USB enumeration | `list_devices()` |
| Cross-module data flow | Impossible (4 echo counters) | Trivial (same counter) |

## Related

- [pico-usb-io-board](https://github.com/syabyr/pico-usb-io-board) — RP2040 firmware
- [st7789 display driver](https://github.com/syabyr/dln2_wrapper) — example ST7789 + BME280 application

## License

MIT
