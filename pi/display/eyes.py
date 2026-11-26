"""Chitti's animated eyes on the GC9A01 round display (two eyes by default).

Usage (on the Pi, from ~/chitti):
    venv/bin/python display/eyes.py --test        # colour test: red, green, blue, white
    venv/bin/python display/eyes.py               # cycle through all expressions
    venv/bin/python display/eyes.py happy         # hold one expression (still blinks)
    venv/bin/python display/eyes.py --single      # one big eye instead of two
    venv/bin/python display/eyes.py --rgb ...     # if red and blue look swapped
Press Ctrl+C to stop. (Stop the boot-screen service first: sudo systemctl stop chitti-display)
"""
import argparse
import math
import random
import time

from PIL import Image, ImageDraw

WIDTH = 240
S = 2                      # draw at 2x, then downscale for smooth edges
W = WIDTH * S
C = W // 2                 # centre of the display

# Layout (in 2x pixels). Two eyes side by side, fully inside the round screen.
TWO_EYE_R = 100            # each eye's radius (= 50 px on the screen)
TWO_EYE_DX = 118           # each eye's distance from the centre
ONE_EYE_R = int(W * 0.40)

# Each expression is a set of numbers; switching expressions animates between them.
#   open: 0 closed .. 1 open      tilt: top-lid angle (deg, + = angry slant)   smile: 0..1 ("^" eye)
#   px, py: pupil position -1..1  pupil: pupil radius (x eye radius)  heart: 0..1   rgb: eye colour
# Colours are kept bright and saturated so they show through the tinted visor.
EXPRESSIONS = {
    "neutral":     dict(open=1.0,  tilt=0,   smile=0, px=0,    py=0,    pupil=0.42, heart=0, rgb=(40, 220, 255)),
    "happy":       dict(open=1.0,  tilt=0,   smile=1, px=0,    py=-0.1, pupil=0.42, heart=0, rgb=(40, 255, 170)),
    "sad":         dict(open=0.7,  tilt=-14, smile=0, px=0,    py=0.35, pupil=0.42, heart=0, rgb=(100, 160, 255)),
    "angry":       dict(open=0.65, tilt=24,  smile=0, px=0,    py=0.1,  pupil=0.34, heart=0, rgb=(255, 60, 30)),
    "surprised":   dict(open=1.0,  tilt=0,   smile=0, px=0,    py=0,    pupil=0.22, heart=0, rgb=(150, 240, 255)),
    "sleepy":      dict(open=0.28, tilt=-4,  smile=0, px=0,    py=0.35, pupil=0.42, heart=0, rgb=(130, 140, 255)),
    "thinking":    dict(open=0.85, tilt=8,   smile=0, px=0.5,  py=-0.6, pupil=0.38, heart=0, rgb=(200, 130, 255)),
    "look_left":   dict(open=1.0,  tilt=0,   smile=0, px=-0.7, py=0,    pupil=0.42, heart=0, rgb=(40, 220, 255)),
    "look_right":  dict(open=1.0,  tilt=0,   smile=0, px=0.7,  py=0,    pupil=0.42, heart=0, rgb=(40, 220, 255)),
    "love":        dict(open=1.0,  tilt=0,   smile=0, px=0,    py=0,    pupil=0.42, heart=1, rgb=(255, 50, 110)),
    "confused":    dict(open=0.8,  tilt=-12, smile=0, px=0.4,  py=-0.35, pupil=0.36, heart=0, rgb=(255, 200, 60)),
    "suspicious":  dict(open=0.42, tilt=10,  smile=0, px=0.55, py=0,    pupil=0.40, heart=0, rgb=(40, 220, 255)),
}


def lerp(a, b, t):
    if isinstance(a, tuple):
        return tuple(lerp(x, y, t) for x, y in zip(a, b))
    return a + (b - a) * t


def blend(p, q, t):
    """Mix two expression dicts (t=0 -> p, t=1 -> q)."""
    return {k: lerp(p[k], q[k], t) for k in q}


def _eye_tile(p, blink, R, mirror):
    """Draw one eye on its own square tile so its lids never cover the other eye."""
    h = int(R * 1.16)
    T = 2 * h
    img = Image.new("RGB", (T, T), "black")
    d = ImageDraw.Draw(img)
    c = h
    rgb = tuple(int(v) for v in p["rgb"])
    eye_scale = 1 - p["heart"]

    if eye_scale > 0.01:
        r = R * eye_scale
        d.ellipse((c - r, c - r, c + r, c + r), fill=rgb)
        # pupil + highlight (pupil hides in the happy "^" eye)
        pr = r * p["pupil"] * (1 - p["smile"])
        cx, cy = c + p["px"] * (r - pr) * 0.8, c + p["py"] * (r - pr) * 0.8
        d.ellipse((cx - pr, cy - pr, cx + pr, cy + pr), fill=(10, 10, 25))
        hr = pr * 0.35
        hx, hy = cx - pr * 0.35, cy - pr * 0.35
        d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=(255, 255, 255))

        opn = p["open"] * blink
        # top lid: a tilted black area coming down from above (mirrored for the right eye)
        top_y = c - r - 4 + (1 - opn) * (r * 1.1 + 4)
        k = math.tan(math.radians(-p["tilt"] if mirror else p["tilt"]))
        y_at = lambda x: top_y + (x - c) * k
        d.polygon([(-10, y_at(-10)), (T + 10, y_at(T + 10)), (T + 10, -10), (-10, -10)], fill="black")
        # bottom lid
        bot_y = c + r + 4 - (1 - opn) * (r * 0.9 + 4)
        d.rectangle((-10, bot_y, T + 10, T + 10), fill="black")
        # happy: a curved lid from below makes the "^" eye
        if p["smile"] > 0.01:
            ey = c + r * 1.6 - p["smile"] * r * 0.7
            d.ellipse((c - r * 1.45, ey - r * 1.1, c + r * 1.45, ey + r * 1.1), fill="black")
        # (nearly) closed: draw a closed-eye curve so the eye doesn't just vanish
        if opn < 0.1:
            if opn < 0.03:
                d.rectangle((0, 0, T, T), fill="black")     # clear leftover pupil/highlight specks
            fade = 1 - opn / 0.1
            col = tuple(int(v * fade) for v in rgb)
            d.arc((c - r * 0.85, c - r * 0.55, c + r * 0.85, c + r * 0.35), 25, 155, fill=col,
                  width=max(2, int(r * 0.13)))

    if p["heart"] > 0.01:
        sc = p["heart"] * blink ** 0.3
        pts = []
        for i in range(100):
            t = 2 * math.pi * i / 100
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((c + x * R / 17 * sc, c - y * R / 17 * sc - R * 0.05 * sc))
        d.polygon(pts, fill=rgb)
    return img


