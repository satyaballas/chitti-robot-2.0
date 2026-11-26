#!/bin/bash
# Chitti robot — enable SPI and install display libraries for the GC9A01 round TFT.
# Run on the Pi:  sudo bash ~/setup-display.sh
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

echo "== 1/3 Python display libraries =="
apt-get update -q
apt-get -y -q install python3-lgpio python3-spidev python3-pil python3-numpy

echo "== 2/3 Enable SPI =="
CFG=/boot/firmware/config.txt
cp -n "$CFG" "$CFG.before-display"
if grep -q "^dtparam=spi=on" "$CFG"; then
  echo "SPI already enabled"
elif grep -q "^#dtparam=spi=on" "$CFG"; then
  sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' "$CFG"
  echo "SPI enabled (uncommented)"
else
  printf '\n# Chitti robot: SPI for the GC9A01 round display\ndtparam=spi=on\n' >> "$CFG"
  echo "SPI enabled (added)"
fi

echo "== 3/3 Let the Chitti venv see these libraries =="
VENVCFG=/home/pi/chitti/venv/pyvenv.cfg
if [ -f "$VENVCFG" ]; then
  sed -i 's/^include-system-site-packages = false/include-system-site-packages = true/' "$VENVCFG"
fi
usermod -aG spi,gpio pi

echo
echo "Done. Rebooting in 5 seconds..."
sleep 5
reboot
