#!/bin/bash
# Chitti robot - restore the Wi-Fi connection from the Raspberry Pi Imager settings on the boot partition
# (/boot/firmware/network-config), e.g. after a power cut left the saved connection files empty.
# Also turns off Wi-Fi power saving (a common cause of the Pi's Wi-Fi dropping out).
# The Wi-Fi password is read straight from that file and never printed.
# Run on the Pi:  sudo bash ~/chitti/fix-wifi.sh
set -euo pipefail

if [ "$(hostname)" != "chitti" ] && [ "$(hostname)" != "chitti-pi" ]; then
  echo "This is not the Chitti card (hostname is $(hostname)). Stopping." >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo bash $0" >&2
  exit 1
fi

# 1. remove the empty (corrupted) netplan files left by the power cut
for f in /etc/netplan/*.yaml; do
  [ -f "$f" ] && [ ! -s "$f" ] && { echo "Removing empty $f"; rm -f "$f"; }
done

# 2. recreate the Wi-Fi connection from the Imager settings
python3 - <<'EOF'
import subprocess, yaml
cfg = yaml.safe_load(open("/boot/firmware/network-config"))
aps = cfg["network"]["wifis"]["wlan0"]["access-points"]
ssid, ap = next(iter(aps.items()))
pw = (ap or {}).get("password")
subprocess.run(["nmcli", "connection", "delete", "chitti-wifi"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
cmd = ["nmcli", "connection", "add", "type", "wifi", "ifname", "wlan0", "con-name", "chitti-wifi",
       "ssid", ssid, "connection.autoconnect", "yes", "802-11-wireless.powersave", "2"]
if pw:
    cmd += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", pw]
subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
print(f"Wi-Fi connection 'chitti-wifi' created for network '{ssid}'")
EOF

# 3. Wi-Fi power saving off for good
cat > /etc/NetworkManager/conf.d/chitti-wifi-powersave.conf <<'EOF'
[connection]
wifi.powersave = 2
EOF
sync
nmcli general reload conf || true
nmcli connection up chitti-wifi || true
sleep 3
nmcli -t -f DEVICE,STATE,CONNECTION device | grep wlan0
ip -4 addr show wlan0 | grep inet || echo "No Wi-Fi address yet - wait a few seconds and run: nmcli device"
sync
echo "Done."