def draw_eyes(img, p, blink=1.0, two=True, cy=C, p_right=None):
    """Draw the eyes onto a 2x-size image (W x W), centred vertically at cy.
    p_right: optional different settings for the right-hand eye (e.g. a wink)."""
    if two:
        for side, mirror in ((-1, False), (1, True)):
            tile = _eye_tile(p_right if (side == 1 and p_right) else p, blink, TWO_EYE_R, mirror)
            img.paste(tile, (C + side * TWO_EYE_DX - tile.width // 2, int(cy) - tile.height // 2))
    else:
        tile = _eye_tile(p, blink, ONE_EYE_R, False)
        img.paste(tile, (C - tile.width // 2, int(cy) - tile.height // 2))


def render(p, blink=1.0, two=True, p_right=None, emoji=None, t=0.0):
    """emoji: optional name from emoji.ALL, animated by t (seconds since it appeared)."""
    img = Image.new("RGB", (W, W), "black")
    import emoji as em
    rgb = tuple(int(v) for v in p["rgb"])
    if emoji in em.REPLACE_EYES and two:
        em.draw_eye_replacement(ImageDraw.Draw(img), emoji, t, rgb)
    else:
        draw_eyes(img, p, blink, two, p_right=p_right)
        if emoji in em.OVERLAYS:
            em.draw_overlay(ImageDraw.Draw(img), emoji, t, rgb)
    return img.resize((WIDTH, WIDTH), Image.LANCZOS)


class Blinker:
    """Returns 1.0 (open) most of the time and a quick close/open every few seconds."""

    def __init__(self):
        self.next = time.monotonic() + random.uniform(2, 5)

    def __call__(self, now):
        if now < self.next:
            return 1.0
        bt = (now - self.next) / 0.18
        if bt >= 1:
            self.next = now + random.uniform(2.5, 6)
            return 1.0
        return abs(1 - 2 * bt)


def colour_test(lcd):
    for name, rgb in [("red", (255, 0, 0)), ("green", (0, 255, 0)), ("blue", (0, 0, 255)), ("white", (255, 255, 255))]:
        print(f"Showing {name}")
        lcd.show(Image.new("RGB", (WIDTH, WIDTH), rgb))
        time.sleep(1.5)


def main():
    from gc9a01 import GC9A01

    ap = argparse.ArgumentParser()
    ap.add_argument("expression", nargs="?", choices=sorted(EXPRESSIONS), help="hold one expression")
    ap.add_argument("--test", action="store_true", help="show a red/green/blue/white colour test")
    ap.add_argument("--rgb", action="store_true", help="use RGB order if red and blue look swapped")
    ap.add_argument("--single", action="store_true", help="one big eye instead of two")
    ap.add_argument("--hold", type=float, default=3.0, help="seconds per expression when cycling")
    args = ap.parse_args()

    lcd = GC9A01(bgr=not args.rgb)
    try:
        if args.test:
            colour_test(lcd)
            return

        order = [args.expression] if args.expression else list(EXPRESSIONS)
        cur = dict(EXPRESSIONS["neutral"])
        idx, target_name = 0, order[0]
        start = dict(cur)
        t_change = time.monotonic()
        next_switch = t_change + args.hold
        blinker = Blinker()
        frames, t_fps = 0, t_change
        print(f"Expression: {target_name}")

        while True:
            now = time.monotonic()
            if len(order) > 1 and now >= next_switch:
                idx = (idx + 1) % len(order)
                target_name = order[idx]
                start, t_change, next_switch = dict(cur), now, now + args.hold
                print(f"Expression: {target_name}")

            # ease towards the target expression over 0.35 s
            t = min(1.0, (now - t_change) / 0.35)
            cur = blend(start, EXPRESSIONS[target_name], t * t * (3 - 2 * t))

            lcd.show(render(cur, blinker(now), two=not args.single))
            frames += 1
            if now - t_fps >= 5:
                print(f"  {frames / (now - t_fps):.1f} fps")
                frames, t_fps = 0, now
    except KeyboardInterrupt:
        pass
    finally:
        lcd.close()


if __name__ == "__main__":
    main()
