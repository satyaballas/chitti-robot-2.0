#!/bin/bash
# Chitti robot — start Chitti automatically at power-on (boot logo -> eyes -> voice assistant).
# Run on the Pi:  sudo bash ~/setup-chitti-service.sh
set -euo pipefail

if [ "$(hostname)" != "chitti" ] && [ "$(hostname)" != "chitti-pi" ]; then
  echo "This is not the Chitti card (hostname is $(hostname)). Stopping." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo bash $0" >&2
  exit 1
fi

echo "== 1/3 Save current mic/headset volumes so they survive a reboot =="
alsactl store && echo "saved"

echo "== 2/3 Install the chitti service =="
# the older boot-screen-only service is replaced by this one
if systemctl list-unit-files chitti-display.service >/dev/null 2>&1; then
  systemctl disable --now chitti-display.service 2>/dev/null || true
  rm -f /etc/systemd/system/chitti-display.service
fi
install -m 644 /home/pi/chitti.service /etc/systemd/system/chitti.service
systemctl daemon-reload
systemctl enable chitti.service

echo "== 3/3 Start it now =="
systemctl restart chitti.service
sleep 2
systemctl --no-pager --lines=0 status chitti.service | head -5
echo
echo "Chitti now starts at every power-on."
echo "  Live log:            journalctl -u chitti -f"
echo "  Stop / start:        sudo systemctl stop chitti   /   sudo systemctl start chitti"
echo "  Turn off auto-start: sudo systemctl disable --now chitti"
echo "  (Stop it before running chitti.py or eyes.py by hand.)"
