#!/bin/bash
# Replay a recorded button through the IR LED:  bash ~/chitti/ir/send.sh forward [times]
set -u
name=${1:?usage: send.sh <button> [times]}
times=${2:-5}
TX=""
for d in /dev/lirc*; do
  ir-ctl -d "$d" --features 2>/dev/null | grep -q "Device can send" && TX=$d && break
done
[ -z "$TX" ] && { echo "No IR transmitter found (check dtoverlay=gpio-ir-tx,gpio_pin=23)"; exit 1; }
f=~/chitti/ir/$name.txt
[ -f "$f" ] || { echo "No recording $f - run record.sh $name"; exit 1; }
echo "Sending $name x$times on $TX"
for _ in $(seq "$times"); do ir-ctl -d "$TX" --send="$f"; sleep 0.1; done
