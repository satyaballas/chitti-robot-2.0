"""Chitti — main loop: wake word -> listen -> understand -> think (Claude) -> speak, with the eyes reacting.

Run on the Pi:   ~/chitti/venv/bin/python ~/chitti/app/chitti.py
Options:         --no-boot   skip the boot logo     --type   type instead of speaking (for testing)
Needs:           ~/chitti/.env containing  ANTHROPIC_API_KEY=...
"""
import argparse
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anthropic  # noqa: E402

import config  # noqa: E402
from face import Face  # noqa: E402


def load_env():
    path = os.path.join(config.HOME, ".env")
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-boot", action="store_true", help="skip the boot logo")
    ap.add_argument("--type", action="store_true", help="type messages instead of speaking")
    ap.add_argument("--debug", action="store_true", help="show mic levels / wake scores, save recordings")
    args = ap.parse_args()

    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("No API key: put ANTHROPIC_API_KEY=... in ~/chitti/.env")

    def on_term(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, on_term)
    face = Face(boot_screen=not args.no_boot)

    from brain import Brain
    from mouth import Mouth
    brain, mouth = Brain(face), Mouth()
    ears = None

    def connect_ears(old=None):
        """Wait until a mic from AUDIO_PROFILES is plugged in, then start listening on it."""
        from ears import Ears, find_audio_profile
        if old:
            old.stop()
        waiting = False
        while (profile := find_audio_profile()) is None:
            if not waiting:
                print("No microphone found - plug in the headset or USB mic. Waiting...")
                face.mode("waiting")
                waiting = True
            time.sleep(3)
        print(f"Audio: {profile['name']}")
        new = Ears()
        new.debug = args.debug
        new.on_level = face.hear        # voice bars on the screen while listening
        if old:   # keep the already-loaded models
            new._whisper, new._wake, new.noise = old._whisper, old._wake, old.noise
            new._kws, new.wake_name = old._kws, old.wake_name
        else:
            print("Loading speech models...")
            new._load_wake()
            new.transcribe(__import__("numpy").zeros(16000, dtype="float32"))  # warm up Whisper
        new.start()
        return new

    if not args.type:
        ears = connect_ears()

    def speak(text):
        if not text:
            return
        print(f"Chitti: {text}")
        face.mode("speaking")
        if ears:
            ears.muted = True       # don't hear ourselves
        mouth.say(text)
        if ears:
            time.sleep(0.2)
            ears.muted = False

    follow_up = False   # True after Chitti asks a question: listen again without the wake word
    try:
        while True:
            face.mode("idle")
            if args.type:
                text, lang = input("\nYou: ").strip(), "en"
                if not text:
                    continue
            else:
                from ears import MicLost
                try:
                    if follow_up:
                        print("\n(listening for your answer)")
                    else:
                        print(f"\nWaiting for the wake word ({ears.wake_name})...")
                        ears.wait_for_wake_word()
                    follow_up = False
                    face.mode("listening")
                    if config.BEEP:
                        ears.muted = True
                        mouth.beep()
                        ears.muted = False
                    print("Listening...")
                    audio = ears.record()
                except MicLost as e:
                    print(f"Microphone lost: {e}")
                    ears = connect_ears(ears)
                    continue
                if audio is None:
                    print("(heard nothing)")
                    face.react("confused")
                    time.sleep(1.6)
                    continue
                face.mode("thinking")
                t0 = time.monotonic()
                text, lang = ears.transcribe(audio)
                print(f"You ({lang}, {time.monotonic() - t0:.1f}s): {text}")
                if not text:
                    face.react("confused")
                    time.sleep(1.6)
                    continue

            face.mode("thinking")
            t0 = time.monotonic()
            try:
                answer = brain.reply(text)
            except anthropic.AuthenticationError:
                face.mode("error")
                answer = "My API key is missing or wrong. Please check the dot env file."
            except anthropic.APIConnectionError:
                face.mode("error")
                answer = "I can't reach the internet right now."
            except anthropic.RateLimitError:
                face.mode("error")
                answer = "I'm being asked too much right now. Give me a moment."
            except anthropic.APIStatusError as e:
                face.mode("error")
                print(f"[brain] API error {e.status_code}: {e.message}")
                answer = "Something went wrong in my brain. Please try again."
            print(f"  (thought for {time.monotonic() - t0:.1f}s)")
            speak(answer)
            follow_up = answer.rstrip().endswith("?")

            if brain.power_request:
                action, brain.power_request = brain.power_request, None
                print(f"Power: {action}")
                import robot
                if robot.power(action):
                    face.mode("waiting")     # sleepy eyes; the system now stops this service ("Bye!")
                    time.sleep(30)
                else:
                    speak("I can't do that yet. My shutdown permission isn't set up on the Pi.")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        face.close()


if __name__ == "__main__":
    main()
