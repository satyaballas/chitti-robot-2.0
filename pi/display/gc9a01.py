"""Minimal GC9A01 (240x240 round TFT) driver for Raspberry Pi using spidev + lgpio.

Wiring (Pi physical pins):
    VCC -> 3.3V (pin 1)        GND -> GND (pin 14; any GND pin)
    SCL -> GPIO11 SCLK (pin 23) SDA -> GPIO10 MOSI (pin 19)
    CS  -> GPIO8 CE0 (pin 24)   DC  -> GPIO25 (pin 22)
    RST -> GPIO27 (pin 13)      BLK -> GPIO22 (pin 15)  (optional; leave unconnected = always on)
"""
import time

import lgpio
import numpy as np
import spidev

WIDTH = HEIGHT = 240

# Standard GC9A01 power-on sequence: (command, data bytes, delay ms)
_INIT = [
    (0xEF, b"", 0), (0xEB, b"\x14", 0), (0xFE, b"", 0), (0xEF, b"", 0),
    (0xEB, b"\x14", 0), (0x84, b"\x40", 0), (0x85, b"\xFF", 0), (0x86, b"\xFF", 0),
    (0x87, b"\xFF", 0), (0x88, b"\x0A", 0), (0x89, b"\x21", 0), (0x8A, b"\x00", 0),
    (0x8B, b"\x80", 0), (0x8C, b"\x01", 0), (0x8D, b"\x01", 0), (0x8E, b"\xFF", 0),
    (0x8F, b"\xFF", 0), (0xB6, b"\x00\x20", 0),
    (0x36, None, 0),  # memory access control, filled in by __init__ (RGB/BGR)
    (0x3A, b"\x05", 0),  # 16-bit colour (RGB565)
    (0x90, b"\x08\x08\x08\x08", 0), (0xBD, b"\x06", 0), (0xBC, b"\x00", 0),
    (0xFF, b"\x60\x01\x04", 0), (0xC3, b"\x13", 0), (0xC4, b"\x13", 0),
    (0xC9, b"\x22", 0), (0xBE, b"\x11", 0), (0xE1, b"\x10\x0E", 0),
    (0xDF, b"\x21\x0C\x02", 0),
    (0xF0, b"\x45\x09\x08\x08\x26\x2A", 0), (0xF1, b"\x43\x70\x72\x36\x37\x6F", 0),
    (0xF2, b"\x45\x09\x08\x08\x26\x2A", 0), (0xF3, b"\x43\x70\x72\x36\x37\x6F", 0),
    (0xED, b"\x1B\x0B", 0), (0xAE, b"\x77", 0), (0xCD, b"\x63", 0),
    (0x70, b"\x07\x07\x04\x0E\x0F\x09\x07\x08\x03", 0), (0xE8, b"\x34", 0),
    (0x62, b"\x18\x0D\x71\xED\x70\x70\x18\x0F\x71\xEF\x70\x70", 0),
    (0x63, b"\x18\x11\x71\xF1\x70\x70\x18\x13\x71\xF3\x70\x70", 0),
    (0x64, b"\x28\x29\xF1\x01\xF1\x00\x07", 0),
    (0x66, b"\x3C\x00\xCD\x67\x45\x45\x10\x00\x00\x00", 0),
    (0x67, b"\x00\x3C\x00\x00\x00\x01\x54\x10\x32\x98", 0),
    (0x74, b"\x10\x85\x80\x00\x00\x4E\x00", 0), (0x98, b"\x3E\x07", 0),
    (0x35, b"", 0),   # tearing effect on
    (0x21, b"", 0),   # display inversion on (needed by most GC9A01 modules)
    (0x11, b"", 120),  # sleep out
    (0x29, b"", 20),   # display on
]


class GC9A01:
    def __init__(self, dc=25, rst=27, bl=22, spi_bus=0, spi_dev=0, speed_hz=40_000_000, bgr=True):
        self.dc, self.rst, self.bl = dc, rst, bl
        self.chip = lgpio.gpiochip_open(0)
        for pin in (dc, rst) + ((bl,) if bl is not None else ()):
            lgpio.gpio_claim_output(self.chip, pin, 0)
        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_dev)
        self.spi.max_speed_hz = speed_hz
        self.spi.mode = 0
        self._madctl = 0x08 if bgr else 0x00

        lgpio.gpio_write(self.chip, rst, 1); time.sleep(0.01)
        lgpio.gpio_write(self.chip, rst, 0); time.sleep(0.01)
        lgpio.gpio_write(self.chip, rst, 1); time.sleep(0.12)
        for cmd, data, delay in _INIT:
            self._cmd(cmd, bytes([self._madctl]) if data is None else data)
            if delay:
                time.sleep(delay / 1000)
        self.backlight(True)

    def _cmd(self, cmd, data=b""):
        lgpio.gpio_write(self.chip, self.dc, 0)
        self.spi.writebytes([cmd])
        if data:
            lgpio.gpio_write(self.chip, self.dc, 1)
            self.spi.writebytes2(data)

    def backlight(self, on):
        if self.bl is not None:
            lgpio.gpio_write(self.chip, self.bl, 1 if on else 0)

    def show(self, image):
        """Show a 240x240 PIL image (any mode)."""
        rgb = np.asarray(image.convert("RGB"), dtype=np.uint16)
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        px = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        self._cmd(0x2A, b"\x00\x00\x00\xEF")  # columns 0..239
        self._cmd(0x2B, b"\x00\x00\x00\xEF")  # rows 0..239
        self._cmd(0x2C, px.astype(">u2").tobytes())

    def off(self):
        """Blank the panel (display off + sleep). The backlight stays lit unless BLK is wired."""
        self.show_black()
        self._cmd(0x28)
        self._cmd(0x10)
        time.sleep(0.12)

    def show_black(self):
        self._cmd(0x2A, b"\x00\x00\x00\xEF")
        self._cmd(0x2B, b"\x00\x00\x00\xEF")
        self._cmd(0x2C, bytes(WIDTH * HEIGHT * 2))

    def close(self):
        self.backlight(False)
        self.spi.close()
        lgpio.gpiochip_close(self.chip)
