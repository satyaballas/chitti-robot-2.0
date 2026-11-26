"""Chitti's voice: offline text-to-speech with Piper, played on the speaker."""
import os
import re
import subprocess
import tempfile
import wave

import config

TELUGU = re.compile(r"[ఀ-౿]")

# Robot voice effects, applied after Piper speaks. ring = metallic buzz (Hz, mix), comb = tin-can echo
# (ms, mix), pitch = played this much higher (and faster), crush = lo-fi bit depth (0 = off).
ROBOT_STYLES = {
    "off":     dict(ring=(0, 0.0),   comb=(0, 0.0),   pitch=1.0,  crush=0),
    "light":   dict(ring=(55, 0.35), comb=(3.5, 0.35), pitch=1.04, crush=0),
    "classic": dict(ring=(70, 0.6),  comb=(5.0, 0.5),  pitch=1.07, crush=0),
    "heavy":   dict(ring=(40, 0.9),  comb=(7.0, 0.6),  pitch=1.1,  crush=7),
}


def robotize(path, style):
    """Rewrite a mono 16-bit wav in place with the robot effect."""
    import numpy as np
    s = ROBOT_STYLES.get(style, ROBOT_STYLES["off"])
    if style == "off":
        return
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    t = np.arange(len(x)) / sr
    f, m = s["ring"]
    if m:
        x = x * (1 - m) + x * np.sin(2 * np.pi * f * t) * m * 1.6
    d, m = s["comb"]
    if m:
        n = int(sr * d / 1000)
        y = x.copy()
        y[n:] += m * x[:-n]
        y[2 * n:] += m * 0.5 * x[:-2 * n]
        x = y
    if s["crush"]:
        q = 2 ** (s["crush"] - 1)
        x = np.round(x * q) / q
    x = x / max(1e-6, np.abs(x).max()) * 0.9
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(int(sr * s["pitch"]))
        w.writeframes((x * 32767).astype(np.int16).tobytes())


class Mouth:
    def __init__(self):
        from piper import PiperVoice
        self.voices = {}
        for lang, name in config.VOICES.items():
            path = os.path.join(config.MODELS, "piper", f"{name}.onnx")
            if os.path.exists(path):
                self.voices[lang] = PiperVoice.load(path)
            else:
                print(f"[mouth] voice {name} not found, {lang} will use English")
        if "en" not in self.voices:
            raise SystemExit("English Piper voice missing - download it first (see README)")

    def beep(self):
        """Short rising two-tone beep: 'I'm listening'."""
        if not hasattr(self, "_beep"):
            import numpy as np
            sr = 22050
            t = np.arange(int(sr * 0.09)) / sr
            tone = np.concatenate([np.sin(2 * np.pi * 880 * t), np.sin(2 * np.pi * 1320 * t)])
            fade = np.minimum(1, np.minimum(np.arange(len(tone)), np.arange(len(tone))[::-1]) / 200)
            self._beep = os.path.join(tempfile.gettempdir(), "chitti-beep.wav")
            with wave.open(self._beep, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
                w.writeframes((tone * fade * 0.4 * 32767).astype(np.int16).tobytes())
        subprocess.run(["aplay", "-q", "-D", config.SPEAKER_DEVICE, self._beep], check=False,
                       stderr=subprocess.DEVNULL)

    def say(self, text):
        lang = "te" if TELUGU.search(text) and "te" in self.voices else "en"
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            with wave.open(path, "wb") as w:
                self.voices[lang].synthesize_wav(text, w)
            robotize(path, getattr(config, "ROBOT_VOICE", "off"))
            subprocess.run(["aplay", "-q", "-D", config.SPEAKER_DEVICE, path], check=False)
        finally:
            os.unlink(path)
