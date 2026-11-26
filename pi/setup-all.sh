#!/bin/bash
# Chitti robot — run all one-time root setup in one go (system packages + IR, then display/SPI).
# Run on the Pi:  sudo bash ~/setup-all.sh
set -euo pipefail
cd "$(dirname "$0")"
SKIP_REBOOT=1 bash ./setup-system.sh
bash ./setup-display.sh   # reboots at the end
