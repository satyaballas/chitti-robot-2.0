#!/bin/bash
# Chitti robot - allow SSH login with the pi user's password (e.g. from a phone app), in addition to keys.
# The card was set up key-only (cloud-init's 50-cloud-init.conf says "PasswordAuthentication no");
# a 10-... file is read first, so its setting wins. Undo: sudo rm /etc/ssh/sshd_config.d/10-chitti-password.conf
# Run on the Pi:  sudo bash ~/chitti/setup-ssh-password.sh
set -euo pipefail

if [ "$(hostname)" != "chitti" ] && [ "$(hostname)" != "chitti-pi" ]; then
  echo "This is not the Chitti card (hostname is $(hostname)). Stopping." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo bash $0" >&2
  exit 1
fi

CONF=/etc/ssh/sshd_config.d/10-chitti-password.conf
echo "PasswordAuthentication yes" > "$CONF"
chmod 644 "$CONF"
if sshd -t; then
  systemctl reload ssh || systemctl restart ssh
  sshd -T | grep -i "^passwordauthentication"
  echo "Done. Log in from the phone as user 'pi' with your Pi password (the one sudo asks for)."
else
  rm -f "$CONF"
  echo "SSH settings test failed - nothing changed." >&2
  exit 1
fi
