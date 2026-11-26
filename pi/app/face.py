"""Chitti's face: runs the round display in a background thread and shows the robot's mood.

    face = Face()            # starts the boot screen, then the eyes
    face.mode("listening")   # idle | listening | thinking | speaking | error | waiting
    face.express("happy")    # hold an expression (from eyes.EXPRESSIONS) until the next mode change
    face.react("confused")   # play a short reaction, then go back to the current mode
    face.emoji("music", 5)   # show an emoji (display/emoji.py) for a few seconds
    face.close()             # eyes close, "Bye!", screen off

While idle, Chitti gets livelier and then sleepier the longer nobody talks to it:
    calm (0-10 s) -> playful (little animations) -> drowsy (2 min) -> asleep (5 min; slower redraw, cooler CPU)
At night (22:00-06:00) it gets drowsy and falls asleep sooner.
If the display can't be opened (not wired, or another program is using it), Face does nothing.
"""
import math
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "display"))

import emoji as em  # noqa: E402
import motion_fx as fx  # noqa: E402
import eyes  # noqa: E402
from eyes import EXPRESSIONS  # noqa: E402

PLAYFUL_AFTER = 10       # seconds idle before little animations start
DROWSY_AFTER = 120       # ... before heavy lids and nodding off
ASLEEP_AFTER = 300       # ... before sleeping
NIGHT_DROWSY_AFTER = 30  # at night (22:00-06:00)
NIGHT_ASLEEP_AFTER = 120

MODE_EXPRESSION = {
    "idle": "neutral",
    "listening": "surprised",
    "thinking": "thinking",
    "speaking": "happy",
    "error": "sad",
    "waiting": "sleepy",     # no microphone plugged in / shutting down
}


def X(name, **changes):
    """An expression from eyes.EXPRESSIONS with some values changed."""
    return dict(EXPRESSIONS[name], **changes)


# Each animation is a list of steps: (expression, seconds) or (effect name, seconds).
# Effects are drawn on top of the current expression: "roll" (eyes circle), "wink", "nod" (nodding off).
ANIMATIONS = {
    "look_around": [(X("look_left"), 0.9), (X("look_right"), 0.9), (X("neutral"), 0.3)],
    "glance_up":   [(X("neutral", px=0.35, py=-0.75), 1.2), (X("neutral"), 0.2)],
    "yawn":        [(X("sleepy", open=0.08, tilt=-6), 1.3), (X("surprised"), 0.35), (X("neutral"), 0.2)],
    "suspicious":  [(X("suspicious"), 1.0), (X("suspicious", px=-0.55), 1.0), (X("neutral"), 0.2)],
    "happy":       [(X("happy"), 1.6), (X("neutral"), 0.2)],
    "eye_roll":    [("roll", 1.4)],
    "wink":        [(X("happy", smile=0.4), 0.2), ("wink", 0.6), (X("neutral"), 0.2)],
    "love":        [(X("happy"), 2.0, "hearts"), (X("neutral"), 0.3)],
    "hum":         [(X("happy", smile=0.5, py=-0.3), 2.6, "music"), (X("neutral"), 0.2)],
    "sparkle":     [(X("happy"), 1.8, "sparkle"), (X("neutral"), 0.2)],
    "starstruck":  [(X("neutral"), 1.4, "star_eyes"), (X("neutral"), 0.2)],
    "oops":        [(X("look_left", open=0.8), 1.6, "sweat"), (X("neutral"), 0.2)],
}
EMOJIS = em.ALL
ANIMATION_WEIGHTS = {"look_around": 3, "glance_up": 2, "yawn": 1, "suspicious": 1, "happy": 2,
                     "eye_roll": 1, "wink": 1, "love": 0.6, "hum": 1.2, "sparkle": 0.8,
                     "starstruck": 0.4, "oops": 0.5}

REACTIONS = {
    "confused": [(X("confused"), 1.6, "question")],
    "startled": [(X("surprised", pupil=0.15), 0.6, "exclaim")],
}

# While the body moves: (expression, effect drawn on top, emoji or None)
ACTIONS = {
    "forward":     (X("neutral", open=0.75, tilt=14, py=-0.1, pupil=0.36, rgb=(40, 255, 200)), "go_forward", None),
    "back":        (X("surprised", open=0.85, py=0.45, pupil=0.3), "go_back", "sweat"),
    "left":        (X("look_left", px=-0.85, tilt=6), "turn_left", None),
    "right":       (X("look_right", px=0.85, tilt=6), "turn_right", None),
    "slide_left":  (X("look_left", px=-0.85), "turn_left", None),
    "slide_right": (X("look_right", px=0.85), "turn_right", None),
}

