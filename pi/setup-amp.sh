#!/bin/bash
# Chitti robot - enable the MAX98357A I2S amplifier (BCLK GPIO18, LRC GPIO19, DIN GPIO21).
# Optional: amp SD pin wired to GPIO4 (Pi pin 7) lets Linux switch the amp off when nothing is playing,
# which removes the idle hiss/static. Pass "sd" to use it:
#   sudo bash ~/chitti/setup-amp.sh        # amp always on
#   sudo bash ~/chitti/setup-amp.sh sd     # amp off when silent (SD -> pin 7)
# Needs a reboot afterwards.
set -euo pipefail

if [ "$(hostname)" != "chitti" ] && [ "$(hostname)" != "chitti-pi" ]; then
  echo "This is not the Chitti card (hostname is $(hostname)). Stopping." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo bash $0 [sd]" >&2
  exit 1
fi

CFG=/boot/firmware/config.txt
LINE="dtoverlay=max98357a"
[ "${1:-}" = "sd" ] && LINE="dtoverlay=max98357a,sdmode-pin=4"
cp "$CFG" "$CFG.before-amp"
if grep -q "^dtoverlay=max98357a" "$CFG"; then
  sed -i "s/^dtoverlay=max98357a.*/$LINE/" "$CFG"
else
  printf '\n# Chitti: MAX98357A I2S speaker amplifier (GPIO18/19/21)\n%s\n' "$LINE" >> "$CFG"
fi
grep -n "max98357a" "$CFG"
sync
echo "Done (backup: $CFG.before-amp). Reboot now:  sudo reboot"
