"""Cartoon-style animation for Chitti's eyes while its body moves.

Each effect has two halves:
    pre(name, p, el, secs, now)   -> (p, p_right)   change the eye settings before drawing
    post(name, img, el, secs, now) -> img            squash / stretch / lean the drawn frame and add
                                                      speed lines, swooshes and sparkles on top
`el` is seconds since the move started, `secs` its length. Works on the final 240x240 frame.
"""
import colorsys
import math

from PIL import Image, ImageDraw

C = 120            # centre of the 240x240 screen
NAMES = ("go_forward", "go_back", "turn_left", "turn_right", "dance", "listen")


def _ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def _affine(img, sx=1.0, sy=1.0, dx=0.0, dy=0.0, shear=0.0):
    """Scale around the centre (squash/stretch), shift, and lean (shear > 0 leans the top left)."""
    a, e = 1 / sx, 1 / sy
    b = -shear / (sx * sy)
    cx = C - a * (C + dx) - b * (C + dy)
    cy = C - e * (C + dy)
    return img.transform(img.size, Image.AFFINE, (a, b, cx, 0, e, cy),
                         resample=Image.BILINEAR, fillcolor=(0, 0, 0))


def _rumble(now, px=1.3):
    return px if int(now * 14) % 2 else -px


def _speed_lines(d, el, outward, col):
    """Streaks above and below the eyes, rushing outward (forward) or inward (backward)."""
    for i in range(12):
        side = -1 if i % 2 else 1                    # top / bottom
        ang = math.radians(side * (45 + 90 * ((i * 0.37) % 1.0)))
        k = (el * 2.2 + i * 0.29) % 1.0
        if not outward:
            k = 1 - k
        r0 = 70 + 55 * k
        r1 = r0 + 10 + 14 * k
        fade = math.sin(math.pi * k)
        c = tuple(int(v * fade) for v in col)
        d.line([(C + r0 * math.cos(ang), C + r0 * math.sin(ang)),
                (C + r1 * math.cos(ang), C + r1 * math.sin(ang))], fill=c, width=3)


def _swoosh(d, el, left, col):
    """A comet-like arc sweeping over the top of the eyes in the turning direction."""
    k = (el * 1.3) % 1.0
    head = 300 - 60 * k if left else 240 + 60 * k     # PIL angles: 270 = straight up; stays above the eyes
    for j in range(8):
        a0 = head + (j * 4 if left else -j * 4)
        fade = (1 - j / 8) * math.sin(math.pi * k)
        c = tuple(int(v * fade) for v in col)
        d.arc((C - 105, C - 100, C + 105, C + 110), min(a0, a0 + 5), max(a0, a0 + 5), fill=c, width=6)


def _sparkles(d, now):
    for i, (x, y) in enumerate([(30, 70), (205, 60), (40, 185), (200, 190), (120, 22)]):
        tw = max(0.0, math.sin(now * 6 + i * 1.9))
        if tw > 0.1:
            r, ri = 10 * tw, 3 * tw
            pts = []
            for n in range(8):
                rr = r if n % 2 == 0 else ri
                a = math.pi * n / 4 - math.pi / 2
                pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
            d.polygon(pts, fill=(int(255 * tw), int(255 * tw), int(200 * tw)))


def _voice_bars(d, now, level):
    """A little equaliser under the eyes: breathes when quiet, jumps with the voice (level 0..1)."""
    n, w, gap = 9, 9, 6
    x0 = C - (n * w + (n - 1) * gap) / 2
    base = 196
    for i in range(n):
        centre = 1 - abs(i - (n - 1) / 2) / ((n - 1) / 2)          # taller in the middle
        idle = 3 + 3 * (0.5 + 0.5 * math.sin(now * 3 + i * 0.7))
        voice = level * (10 + 26 * centre) * (0.6 + 0.4 * abs(math.sin(now * 11 + i * 1.9)))
        h = idle + voice
        x = x0 + i * (w + gap)
        g = 0.55 + 0.45 * min(1.0, level * 1.5)
        col = (int(90 * g), int(230 * g), int(255 * g))
        d.rounded_rectangle((x, base - h, x + w, base + h), radius=4, fill=col)


