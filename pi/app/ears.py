"""Chitti's ears: microphone, wake word, recording until you stop talking, and speech-to-text."""
import math
import queue
import time

import numpy as np
import sounddevice as sd
import webrtcvad
from scipy.signal import resample_poly

import config

RATE = 16000
CHUNK = 1280                     # 80 ms at 16 kHz (openWakeWord needs this size; fine for sherpa too)
VAD_FRAME = 480                  # 30 ms at 16 kHz (what webrtcvad expects)


class MicLost(Exception):
    pass


def find_audio_profile():
    """Return the first AUDIO_PROFILES entry whose mic is plugged in (and apply it to config), or None."""
    sd._terminate()          # re-scan devices so newly plugged ones show up
    sd._initialize()
    for p in config.AUDIO_PROFILES:
        try:
            sd.query_devices(p["mic"], "input")
        except ValueError:
            continue
        config.MIC_DEVICE, config.MIC_RATE, config.MIC_GAIN = p["mic"], p["rate"], p["gain"]
        config.SPEAKER_DEVICE = p["speaker"]
        return p
    return None


class Ears:
    def __init__(self):
        self.q = queue.Queue()
        g = math.gcd(RATE, config.MIC_RATE)
        self._up, self._down = RATE // g, config.MIC_RATE // g   # e.g. 44100 -> 16000 = x160 / 441
        self.stream = sd.InputStream(
            device=config.MIC_DEVICE, samplerate=config.MIC_RATE, channels=1, dtype="int16",
            blocksize=CHUNK * config.MIC_RATE // RATE, callback=self._on_audio)
        self.vad = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)
        self._wake = None
        self._kws = None
        self.wake_name = config.WAKE_NAME
        self._whisper = None
        self.muted = False
        self.on_level = None             # called with 0..1 mic loudness while recording (face voice bars)
        self.debug = False
        self.noise = 300.0               # room noise level (rms), updated while waiting for the wake word

    def _on_audio(self, data, frames, t, status):
        if not self.muted:
            self.q.put(data[:, 0].copy())

    def _chunks(self):
        """16 kHz int16 chunks of 80 ms."""
        while True:
            try:
                x = self.q.get(timeout=5)
            except queue.Empty:
                if self.muted:
                    continue
                raise MicLost("no sound from the microphone for 5 s (unplugged?)")
            y = resample_poly(x.astype(np.float32), self._up, self._down) * config.MIC_GAIN
            yield np.clip(y, -32768, 32767).astype(np.int16)

    def start(self):
        self.stream.start()

    def stop(self):
        try:
            self.stream.close()
        except Exception:
            pass

    def flush(self):
        while not self.q.empty():
            self.q.get_nowait()

    # ---- wake word -------------------------------------------------------------
    def _load_wake(self):
        """Load the wake-word engine(s): config.WAKE_ENGINE = "both" | "sherpa" | "openwakeword"."""
        import os
        eng = config.WAKE_ENGINE
        self._kws, self._wake, names = None, None, []
        if eng in ("both", "sherpa"):
            if os.path.isdir(config.KWS_MODEL):
                import sherpa_onnx
                kw_file = os.path.join(config.MODELS, "kws", "keywords.txt")
                with open(kw_file, "w", encoding="utf-8") as f:
                    for p in config.KWS_PHRASES:
                        f.write(f"{p} :{config.KWS_BOOST} #{config.KWS_THRESHOLD} @WAKE\n")
                m = config.KWS_MODEL
                self._kws = sherpa_onnx.KeywordSpotter(
                    tokens=f"{m}/tokens.txt",
                    encoder=f"{m}/encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
                    decoder=f"{m}/decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
                    joiner=f"{m}/joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
                    num_threads=1, keywords_file=kw_file, keywords_score=config.KWS_BOOST,
                    keywords_threshold=config.KWS_THRESHOLD, max_active_paths=4, provider="cpu")
                names.append(config.WAKE_NAME)
            else:
                print(f"[ears] keyword model not found at {config.KWS_MODEL}")
        if eng in ("both", "openwakeword") or self._kws is None:
            from openwakeword.model import Model
            self._wake = Model(wakeword_models=[config.WAKE_WORD], inference_framework="onnx")
            names.append(config.WAKE_WORD.replace("_", " ").title())
        self.wake_name = " or ".join(names)

    def wait_for_wake_word(self):
        """Block until a wake word is heard (from either engine)."""
        if self._wake is None and self._kws is None:
            self._load_wake()
        stream = self._kws.create_stream() if self._kws else None
        if self._wake:
            self._wake.reset()
        self.flush()
        best, levels, t_report = 0.0, [], time.monotonic()
        for chunk in self._chunks():
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            # track the quiet room level: falls quickly, rises slowly (so speech doesn't count as noise)
            self.noise = 0.7 * self.noise + 0.3 * rms if rms < self.noise else 0.995 * self.noise + 0.005 * rms
            if stream is not None:
                stream.accept_waveform(RATE, chunk.astype(np.float32) / 32768.0)
                while self._kws.is_ready(stream):
                    self._kws.decode_stream(stream)
                    if self._kws.get_result(stream):
                        if self.debug:
                            print("   [debug] woken by the keyword spotter")
                        return
            if self._wake:
                score = max(self._wake.predict(chunk).values())
                best = max(best, score)
                if score >= config.WAKE_THRESHOLD:
                    self._wake.reset()
                    if self.debug:
                        print(f"   [debug] woken by openWakeWord ({score:.2f})")
                    return
            if self.debug:
                levels.append(rms)
                self._recent = np.concatenate([getattr(self, "_recent", np.zeros(0, np.int16)), chunk])[-RATE * 30:]
                if time.monotonic() - t_report >= 2:
                    import wave
                    with wave.open("/tmp/chitti-wake.wav", "wb") as w:      # last 30 s, to test the wake word
                        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
                        w.writeframes(self._recent.tobytes())
                    print(f"   [debug] mic level avg {np.mean(levels):5.0f} max {np.max(levels):5.0f} "
                          f"room {self.noise:4.0f} | jarvis score {best:.2f} | listening for '{self.wake_name}'")
                    best, levels, t_report = 0.0, [], time.monotonic()

    # ---- record one sentence ----------------------------------------------------
    def record(self):
        """Record until the speaker stops. Returns 16 kHz float32 audio, or None if nobody spoke."""
        self.flush()
        frames, spoke, silent_for, speech_run = [], False, 0.0, 0.0
        loud = self.noise * config.SPEECH_LEVEL
        t0 = time.monotonic()
        buf = np.zeros(0, dtype=np.int16)
        for chunk in self._chunks():
            frames.append(chunk)
            if self.on_level:
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                self.on_level(min(1.0, max(0.0, (rms - self.noise) / max(1.0, 2 * loud - self.noise))))
            buf = np.concatenate([buf, chunk])
            while len(buf) >= VAD_FRAME:
                frame, buf = buf[:VAD_FRAME], buf[VAD_FRAME:]
                level = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
                is_speech = self.vad.is_speech(frame.tobytes(), RATE) and level > loud
                if is_speech:
                    speech_run += VAD_FRAME / RATE
                    silent_for = 0.0
                    if speech_run >= config.SPEECH_START:
                        spoke = True
                else:
                    speech_run = 0.0 if not spoke else speech_run
                    silent_for += VAD_FRAME / RATE
            elapsed = time.monotonic() - t0
            if not spoke and elapsed > config.LISTEN_TIMEOUT:
                return None
            if spoke and (silent_for >= config.END_SILENCE or elapsed > config.MAX_UTTERANCE):
                break
        audio = np.concatenate(frames)
        if self.debug:
            import wave
            with wave.open("/tmp/chitti-last.wav", "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(audio.tobytes())
            rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
            print(f"   [debug] recorded {len(audio) / RATE:.1f}s, level {rms:.0f}, peak {np.abs(audio).max()}, "
                  f"speech needed > {loud:.0f} -> /tmp/chitti-last.wav")
        return audio.astype(np.float32) / 32768.0

    # ---- speech to text -----------------------------------------------------------
    def transcribe(self, audio):
        """Returns (text, language)."""
        if self._whisper is None:
            import os
            os.environ.setdefault("HF_HUB_OFFLINE", "1")  # models are already downloaded; don't wait on the network
            from faster_whisper import WhisperModel
            self._whisper = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8",
                                         cpu_threads=4, download_root=f"{config.MODELS}/whisper")
        lang = config.LANGUAGES[0]
        english_only = config.WHISPER_MODEL.endswith(".en")
        if len(config.LANGUAGES) > 1 and not english_only:
            _, _, probs = self._whisper.detect_language(audio)
            allowed = [(p, l) for l, p in probs if l in config.LANGUAGES]
            if allowed:
                lang = max(allowed)[1]
        segments, _ = self._whisper.transcribe(
            audio, language=None if english_only else lang, beam_size=1, vad_filter=False,
            condition_on_previous_text=False, initial_prompt=config.WHISPER_HINT)
        return " ".join(s.text.strip() for s in segments).strip(), lang
