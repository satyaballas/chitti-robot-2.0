#!/bin/bash
# Chitti robot - Bluetooth speaker support.
# Installs BlueALSA (Bluetooth audio for plain ALSA, no desktop sound server needed), turns the
# Bluetooth radio on, and lets user "pi" pair devices. Pairing itself is done afterwards (no sudo).
# Run on the Pi:  sudo bash ~/chitti/setup-bluetooth.sh
set -euo pipefail

if [ "$(hostname)" != "chitti" ] && [ "$(hostname)" != "chitti-pi" ]; then
  echo "This is not the Chitti card (hostname is $(hostname)). Stopping." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo bash $0" >&2
  exit 1
fi

apt-get update -q
apt-get install -y -q bluez-alsa-utils rfkill
rfkill unblock bluetooth
usermod -aG bluetooth pi
systemctl enable --now bluetooth
systemctl enable --now bluealsa 2>/dev/null || systemctl enable --now bluez-alsa 2>/dev/null || true
sleep 2
bluetoothctl power on || true
echo
systemctl --no-pager --type=service | grep -iE "blue" || true
bluetoothctl show | grep -E "Powered|Name" || true
echo
echo "Done. Now put your Bluetooth speaker in pairing mode and tell Claude - it will pair it."
