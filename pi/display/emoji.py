"""Chitti's emoji-style reactions, drawn on top of (or instead of) the eyes. Original designs.

All drawing is on the 2x canvas used by eyes.py (480x480, centre 240; eyes at x = 240 +/- 118, y = 240,
radius 100). `t` is seconds since the emoji appeared, so everything animates.

Overlays (eyes stay):  zzz, question, exclaim, music, hearts, sparkle, sweat, tears, anger
Eye replacements:      star_eyes, dizzy
"""
import math

from PIL import ImageFont

C = 240
EYE_DX = 118
EYE_R = 100

OVERLAYS = ["zzz", "question", "exclaim", "music", "hearts", "sparkle", "sweat", "tears", "anger"]
REPLACE_EYES = ["star_eyes", "dizzy"]
ALL = OVERLAYS + REPLACE_EYES

_fonts = {}


def _font(size):
    if size not in _fonts:
        for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arialbd.ttf"):
            try:
                _fonts[size] = ImageFont.truetype(path, size)
                break
            except OSError:
                pass
        else:
            _fonts[size] = ImageFont.load_default(size=size)
    return _fonts[size]


def _text(d, xy, s, size, fill):
    d.text(xy, s, font=_font(size), fill=fill, anchor="mm")


def _scale(rgb, k):
    return tuple(int(max(0, min(255, v * k))) for v in rgb)


def _heart(d, x, y, s, fill):
    pts = []
    for i in range(40):
        a = 2 * math.pi * i / 40
        hx = 16 * math.sin(a) ** 3
        hy = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pts.append((x + hx * s / 17, y - hy * s / 17))
    d.polygon(pts, fill=fill)


def _star(d, x, y, r_out, r_in, rot, fill, points=5):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / points - math.pi / 2
        pts.append((x + r * math.cos(a), y + r * math.sin(a)))
    d.polygon(pts, fill=fill)


def _note(d, x, y, s, fill, double=False):
    """An eighth note (or a pair of beamed notes)."""
    w = s * 0.55
    d.ellipse((x - w, y - w * 0.75, x + w, y + w * 0.75), fill=fill)
    stem_x = x + w * 0.85
    d.rectangle((stem_x - s * 0.12, y - s * 2.2, stem_x + s * 0.06, y), fill=fill)
    if double:
        x2 = x + s * 1.6
        d.ellipse((x2 - w, y - w * 0.75, x2 + w, y + w * 0.75), fill=fill)
        stem2 = x2 + w * 0.85
        d.rectangle((stem2 - s * 0.12, y - s * 2.2, stem2 + s * 0.06, y), fill=fill)
        d.polygon([(stem_x - s * 0.12, y - s * 2.2), (stem2 + s * 0.06, y - s * 2.2),
                   (stem2 + s * 0.06, y - s * 1.75), (stem_x - s * 0.12, y - s * 1.75)], fill=fill)
    else:
        d.polygon([(stem_x, y - s * 2.2), (stem_x + s * 0.9, y - s * 1.5),
                   (stem_x + s * 0.8, y - s * 1.2), (stem_x, y - s * 1.75)], fill=fill)


def _drop(d, x, y, s, fill):
    d.ellipse((x - s, y - s, x + s, y + s), fill=fill)
    d.polygon([(x - s * 0.92, y - s * 0.35), (x, y - s * 2.4), (x + s * 0.92, y - s * 0.35)], fill=fill)


