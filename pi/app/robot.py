"""Chitti's body: drives the Silverlit robot by sending its own remote's infrared codes.

The remote (Silverlit 88071 "Program A Bot X") speaks standard NEC, address 0x00. Codes were
recorded on 2026-11-26 and are named by where the button sits on the remote:
  cluster "glide" (dance button in the middle) and cluster "walk" (PROGRAM button in the middle),
  top/right/bottom/left as seen in the photo of the remote held sideways.
MOVES maps Chitti's directions onto those buttons - fill it in after watching what each button does
(`python robot.py send glide_top 5`). Until a direction is mapped, move() pretends.

The IR transmitter is a KY-005 on GPIO23. /dev/lircN numbers swap between boots, so the
transmitter is found by asking each device whether it can send.

    python robot.py list
    python robot.py send <button> [times]
"""
import glob
import subprocess
import sys
import time

NEC_ADDRESS = 0x00
BUTTONS = {                      # button -> NEC command
    "dance":        0x16,        # glide cluster, centre
    "glide_top":    0x47,
    "glide_right":  0x08,
    "glide_bottom": 0x44,
    "glide_left":   0x1C,
    "program":      0x09,        # walk cluster, centre (records / plays up to 48 moves)
    "walk_top":     0x46,
    "walk_right":   0x45,
    "walk_bottom":  0x15,
    "walk_left":    0x5E,
}
# Chitti direction -> button. None = not worked out yet (move() pretends).
MOVES = {
    "forward": "glide_top", "back": "glide_bottom", "left": "walk_left", "right": "walk_right",
    "slide_left": None, "slide_right": None,
}
DIRECTIONS = list(MOVES)
REPEAT_GAP = 0.11                # NEC remotes repeat about every 110 ms while a button is held
_tx = None


def ir_device(send=True):
    """The /dev/lircN that can send (send=True) or receive (send=False)."""
    for dev in sorted(glob.glob("/dev/lirc*")):
        out = subprocess.run(["ir-ctl", "-d", dev, "--features"], capture_output=True, text=True).stdout
        if send and "Device can send" in out:
            return dev
        if not send and "Device can receive raw IR" in out:
            return dev
    return None


def send(button, times=1):
    """Send one remote button `times` times (several sends = holding the button down)."""
    global _tx
    _tx = _tx or ir_device(send=True)
    if not _tx:
        print("[robot] no IR transmitter found (check dtoverlay=gpio-ir-tx)")
        return False
    scancode = f"nec:0x{(NEC_ADDRESS << 8) | BUTTONS[button]:04x}"
    for i in range(times):
        subprocess.run(["ir-ctl", "-d", _tx, "-S", scancode], check=False)
        if i < times - 1:
            time.sleep(REPEAT_GAP)
    return True


def move(direction, seconds):
    seconds = max(0.2, min(float(seconds), 5.0))
    button = MOVES.get(direction)
    if not button:
        print(f"[robot] (mock) {direction} {seconds:.1f}s")
        return f"Pretended to move {direction} (that direction isn't set up yet)"
    send(button, times=max(1, round(seconds / (REPEAT_GAP + 0.07))))
    return f"Moved {direction} for {seconds:.1f}s"


def dance():
    return "Danced" if send("dance") else "Couldn't dance (IR transmitter not found)"


def power(action):
    """Shut down or restart the Pi. Needs the sudo rule from setup-power.sh (no password for these two)."""
    cmd = ["sudo", "-n", "/usr/sbin/shutdown", "-r" if action == "restart" else "-h", "now"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[robot] {action} failed: {r.stderr.strip()} (run: sudo bash ~/setup-power.sh)")
        return False
    return True


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "send" and sys.argv[2] in BUTTONS:
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        print(f"sending {sys.argv[2]} x{n} on {ir_device(True)}")
        send(sys.argv[2], n)
    else:
        print("buttons:", ", ".join(BUTTONS))
        print("usage: python robot.py send <button> [times]")
