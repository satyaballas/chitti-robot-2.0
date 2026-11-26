#!/bin/bash
# Chitti robot — one-time system setup for the Chitti SD card.
# Run on the Pi:  sudo bash ~/setup-system.sh
set -euo pipefail

if [ "$(hostname)" != "chitti" ] && [ "$(hostname)" != "chitti-pi" ]; then
  echo "This is not the Chitti card (hostname is $(hostname)). Stopping." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo bash $0" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "== 1/3 System updates =="
apt-get update -q
apt-get -y -q -o Dpkg::Options::=--force-confold full-upgrade

echo "== 2/3 Packages: Python, audio, IR =="
apt-get -y -q install \
  git python3-venv python3-pip python3-dev build-essential \
  v4l-utils \
  alsa-utils libportaudio2 portaudio19-dev ffmpeg \
  libopenblas0

echo "== 3/3 IR overlays in /boot/firmware/config.txt =="
CFG=/boot/firmware/config.txt
cp -n "$CFG" "$CFG.before-chitti"
if ! grep -q "^dtoverlay=gpio-ir," "$CFG"; then
  cat >> "$CFG" <<'EOF'

# Chitti robot: IR receiver on GPIO17 (pin 11), IR transmitter on GPIO23 (pin 16)
dtoverlay=gpio-ir,gpio_pin=17
dtoverlay=gpio-ir-tx,gpio_pin=23
EOF
  echo "IR overlays added (backup: $CFG.before-chitti)"
else
  echo "IR overlays already present"
fi

usermod -aG gpio,audio,video,dialout pi

echo
if [ "${SKIP_REBOOT:-0}" = "1" ]; then
  echo "Setup finished (reboot skipped)."
  exit 0
fi
echo "Setup finished. Rebooting in 5 seconds..."
sleep 5
reboot
