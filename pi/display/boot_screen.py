"""Chitti boot screen: logo + start-up status, then idle eyes. Runs as the chitti-display service.

Sequence:
  1. "CHITTI" logo with a spinning ring, and a status line (Starting up / Connecting Wi-Fi / ...)
  2. When Wi-Fi is up (or after 45 s): shows the IP address, temperature and power status for a moment
  3. Eyes wake up (sleepy -> neutral), then idle: blinking and glancing around
  4. On shutdown (SIGTERM): eyes close, "Bye!", screen goes black

Test by hand (stop the service first):  sudo systemctl stop chitti-display
    ~/chitti/venv/bin/python ~/chitti/display/boot_screen.py
"""
import math
import random
import signal
import socket
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont

import eyes
from eyes import C, EXPRESSIONS, S, W, WIDTH

CYAN = (40, 220, 255)
DIM = (20, 70, 90)
WHITE = (255, 255, 255)
WAIT_FOR_WIFI = 45  # seconds


def font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "arialbd.ttf"):  # last one: for previews on Windows
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)  # Pillow >= 10.1


F_LOGO = font(46 * S)
F_TEXT = font(15 * S)
F_SMALL = font(13 * S)


def ip_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent; just picks the outgoing interface
            ip = s.getsockname()[0]
            return None if ip.startswith("127.") else ip
    except OSError:
        return None


def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read()) / 1000
    except OSError:
        return None


def power_ok():
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2).stdout
        return int(out.strip().split("=")[1], 16) & 0x5 == 0  # bit0 under-voltage now, bit2 throttled now
    except Exception:
        return None


def centred(d, y, text, f, fill):
    x0, y0, x1, y1 = d.textbbox((0, 0), text, font=f)
    d.text((C - (x1 - x0) / 2 - x0, y - (y1 - y0) / 2 - y0), text, font=f, fill=fill)


def logo_frame(t, status, progress=None, fade=1.0):
    """CHITTI logo with a spinning arc around the edge. progress (0..1) fills the ring instead."""
    img = Image.new("RGB", (W, W), "black")
    d = ImageDraw.Draw(img)
    col = tuple(int(v * fade) for v in CYAN)
    dim = tuple(int(v * fade) for v in DIM)
    m = 10 * S
    box = (m, m, W - m, W - m)
    d.arc(box, 0, 360, fill=dim, width=6 * S)
    if progress is None:
        a = (t * 300) % 360
        d.arc(box, a, a + 90, fill=col, width=6 * S)
    else:
        d.arc(box, -90, -90 + 360 * progress, fill=col, width=6 * S)
    # small glowing "eyes" above the name
    for side in (-1, 1):
        glow = 0.6 + 0.4 * math.sin(t * 3)
        r = 9 * S
        ex, ey = C + side * 32 * S, C - 42 * S
        d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=tuple(int(v * glow * fade) for v in CYAN))
    centred(d, C + 2 * S, "CHITTI", F_LOGO, tuple(int(v * fade) for v in WHITE))
    centred(d, C + 48 * S, status, F_TEXT, col)
    return img.resize((WIDTH, WIDTH), Image.LANCZOS)


def info_frame(ip, temp, power):
    img = Image.new("RGB", (W, W), "black")
    d = ImageDraw.Draw(img)
    d.arc((10 * S, 10 * S, W - 10 * S, W - 10 * S), 0, 360, fill=CYAN, width=6 * S)
    centred(d, C - 52 * S, "Hello!", F_LOGO, WHITE)
    lines = [
        (f"Wi-Fi  {ip}" if ip else "No Wi-Fi", CYAN if ip else (255, 120, 60)),
        (f"Temp  {temp:.0f}°C" if temp is not None else "", CYAN),
        ({True: "Power OK", False: "LOW POWER!", None: ""}[power], CYAN if power is not False else (255, 60, 30)),
    ]
    for i, (text, col) in enumerate(lines):
        if text:
            centred(d, C + (8 + 24 * i) * S, text, F_TEXT, col)
    return img.resize((WIDTH, WIDTH), Image.LANCZOS)


class Stop(Exception):
    pass


def _on_term(*_):
    raise Stop


def run(lcd):
    startup(lcd)
    idle(lcd)


def startup(lcd):
    """Logo, Wi-Fi wait, status card, eyes waking up. Returns when the eyes are open."""
    t0 = time.monotonic()

    # 1. logo + wait for Wi-Fi
    ip = None
    while True:
        t = time.monotonic() - t0
        ip = ip_address()
        if ip or t > WAIT_FOR_WIFI:
            break
        status = "Starting up" if t < 3 else "Connecting Wi-Fi" + "." * (int(t * 2) % 4)
        lcd.show(logo_frame(t, status))
        time.sleep(0.03)

    # ring fills up, then fades
    t1 = time.monotonic()
    while (k := (time.monotonic() - t1) / 0.6) < 1:
        lcd.show(logo_frame(time.monotonic() - t0, "Ready", progress=k))
    lcd.show(logo_frame(time.monotonic() - t0, "Ready", progress=1))
    time.sleep(0.4)

    # 2. status card
    lcd.show(info_frame(ip, cpu_temp(), power_ok()))
    time.sleep(4)

    # 3. wake up: eyes open from closed, sleepy -> neutral
    closed = dict(EXPRESSIONS["sleepy"], open=0.0)
    t1 = time.monotonic()
    while (k := (time.monotonic() - t1) / 1.2) < 1:
        e = k * k * (3 - 2 * k)
        p = eyes.blend(closed, EXPRESSIONS["sleepy"], min(1, e * 2)) if e < 0.5 else \
            eyes.blend(EXPRESSIONS["sleepy"], EXPRESSIONS["neutral"], (e - 0.5) * 2)
        lcd.show(eyes.render(p))


def idle(lcd):
    """4. idle: blink, and glance left/right/up now and then (runs forever)."""
    blinker = eyes.Blinker()
    cur = dict(EXPRESSIONS["neutral"])
    start, target, t_change = dict(cur), cur, time.monotonic()
    next_glance = t_change + random.uniform(3, 7)
    while True:
        now = time.monotonic()
        if now >= next_glance:
            name = random.choice(["neutral", "neutral", "look_left", "look_right", "thinking", "happy"])
            start, target, t_change = dict(cur), EXPRESSIONS[name], now
            next_glance = now + random.uniform(2, 6)
        k = min(1.0, (now - t_change) / 0.35)
        cur = eyes.blend(start, target, k * k * (3 - 2 * k))
        lcd.show(eyes.render(cur, blinker(now)))


def goodbye(lcd, last=None):
    p = dict(EXPRESSIONS["sleepy"])
    t1 = time.monotonic()
    while (k := (time.monotonic() - t1) / 0.5) < 1:
        lcd.show(eyes.render(dict(p, open=p["open"] * (1 - k))))
    img = Image.new("RGB", (W, W), "black")
    centred(ImageDraw.Draw(img), C, "Bye!", F_LOGO, CYAN)
    lcd.show(img.resize((WIDTH, WIDTH), Image.LANCZOS))
    time.sleep(0.8)
    lcd.off()


def main():
    from gc9a01 import GC9A01

    signal.signal(signal.SIGTERM, _on_term)
    lcd = GC9A01()
    try:
        run(lcd)
    except (Stop, KeyboardInterrupt):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        goodbye(lcd)
    finally:
        lcd.close()


if __name__ == "__main__":
    main()
