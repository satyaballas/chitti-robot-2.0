#!/bin/bash
# Chitti robot — let Chitti shut down / restart the Pi by voice.
# Adds a sudo rule so user "pi" may run ONLY "shutdown -h now" and "shutdown -r now" without a password.
# Run on the Pi:  sudo bash ~/setup-power.sh
set -euo pipefail

if [ "$(hostname)" != "chitti" ] && [ "$(hostname)" != "chitti-pi" ]; then
  echo "This is not the Chitti card (hostname is $(hostname)). Stopping." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo bash $0" >&2
  exit 1
fi

RULE=/etc/sudoers.d/chitti-power
TMP=$(mktemp)
cat > "$TMP" <<'EOF'
# Chitti robot: voice shutdown / restart (only these two exact commands)
pi ALL=(root) NOPASSWD: /usr/sbin/shutdown -h now, /usr/sbin/shutdown -r now
EOF
# check the rule before installing it, so a mistake can never break sudo
visudo -cf "$TMP"
install -m 440 -o root -g root "$TMP" "$RULE"
rm -f "$TMP"
echo "Installed $RULE"
sudo -l -U pi | grep shutdown
if systemctl is-enabled --quiet chitti 2>/dev/null; then
  systemctl restart chitti && echo "Restarted chitti to load the new code"
fi
echo
echo "Done. Say \"Hey Jarvis, please shut down\", then \"yes\" after the beep."
