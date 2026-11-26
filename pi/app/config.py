"""Chitti settings. Change values here; the API key goes in ~/chitti/.env (never in this file)."""
import os

HOME = os.path.expanduser("~/chitti")
MODELS = os.path.join(HOME, "models")

# --- Claude (the brain) -------------------------------------------------------
CLAUDE_MODEL = "claude-opus-5-5"
CLAUDE_EFFORT = "low"          # low = fastest replies; raise to "medium" for harder questions
CLAUDE_MAX_TOKENS = 4000
CONVERSATION_RESET_SECONDS = 300   # start a fresh conversation after 5 min of silence
CONVERSATION_MAX_MESSAGES = 40     # ...or after this many messages

# --- Wake word ------------------------------------------------------------------
WAKE_WORD = "hey_jarvis"        # built-in openWakeWord model; a custom "hey_chitti" comes later
WAKE_THRESHOLD = 0.30           # 0..1, raise if it wakes up by itself, lower if it misses you
                                # (tested 2026-11-24: "Hey Jarvis" scores 0.25-0.40 for this voice; silence 0.00)

# --- Microphone -------------------------------------------------------------------
# Audio setups, in order of preference: Chitti uses the first one whose mic is plugged in
# (checked at start-up, and again whenever the mic disappears). mic = part of the name shown by `arecord -l`.
AUDIO_PROFILES = [
    dict(name="Jabra headset", mic="Jabra", rate=16000, gain=1.0, speaker="plughw:CARD=MS,DEV=0"),
    dict(name="USB desk mic + 3.5mm jack", mic="USB PnP Sound Device", rate=48000, gain=3.0,
         speaker="plughw:CARD=Headphones,DEV=0"),
]
# Filled in from the chosen profile at start-up:
MIC_DEVICE = "Jabra"
MIC_RATE = 16000                      # resampled to 16 kHz if different
LISTEN_TIMEOUT = 6.0                  # give up if you don't start talking within this many seconds
MAX_UTTERANCE = 15.0                  # stop recording after this many seconds
END_SILENCE = 0.9                     # stop recording after this much silence once you've spoken
VAD_AGGRESSIVENESS = 3                # 0..3, higher ignores more background noise
MIC_GAIN = 1.0                        # software boost (from the profile; the small USB mic needs 3.0)
SPEECH_START = 0.2                    # seconds of clear speech before it counts as "started talking"
SPEECH_LEVEL = 3.0                    # speech must be this many times louder than the room noise
BEEP = True                           # short beep when Chitti starts listening

# --- Speech to text (offline) -------------------------------------------------------
# Measured on the Pi 4 for a 3 s sentence: tiny.en 2.8 s, base.en / base 5 s, +3.7 s to detect the language.
# Offline Telugu does not work with these models (base took 110 s and produced nonsense), so listening is English.
WHISPER_MODEL = "tiny.en"       # tiny.en (fastest) | base.en (more accurate) | base (multilingual)
LANGUAGES = ["en"]              # languages Chitti listens for (detection only runs if more than one)
WHISPER_HINT = "Chitti, the robot."   # helps Whisper spell the robot's name

# --- Voice (offline Piper) -------------------------------------------------------------
VOICES = {                      # language -> Piper voice name (downloaded into models/piper)
    "en": "en_US-ryan-medium",          # others: en_US-lessac-medium, en_GB-alan-medium, en_US-amy-medium
    "te": "te_IN-venkatesh-medium",     # others: te_IN-maya-medium, te_IN-padmavathi-medium
}
SPEAKER_DEVICE = "plughw:CARD=MS,DEV=0"   # from the profile (3.5mm jack: "plughw:CARD=Headphones,DEV=0")