def draw_overlay(d, name, t, rgb):
    """Things drawn on top of the eyes."""
    if name == "zzz":
        # three Z's drifting up and to the right, growing and fading in a loop
        for i in range(3):
            k = ((t / 2.4) + i / 3) % 1.0
            size = int(34 + 40 * k)
            x = C + 40 + 90 * k
            y = 150 - 90 * k
            fade = min(1.0, k * 4) * (1 - k) ** 0.5
            _text(d, (x, y), "Z", size, _scale((150, 170, 255), fade * 1.2))
    elif name == "question":
        bob = 10 * math.sin(t * 4)
        tilt = 8 * math.sin(t * 2)
        _text(d, (C + 95 + tilt, 100 + bob), "?", 100, (255, 210, 60))
    elif name == "exclaim":
        pop = min(1.0, t / 0.15)
        size = int(60 + 70 * pop)
        _text(d, (C + 90, 100), "!", size, (255, 80, 60))
    elif name == "music":
        for i in range(3):
            k = ((t / 2.0) + i / 3) % 1.0
            x = C - 110 + 220 * ((i * 0.37 + k * 0.6) % 1.0)
            y = 150 - 80 * k + 8 * math.sin(t * 6 + i)
            fade = min(1.0, k * 5) * (1 - k)
            _note(d, x, y, 22, _scale((255, 230, 120), fade * 1.1), double=(i == 1))
    elif name == "hearts":
        for i in range(4):
            k = ((t / 2.2) + i / 4) % 1.0
            x = C + (-1 if i % 2 else 1) * (40 + 60 * ((i * 0.53) % 1.0)) + 15 * math.sin(t * 3 + i)
            y = 150 - 90 * k
            fade = min(1.0, k * 5) * (1 - k)
            _heart(d, x, y, 18 + 14 * k, _scale((255, 60, 120), fade * 1.2))
    elif name == "sparkle":
        spots = [(C - 190, 120), (C + 185, 110), (C - 40, 90), (C + 60, 395), (C - 150, 370), (C + 170, 360)]
        for i, (x, y) in enumerate(spots):
            tw = max(0.0, math.sin(t * 5 + i * 1.7))
            if tw > 0.05:
                _star(d, x, y, 26 * tw, 6 * tw, 0, _scale((255, 255, 200), tw), points=4)
    elif name == "sweat":
        k = (t / 1.6) % 1.0
        _drop(d, C + 165, 120 + 60 * k, 16, _scale((120, 200, 255), 1 - k * 0.6))
    elif name == "tears":
        for side in (-1, 1):
            for i in range(2):
                k = ((t / 1.1) + i * 0.5) % 1.0
                x = C + side * (EYE_DX - 35)
                y = C + 70 + 140 * k
                _drop(d, x, y, 11, _scale((90, 160, 255), 1 - k * 0.7))
    elif name == "anger":
        # four bulging curved strokes (an "anger mark"), throbbing
        s = 30 * (1 + 0.18 * abs(math.sin(t * 7)))
        x, y = C + 95, 100
        col = (255, 50, 40)
        w = max(4, int(s * 0.28))
        for dx, dy, start in ((-1, -1, 0), (1, -1, 90), (1, 1, 180), (-1, 1, 270)):
            cx, cy = x + dx * s * 0.75, y + dy * s * 0.75
            d.arc((cx - s * 0.6, cy - s * 0.6, cx + s * 0.6, cy + s * 0.6), start, start + 90, fill=col, width=w)


def draw_eye_replacement(d, name, t, rgb):
    """Eyes replaced by a symbol (both eyes)."""
    for side in (-1, 1):
        x, y = C + side * EYE_DX, C
        if name == "star_eyes":
            pulse = 1 + 0.08 * math.sin(t * 8)
            rot = 0.25 * math.sin(t * 2)
            _star(d, x, y, EYE_R * 0.95 * pulse, EYE_R * 0.42 * pulse, rot, (255, 215, 50))
            _star(d, x - 18, y - 22, 16, 7, rot, (255, 255, 220))
        elif name == "dizzy":
            rot = t * 5 * side
            pts = []
            for i in range(120):
                a = i / 120 * 3.2 * 2 * math.pi
                r = EYE_R * 0.9 * i / 120
                pts.append((x + r * math.cos(a + rot), y + r * math.sin(a + rot)))
            d.line(pts, fill=rgb, width=12, joint="curve")
