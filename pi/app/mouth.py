"""Chitti's voice: offline text-to-speech with Piper, played on the speaker."""
import os
import re
import subprocess
import tempfile
import wave

import config

TELUGU = re.compile(r"[ఀ-౿]")


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
            subprocess.run(["aplay", "-q", "-D", config.SPEAKER_DEVICE, path], check=False)
        finally:
            os.unlink(path)