DROWSY = X("sleepy", open=0.45)
ASLEEP = X("sleepy", open=0.07, py=0.4, rgb=(60, 70, 170))


class Face:
    def __init__(self, boot_screen=True):
        self._lock = threading.Lock()
        self._mode = "idle"
        self._override = None
        self._idle_since = time.monotonic()
        self._stage = "calm"
        self._queue, self._step_end, self._in_anim = [], 0.0, False
        self._effect = None                     # (name, start, seconds)
        self._emoji = None                      # (name, start, until)
        self._asleep_since = 0.0
        self._target = EXPRESSIONS["neutral"]
        self._cur = dict(self._target)
        self._start = dict(self._target)
        self._changed = time.monotonic()
        self._stop = threading.Event()
        self.lcd = None
        try:
            from gc9a01 import GC9A01
            self.lcd = GC9A01()
        except Exception as e:  # no display: keep going without one
            print(f"[face] display not available ({e}); running without eyes")
            return
        self._thread = threading.Thread(target=self._run, args=(boot_screen,), daemon=True)
        self._thread.start()

    # ---- called by the app -------------------------------------------------
    def mode(self, name):
        with self._lock:
            now = time.monotonic()
            was_asleep = self._mode == "idle" and self._stage == "asleep"
            self._mode = name
            if name == "speaking" and self._effect and self._effect[0] == "dance" and self._in_anim:
                return                      # keep dancing while Chitti talks
            self._queue, self._in_anim, self._effect = [], False, None
            if name == "idle":
                self._idle_since, self._stage = now, "calm"
            if name == "listening":
                self._emoji = None
            if name == "speaking" and self._override:
                return                      # keep the expression Claude chose
            self._override = None
            self._set(MODE_EXPRESSION.get(name, "neutral"))
            if was_asleep and name != "idle":
                self._play(REACTIONS["startled"], now)     # jolt awake

    def express(self, name):
        with self._lock:
            if name in EXPRESSIONS:
                self._queue, self._in_anim, self._effect = [], False, None
                self._override = name
                self._set(name)

    def react(self, name):
        with self._lock:
            if name in REACTIONS:
                self._play(REACTIONS[name], time.monotonic())

    def action(self, name, seconds):
        """Act out a body movement for `seconds` (eyes look where it's going, a little rumble)."""
        with self._lock:
            if name not in ACTIONS:
                return
            expr, effect, emo = ACTIONS[name]
            now = time.monotonic()
            self._queue, self._in_anim, self._step_end = [], True, now + seconds
            self._set(expr)
            self._effect = (effect, now, seconds)
            if emo:
                self._emoji = (emo, now, now + seconds)

    def dance(self, seconds=8.0):
        """Happy eyes bopping side to side with music notes; the notes and smile last through the reply."""
        with self._lock:
            now = time.monotonic()
            self._override = "happy"
            self._queue, self._in_anim, self._step_end = [], True, now + seconds
            self._set(X("happy", smile=0.45, py=-0.3))      # half-smile so the swaying pupils show
            self._effect = ("dance", now, seconds)
            self._emoji = ("music", now, now + seconds)

    def emoji(self, name, seconds=5.0):
        with self._lock:
            if name in EMOJIS:
                now = time.monotonic()
                self._emoji = (name, now, now + seconds)

    def close(self):
        if not self.lcd:
            return
        self._stop.set()
        self._thread.join(timeout=3)
        try:
            import boot_screen
            boot_screen.goodbye(self.lcd)
        finally:
            self.lcd.close()

    # ---- helpers (call with the lock held) --------------------------------------
    def _set(self, target):
        self._start = dict(self._cur)
        self._target = EXPRESSIONS[target] if isinstance(target, str) else target
        self._changed = time.monotonic()

    def _play(self, steps, now):
        self._queue, self._in_anim, self._step_end = list(steps), True, now

    def _base(self):
        """What the face rests on when no animation is playing."""
        if self._mode != "idle":
            return self._override or MODE_EXPRESSION.get(self._mode, "neutral")
        return {"drowsy": DROWSY, "asleep": ASLEEP}.get(self._stage, "neutral")

    def _idle_stage(self, now):
        hour = time.localtime().tm_hour
        night = hour >= 22 or hour < 6
        drowsy, asleep = (NIGHT_DROWSY_AFTER, NIGHT_ASLEEP_AFTER) if night else (DROWSY_AFTER, ASLEEP_AFTER)
        t = now - self._idle_since
        if t >= asleep:
            return "asleep"
        if t >= drowsy:
            return "drowsy"
        return "playful" if t >= PLAYFUL_AFTER else "calm"

    # ---- display thread ----------------------------------------------------
    def _run(self, boot_screen):
        if boot_screen:
            import boot_screen as bs
            bs.startup(self.lcd)
        blinker = eyes.Blinker()
        next_event = time.monotonic() + 4
        while not self._stop.is_set():
            t_frame = time.monotonic()
            now = t_frame
            with self._lock:
                mode = self._mode

                # play the next step of an animation / reaction
                if self._in_anim and now >= self._step_end:
                    if self._queue:
                        what, secs, *extra = self._queue.pop(0)
                        if extra:
                            self._emoji = (extra[0], now, now + secs)
                        if isinstance(what, str):
                            self._effect = (what, now, secs)
                        else:
                            self._set(what)
                        self._step_end = now + secs
                    else:
                        self._in_anim, self._effect = False, None
                        self._set(self._base())

                # idle life: calm -> playful -> drowsy -> asleep
                if mode == "idle":
                    stage = self._idle_stage(now)
                    if stage != self._stage:
                        self._stage = stage
                        if stage == "asleep":
                            self._asleep_since = now
                        if not self._in_anim:
                            self._set(self._base())
                    if not self._in_anim and now >= next_event:
                        if stage == "playful":
                            names = list(ANIMATION_WEIGHTS)
                            name = random.choices(names, [ANIMATION_WEIGHTS[n] for n in names])[0]
                            self._play(ANIMATIONS[name], now)
                            next_event = now + random.uniform(4, 8)
                        elif stage == "drowsy":
                            self._play([("nod", 1.8)], now)
                            next_event = now + random.uniform(5, 9)
                        else:
                            next_event = now + 2
                elif mode == "thinking" and not self._in_anim and now >= next_event:
                    # eyes dart around while waiting for the answer
                    self._set(random.choice(["thinking", "look_left", "look_right"]))
                    next_event = now + random.uniform(0.6, 1.2)

                k = min(1.0, (now - self._changed) / 0.3)
                self._cur = eyes.blend(self._start, self._target, k * k * (3 - 2 * k))
                p, p_right, effect = dict(self._cur), None, self._effect
                stage = self._stage if mode == "idle" else None
                emo = self._emoji if self._emoji and now < self._emoji[2] else None
                if stage == "asleep":
                    emo = ("zzz", self._asleep_since, 0)
                emoji_name, emoji_t = (emo[0], now - emo[1]) if emo else (None, 0.0)

            # effects drawn on top of the expression
            if effect:
                name, t0, secs = effect
                x = min(1.0, (now - t0) / secs)
                bump = math.sin(math.pi * x)
                if name == "roll":
                    a = 2 * math.pi * x
                    amp = 0.75 * min(1.0, 4 * x, 4 * (1 - x))
                    p["px"], p["py"] = amp * math.sin(a), -amp * math.cos(a)
                elif name == "wink":
                    p_right = dict(p, open=p["open"] * (1 - bump))
                elif name == "nod":
                    p["open"] *= 1 - 0.9 * bump
                elif name in fx.NAMES:      # movement animation (motion_fx.py)
                    p, p_right = fx.pre(name, p, now - t0, secs, now)
            if mode == "speaking":  # gentle bounce while talking
                p["open"] = p["open"] * (0.85 + 0.15 * abs(((now * 4) % 2) - 1))

            if stage == "asleep":
                breath = 0.5 + 0.5 * math.sin(2 * math.pi * now / 4)      # slow breathing glow
                p["open"] = 0.0
                p["rgb"] = tuple(v * (0.45 + 0.55 * breath) for v in p["rgb"])
                self.lcd.show(eyes.render(p, 1.0, p_right=p_right, emoji=emoji_name, t=emoji_t))
                time.sleep(0.25)            # ~4 fps while asleep keeps the CPU cool
            else:
                img = eyes.render(p, blinker(now), p_right=p_right, emoji=emoji_name, t=emoji_t)
                if effect and effect[0] in fx.NAMES and now - effect[1] < effect[2]:
                    img = fx.post(effect[0], img, now - effect[1], effect[2], now)
                self.lcd.show(img)
                time.sleep(max(0.0, 1 / 15 - (time.monotonic() - t_frame)))   # cap at 15 fps
