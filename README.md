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
gpio.enable_pin(25)
gpio.set_direction(25, "out")
gpio.write(25, 1)                 # set pin HIGH
val = gpio.read(25)               # read pin level

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

## CLI Commands

After installation, the following commands are available:

| Command | Description |
|---|---|
| `dln2-gpio-info` | Read GPIO pin state (JSON output) |
| `dln2-gpio-toggle` | Toggle a GPIO pin (default: Pico LED) |
| `dln2-gpio-watch` | Watch GPIO pin events |
| `dln2-adc-info` | Read all ADC channels (JSON output) |
| `dln2-adc-watch` | Stream one ADC channel |
| `dln2-i2c-scan` | Scan I2C bus for devices |
| `dln2-i2c-test` | Read/write I2C register |
| `dln2-bme280` | Read BME280 sensor measurements |
| `dln2-spi-test` | Send SPI JEDEC ID probe |
| `dln2-bpw-test` | Cycle SPI bits-per-word 4..16 |

```bash
# GPIO
dln2-gpio-info --pin 2
dln2-gpio-toggle --pin 25 --count 5 --interval 0.2
dln2-gpio-watch --pin 2 --timeout-ms 500

# ADC
dln2-adc-info
dln2-adc-watch --channel 0 --interval 0.5

# I2C
dln2-i2c-scan
dln2-i2c-test --address 0x76 --register 0xD0 --read 1

# BME280
dln2-bme280 --address 0x76 --pretty

# SPI
dln2-spi-test
dln2-bpw-test
```

## Examples (as scripts)

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

## Pin Constraints

| Pins | Capability |
|---|---|
| 0–22, 26–28 | Full GPIO (input/output + events) |
| 23, 24, 29 | Output-only (reserved for SMPS / VBUS / VSYS) |
| 25 | Output-only (on-board LED) |
| ADC 0–2 | Map to GPIO 26, 27, 28 respectively |

## Firmware Compatibility

| dln2 Python | Minimum firmware | Notes |
|---|---|---|
| 0.2.1 | [pico-usb-io-board](https://github.com/syabyr/pico-usb-io-board) `>= v0.2` | SPI bpw validation, ADC pin-sharing fix |
| 0.2.0 | any | Works with all firmware versions |

To flash updated firmware:
1. Hold the BOOTSEL button while connecting the Pico (or press and release RESET while holding BOOTSEL)
2. Copy `dln2.uf2` to the `RPI-RP2` USB drive that appears
3. The Pico reboots automatically with the new firmware

## Related

- [pico-usb-io-board](https://github.com/syabyr/pico-usb-io-board) — RP2040 firmware
- [st7789 display driver](https://github.com/syabyr/dln2_wrapper) — example ST7789 + BME280 application

## License

MIT
