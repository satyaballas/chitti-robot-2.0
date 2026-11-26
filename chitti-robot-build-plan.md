# Chitti Robot — Build Plan & Decisions

AI desk robot built from a toy robot + Raspberry Pi 4 (4GB). Summary of decisions so far.

## Hardware
- **Toy robot:** Silverlit (2024) — likely YCOO "Program A Bot X". ~40cm, wheels under the feet (glide forward/back/sideways), **infrared remote**, IR gesture sensors on the chest.
- **Brain:** Raspberry Pi 4, 4GB (Model B Rev 1.2). Shared with another project: Chitti runs from its **own SD card** (64GB, Raspberry Pi OS Lite 64-bit, Debian 13 Trixie, hostname `chitti-pi`, user `pi`, SSH key-only), and the cards are swapped to switch. The other project's card is never modified.
- **Helper:** Arduino Nano (connected to Pi over USB serial).
- **Power:** Portronics POR 2688 power bank (10,000mAh / 37Wh, 5V 3A on USB-A and USB-C).

## 1. Movement — emulate the IR remote (no opening the robot)
- Parts (ordered): IR receiver (VS1838B / KY-022) + IR transmitter (KY-005 or 940nm IR LED + 2N2222 + resistors).
- Wiring: receiver OUT → GPIO17 (pin 11), 3.3V, GND. Transmitter signal → **GPIO23 (pin 16)**. (Moved off GPIO18 because the MAX98357A I2S amp needs GPIO18/19/21.)
- `/boot/firmware/config.txt` (done on the Chitti card):
  ```
  dtoverlay=gpio-ir,gpio_pin=17
  dtoverlay=gpio-ir-tx,gpio_pin=23
  ```
