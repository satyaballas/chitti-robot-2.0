#!/bin/bash
# Record the robot's IR remote, one button at a time, into ~/chitti/ir/<name>.txt
#   bash ~/chitti/ir/record.sh              # all buttons
#   bash ~/chitti/ir/record.sh forward      # just one (to redo it)
# Stop the robot service first so nothing else uses IR:  sudo systemctl stop chitti
set -u
DIR=~/chitti/ir
BUTTONS=("$@")
[ ${#BUTTONS[@]} -eq 0 ] && BUTTONS=(forward back left right slide_left slide_right stop dance)

RX=""
for d in /dev/lirc*; do
  ir-ctl -d "$d" --features 2>/dev/null | grep -q "can receive raw IR" && RX=$d && break
done
[ -z "$RX" ] && { echo "No IR receiver found (check the wiring and dtoverlay=gpio-ir,gpio_pin=17)"; exit 1; }
echo "Receiver: $RX.  Hold the remote 5-10 cm from the receiver, pointing at it."
mkdir -p "$DIR"

for b in "${BUTTONS[@]}"; do
  while true; do
    read -rp $'\n'"Press Enter, then tap '$b' on the remote ONCE (8 s): " _
    timeout 8 ir-ctl -d "$RX" -r -1 > "$DIR/$b.txt" 2>/dev/null
    n=$(grep -oE '[+-][0-9]+' "$DIR/$b.txt" | wc -l)
    if [ "$n" -ge 10 ]; then
      echo "  saved $b.txt ($n pulses)"
      break
    fi
    echo "  got nothing useful ($n pulses) - try again (closer, fresh batteries, channel switch unchanged)"
  done
done
echo -e "\nDone. Test one with:  bash ~/chitti/ir/send.sh forward"
