#!/bin/bash
# Chitti robot - enable the MAX98357A I2S amplifier (BCLK GPIO18, LRC GPIO19, DIN GPIO21).
# Adds dtoverlay=max98357a to /boot/firmware/config.txt. Needs a reboot afterwards.
# Run on the Pi:  sudo bash ~/chitti/setup-amp.sh
set -euo pipefail

if [ "$(hostname)" != "chitti" ] && [ "$(hostname)" != "chitti-pi" ]; then
  echo "This is not the Chitti card (hostname is $(hostname)). Stopping." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo bash $0" >&2
  exit 1
fi

CFG=/boot/firmware/config.txt
if grep -q "^dtoverlay=max98357a" "$CFG"; then
  echo "MAX98357A overlay already enabled."
else
  cp "$CFG" "$CFG.before-amp"
  printf '\n# Chitti: MAX98357A I2S speaker amplifier (GPIO18/19/21)\ndtoverlay=max98357a\n' >> "$CFG"
  echo "Added dtoverlay=max98357a (backup: $CFG.before-amp)"
fi
sync
echo "Done. Reboot now:  sudo reboot"