- Done on the Chitti card (2026-11-23): `v4l-utils` installed. **lirc numbering is not fixed.** On 2026-11-26, `/dev/lirc0` was the receiver and `/dev/lirc1` the transmitter, so `app/robot.py`, `ir/record.sh` and `ir/send.sh` find each device by its features. Full wiring + steps: `docs/wiring.md`. Python env at `~/chitti/venv` (Python 3.13). Root setup script: `pi/setup-system.sh` (sudo needs the Pi password, so it's run by hand).
- **Remote decoded (2026-11-26):** standard NEC, address 0x00, so the Pi sends scancodes (`ir-ctl -S nec:0x00CC`) instead of raw replays. Codes are in `app/robot.py` (`BUTTONS`). Test: `python robot.py send <button> [times]`. Raw capture: `pi/ir/remote-capture-2026-11-26.log`.

  | Button (remote photo held sideways) | NEC cmd | Robot does (tested) | Chitti direction |
  |---|---|---|---|
  | glide cluster top | 0x47 | forward, long | **forward** |
  | glide cluster bottom | 0x44 | back, long | **back** |
  | glide cluster left | 0x1C | forward, short | — |
  | glide cluster right | 0x08 | back, short | — |
  | glide cluster centre | 0x16 | dance | `dance` |
  | walk cluster top | 0x46 | walks forward | — |
  | walk cluster bottom | 0x15 | walks backward | — |
  | walk cluster right | 0x45 | turns right | **right** |
  | walk cluster left | 0x5E | turns left (slowly, needs ~3 s) | **left** |
  | walk cluster centre | 0x09 | PROGRAM (not sent) | — |
- Wiring lessons: GND/VCC/OUT mix-up made a receiver hot and reset the Pi. Count pins from the top (purple wire = pin 1) in the left column for odd pins. The receiver OUT idles high, so "GPIO17 held high" doesn't mean a short.
- Record raw (old method): `ir-ctl -d <receiver> -r -1 > forward.txt`
- Replay: `ir-ctl -d /dev/lirc0 --send=forward.txt`
- Notes: Silverlit uses a proprietary code, so use raw record/replay. Keep the remote's channel switch fixed while recording. Record all buttons (fwd, back, left, right, slide L/R, stop, dance). Toy may need repeated sends while "held".
- **Teardown (2026-11-23):** the robot's IR receiver is a 3-pin part on the edge of the head's LED board ("HJ-RC…08R-LED", connector CN3), behind the visor — not on the chest. Mount the KY-005 LED inside the head, 1–2cm from it. The head board also carries the two 3×3 LED eye grids. Main board + motor driver sit in the back; the robot's own speaker is in the other body half.
- **Parts on hand:** USB mini microphone, KY-005 IR transmitter, loose 3-pin IR receiver (VS1838B-type), 1.28" round TFT (GC9A01, 240×240, SPI), jumper wires. Not yet: MAX98357A amp, WS2812B LEDs.
- *(Old note, superseded by the teardown)* **Mounting:** robot's IR receiver is on the chest — three dots under the hand icon; middle dot is most likely the receiver (confirm by covering it with a finger). Mount the IR LED 1–2cm away, angled at the middle dot (e.g. under the chest shelf). Don't put anything flat in front of the three dots (reflections trigger gestures). Use low LED power at close range (470Ω–1kΩ).
- Pi rides on the robot, so line-of-sight stays fixed.

## 2. AI pipeline (built 2026-11-24; `move()` mocked until IR works)
Code: `pi/app/` → `~/chitti/app/` on the Pi. Run: `~/chitti/venv/bin/python ~/chitti/app/chitti.py` (`--type` to type instead of speak, `--no-boot` to skip the logo). Settings in `app/config.py`; API key in `~/chitti/.env` (`ANTHROPIC_API_KEY=...`, chmod 600, typed by the user).
1. Wake word — **"Hey Chitti"** (2026-11-26): sherpa-onnx open-vocabulary keyword spotter (`sherpa-onnx-kws-zipformer-gigaspeech-3.3M`, int8), no training. Phrases are word-piece spellings in `config.KWS_PHRASES` (several spellings of Chitti + "Hey Jarvis" as a backup); threshold 0.08, boost 2.5. PC test with Windows voices: 6/6 caught, 0 false wakes on "hey kitty", "hey siri", "city". Install: `bash setup-wake-word.sh`. New phrases: `tools/wake_tokens.py`. Old engine (openWakeWord "Hey Jarvis") remains as fallback via `WAKE_ENGINE`.
2. Listening — USB mic at 48 kHz → 16 kHz, webrtcvad stops recording after 0.9 s of silence. Mic capture volume was 0% — set to 75% with `amixer -c 3 sset Mic 75% cap`.
3. Speech-to-text — faster-whisper offline, `tiny.en` + name hint ("Chitti"): 2.8 s for a 3 s sentence. `base` 5 s; language detection +3.7 s. **Offline Telugu doesn't work** (base: 110 s, nonsense) → listening is English for now; Telugu needs cloud speech-to-text.
4. Brain — Claude (`claude-opus-5-5`, effort low) via the Messages API with tools `move`, `dance`, `show_expression`; server-side refusal fallback on. Conversation resets after 5 min idle. 
5. Voice — Piper offline: `en_US-ryan-medium`, `te_IN-venkatesh-medium` (Telugu voice works; ~1 s to make 3 s of speech). Plays on the 3.5mm jack until the MAX98357A arrives.
6. Eyes — `app/face.py` runs the boot screen, then idle / listening (wide) / thinking (darting) / speaking (bounce) / error (sad).

Decided: Claude, built-in wake word first. **Listening is English only for now** (2026-11-24); Chitti can still speak Telugu.

**Working end to end (2026-11-24)** with the Jabra EVOLVE 20 USB headset (mic + earphones): "Can you dance?" → understood in 2.6 s → Claude 4.5 s (called `dance`) → spoken reply. ~5–7 s from end of speech to reply. With the small USB desk mic it also worked, but it's quiet (needs 100% + 3× software gain) and picks up more room noise.
- Debug: `chitti.py --debug` prints mic level / room noise / wake score every 2 s and saves each recording to `/tmp/chitti-last.wav`.
- Tuning done: wake threshold 0.30 ("Hey Jarvis" scores only 0.25–0.40 for this voice — a custom "Hey Chitti" model trained on our voice will fix this); speech must be 3× louder than the room for 0.2 s before recording counts (stopped noise ending recordings early); beep when listening starts (eyes are hard to see through the visor).
- **Starts at boot** (2026-11-24): `chitti.service` (installed by `sudo bash ~/setup-chitti-service.sh`, which also saves mixer levels with `alsactl store`). Verified after a reboot: service starts at 9.6 s, listening at ~39 s; restarts itself if it crashes. Log: `journalctl -u chitti -f`. Stop it before running `chitti.py`/`eyes.py` by hand.
- **Audio profiles** (`AUDIO_PROFILES` in config): uses the Jabra headset if plugged in, else the USB desk mic + 3.5mm jack; with no mic it shows sleepy eyes and waits; if the mic is unplugged it goes back to waiting.
- **Follow-up listening:** if Chitti's reply ends with a question, it beeps and listens again without the wake word.
- **Voice shutdown/restart:** "Hey Jarvis, shut down" → Chitti asks to confirm → "yes" → goodbye → safe power-off. Uses the `power` tool and a narrow sudo rule (`/etc/sudoers.d/chitti-power`, only `shutdown -h now` / `-r now`) installed by `sudo bash ~/setup-power.sh`.
- **Idle life** (`app/face.py`): calm (0–10 s) → playful (a little animation every 4–8 s: look around, glance up, yawn, suspicious squint, happy, eye roll, wink, hearts, humming with music notes, sparkle, star eyes, sweat drop) → drowsy at 2 min (heavy lids, nodding off) → asleep at 5 min (closed-eye curves that glow with slow breathing, floating Zzz, ~4 fps to keep the CPU cool). At night (22:00–06:00) drowsy at 30 s, asleep at 2 min. Waking from sleep → startled "!"; heard nothing → confused look + "?".
- **Emojis** (`display/emoji.py`, original designs): zzz, question, exclaim, music, hearts, sparkle, sweat, tears, anger (overlays) and star_eyes, dizzy (replace the eyes). Claude can show them with the `show_emoji` tool; new expressions `confused` and `suspicious`. Previews: `display/idle-preview.png`, `display/emoji-preview.png`.
- Runs warm: ~71–72°C with the eyes animating and the wake word always listening (throttling starts at 80°C) — keep the fan, and watch it once inside the robot.
- Next: test "Hey Chitti" with real voices on the Pi and tune KWS_THRESHOLD; faster replies (stream Claude's answer and start speaking at the first sentence).

## 3. Audio
- Mic: mini USB microphone (₹300–500).
- Speaker: MAX98357A I2S amp + 3W 4Ω 40–50mm speaker. Wiring: BCLK → GPIO18 (pin 12), LRC → GPIO19 (pin 35), DIN → GPIO21 (pin 40), VIN → 5V, GND. (Alt: USB speakerphone.) Avoid ReSpeaker HATs.
- Mute mic while robot speaks (echo).

- **Bluetooth speaker (2026-11-26):** pTron BT Speaker paired via BlueALSA (`sudo bash setup-bluetooth.sh`, then `bluetoothctl` pair/trust/connect). `~/.asoundrc` defines `chitti_bt` (see `pi/asoundrc-bluetooth`). Chitti speaks through it whenever it's connected (checked every 5 s), falls back to the wired speaker otherwise, and tries to reconnect every 60 s. 0.25 s of silence is added at the start so the speaker doesn't swallow the first word.

## 4. Power
- Power bank USB-A → short, thick USB-A-to-C cable (≤30cm, 3A). Avoid C-to-C (early Pi 4 quirk).
- Expected runtime ~5–6 h.
- Checks: `vcgencmd get_throttled` → `0x0`; confirm bank doesn't auto-off at idle.
- Mount flat and low on the robot's back for balance.
- Future upgrade: UPS HAT with 18650 cells (battery level readable). Alternative if too heavy: Pi on desk + ESP32 on robot for IR.

## 5. Arduino Nano — mood lights (chosen)
- WS2812B ring (12/16 LEDs) or two 7-LED Jewels as eyes, behind the black visor.
- Data → D6 via 330Ω; 1000µF cap across 5V/GND; brightness ~30%.
- States: idle = soft blue breathing; wake = white flash; listening = blue pulse; thinking = cyan/purple spinner; speaking = green, reacts to voice; moving = orange sweep in travel direction; error = red blink.
- Open choice: ring vs two eyes; colour tweaks.
- Other possible Nano jobs later: desk-edge sensors (TCRT5000), head servo, light/touch sensors.

## 6. Round display eye (GC9A01 1.28" 240×240, SPI)
- Wiring: VCC → 3.3V (pin 1), GND → pin 14 (any GND pin works), SCL → GPIO11 (pin 23), SDA → GPIO10 (pin 19), CS → GPIO8 (pin 24), DC → GPIO25 (pin 22), RST → GPIO27 (pin 13), BLK → GPIO22 (pin 15, optional).
- Setup: `pi/setup-display.sh` (run with sudo: enables SPI, installs lgpio/spidev/Pillow/numpy). Code: `pi/display/gc9a01.py` (driver), `pi/display/eyes.py` (expressions: neutral, happy, sad, angry, surprised, sleepy, thinking, look_left/right, love; auto-blink). Preview: `pi/display/expressions-preview.png`.
- Tested on the Pi 2026-11-24: colours correct (BGR default), all expressions run at ~15–24 fps, no power warnings. Wire it in two stages with the Pi off (power pins first, then signals) — a mis-placed signal wire earlier knocked the Pi off Wi-Fi / stopped it booting.
- **Two eyes (2026-11-24):** `eyes.py` now draws two eyes side by side on the one screen (each ~100 px across; lids mirrored so angry/sad slant the right way). `--single` brings back the one big eye. Colours made brighter for the visor.
- **Boot screen:** `display/boot_screen.py` runs as the `chitti-display` service (`pi/chitti-display.service`, installed by `sudo bash ~/setup-boot-screen.sh`): CHITTI logo + spinning ring + "Connecting Wi-Fi" → "Hello!" card with IP, temperature and power status → eyes wake up → idle blinking/glancing. On shutdown: eyes close, "Bye!", screen blanks. Appears a few seconds after power-on (nothing can draw on SPI before Linux starts). The AI program will later take over the display from this service.
- **Brightness:** with BLK unconnected the backlight is already at 100%; software can only use brighter colours. Options: mount the screen pressed against the visor, cut a window in the visor behind the eyes (or sand/thin it there), or use the WS2812B LEDs (much brighter) for glow. A brighter round AMOLED is possible but needs a different (QSPI) driver.

## 7. Backup (required once the build is done)
- **Full SD card image** of the Chitti card when the build is finished, and again after big milestones.
  1. `sudo shutdown -h now`, wait for the green LED to stop, take the card out.
  2. On the PC, read the whole card to a compressed image with **USBImager** (free, can write `.img.zst`/`.img.gz`) or Win32 Disk Imager ("Read"). The 64GB card holds ~6GB of data, so a compressed image is a few GB.
  3. Store the image off the card (PC + one more place, e.g. external drive or cloud). Name it with the date, e.g. `chitti-2026-11-24.img.gz`.
  4. Restore = write the image back to a card with Raspberry Pi Imager ("Use custom") or USBImager.
- The code in `pi/` (this repo) is the lightweight backup between images (the API key in `~/chitti/.env` is not copied there — keep it in the Anthropic console / a password manager).
- The other project's SD card is separate and is never touched by this.

**Backups taken**
| Date | File | Size | Contents | Verified |
|---|---|---|---|---|
| 2026-11-26 | `chitti-2026-11-26.img.zst`, kept off-repo in two places | 2.7 GB compressed / 58.24 GiB raw | Voice pipeline (Jabra), boot service, voice shutdown, idle life + emojis | Fully decompressed, size = whole card; SHA-256 of raw image `0ef390b1…b666e186` (full hash in the README beside it) |

## Future ideas
- Round display behind the visor for animated eyes; Pi Camera for face tracking.