def pre(name, p, el, secs, now, level=0.0):
    p_right = None
    if name == "listen":
        p["open"] = min(1.0, p["open"] + 0.1 * level)               # eyes widen a little as you talk
        p["py"] = -0.25 + 0.05 * math.sin(now * 2)
        p["px"] = 0.15 * math.sin(now * 0.9)                         # small attentive glances
        return p, p_right
    if name == "go_back":
        # nervous little shiver of the pupils
        p["px"] += 0.08 * math.sin(now * 25)
    elif name in ("turn_left", "turn_right"):
        s = -1 if name == "turn_left" else 1
        p["px"] = s * (0.5 + 0.4 * _ease(el / 0.25))       # pupils lead the turn
    elif name == "dance":
        beat = el * 2.0                                     # 2 beats a second
        p["rgb"] = tuple(int(v * 255) for v in colorsys.hsv_to_rgb((el * 0.35) % 1.0, 0.8, 1.0))
        p["px"] = 0.5 * math.sin(math.pi * beat)
        if int(beat) % 4 == 3:                              # a wink every fourth beat
            w = math.sin(math.pi * (beat % 1.0))
            p_right = dict(p, open=p["open"] * (1 - w))
    return p, p_right


def post(name, img, el, secs, now, level=0.0):
    end = max(0.0, secs - el)
    if name == "listen":
        # perk up (quick stretch), then hold a head-cocked listening pose that bobs gently with the voice
        perk = math.exp(-7 * el) * math.sin(min(math.pi, el * 12))
        tilt = 0.14 * _ease(el / 0.35)
        img = _affine(img, 1 - 0.06 * perk, 1 + 0.18 * perk + 0.03 * level, dy=-14 * perk - 12 - 3 * level,
                      shear=tilt)
        _voice_bars(ImageDraw.Draw(img), now, level)
        return img
    if name == "go_forward":
        if el < 0.25:                                       # anticipation: squash down
            k = _ease(el / 0.25)
            img = _affine(img, 1 + 0.12 * k, 1 - 0.2 * k, dy=8 * k)
        else:                                               # launch: stretch, settle, rumble
            s = 0.08 + 0.14 * math.exp(-5 * (el - 0.25))
            img = _affine(img, 1 - s * 0.6, 1 + s, dy=_rumble(now) - 4)
        d = ImageDraw.Draw(img)
        if el > 0.2 and end > 0.1:
            _speed_lines(d, el, outward=True, col=(120, 255, 220))
    elif name == "go_back":
        if el < 0.35:                                       # startled hop
            k = math.sin(math.pi * el / 0.35)
            img = _affine(img, 1 - 0.08 * k, 1 + 0.15 * k, dy=-16 * k)
        else:                                               # shrink back, wobble nervously
            img = _affine(img, 0.9, 0.9, dy=_rumble(now) + 6, shear=0.05 * math.sin(now * 9))
        d = ImageDraw.Draw(img)
        if el > 0.3 and end > 0.1:
            _speed_lines(d, el, outward=False, col=(160, 200, 255))
    elif name in ("turn_left", "turn_right"):
        s = -1 if name == "turn_left" else 1
        k = _ease(el / 0.3) * _ease(end / 0.3)              # lean in, straighten at the end
        img = _affine(img, 1 - 0.14 * k, 1 + 0.04 * k, dx=s * 7 * k, dy=_rumble(now), shear=-s * 0.25 * k)
        _swoosh(ImageDraw.Draw(img), el, s < 0, (255, 220, 90))
    elif name == "dance":
        beat = el * 2.0
        bounce = abs(math.sin(math.pi * beat))
        img = _affine(img, 1 + 0.1 * (1 - bounce), 1 - 0.12 * (1 - bounce) + 0.06 * bounce,
                      dy=-14 * bounce + 6, shear=0.18 * math.sin(math.pi * beat / 2))
        _sparkles(ImageDraw.Draw(img), now)
    return img
