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


def pad_start(path, seconds=0.25):
    """Prepend a little silence: Bluetooth speakers often swallow the first moment of sound."""
    with wave.open(path, "rb") as w:
        params, data = w.getparams(), w.readframes(w.getnframes())
    with wave.open(path, "wb") as w:
        w.setparams(params)
        w.writeframes(b"\0" * (int(params.framerate * seconds) * params.sampwidth * params.nchannels) + data)


class Mouth:
    _bt_checked, _bt_ok, _bt_retry = 0.0, False, 0.0

    def speaker(self):
        """(ALSA device, is_bluetooth): the Bluetooth speaker if connected, else the profile's speaker."""
        bt = getattr(config, "BT_SPEAKER", None)
        if not bt:
            return config.SPEAKER_DEVICE, False
        import time
        now = time.monotonic()
        if now - self._bt_checked > 5:                     # ask bluez at most every 5 s
            self._bt_checked = now
            try:
                out = subprocess.run(["bluetoothctl", "info", bt["mac"]], capture_output=True,
                                     text=True, timeout=3).stdout
                self._bt_ok = "Connected: yes" in out
            except Exception:
                self._bt_ok = False
            if not self._bt_ok and now - self._bt_retry > 60:  # speaker switched on later? reconnect quietly
                self._bt_retry = now
                subprocess.Popen(["bluetoothctl", "connect", bt["mac"]], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        return (bt["pcm"], True) if self._bt_ok else (config.SPEAKER_DEVICE, False)

    def _play(self, path):
        dev, is_bt = self.speaker()
        if is_bt:
            pad_start(path)
        r = subprocess.run(["aplay", "-q", "-D", dev, path], check=False, stderr=subprocess.DEVNULL)
        if r.returncode != 0 and is_bt:                    # Bluetooth dropped mid-way: use the wired speaker
            self._bt_ok = False
            subprocess.run(["aplay", "-q", "-D", config.SPEAKER_DEVICE, path], check=False,
                           stderr=subprocess.DEVNULL)

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
        import shutil
        tmp = self._beep + ".play.wav"
        shutil.copy(self._beep, tmp)                        # _play may pad it for Bluetooth
        self._play(tmp)
        os.unlink(tmp)

    def say(self, text):
        lang = "te" if TELUGU.search(text) and "te" in self.voices else "en"
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            with wave.open(path, "wb") as w:
                self.voices[lang].synthesize_wav(text, w)
            robotize(path, getattr(config, "ROBOT_VOICE", "off"))
            self._play(path)
        finally:
            os.unlink(path)
