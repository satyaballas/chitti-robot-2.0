"""Generates docs/wiring.svg - every connection to Chitti's Raspberry Pi 4.

    python tools/make_wiring_svg.py

Edit CONNECTIONS / DEVICES below and re-run; the SVG is drawn from this data.
"""
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "wiring.svg")

# ---- the Pi's 40-pin header -------------------------------------------------
PINS = {
    1: "3.3V", 2: "5V", 3: "GPIO2", 4: "5V", 5: "GPIO3", 6: "GND", 7: "GPIO4", 8: "GPIO14",
    9: "GND", 10: "GPIO15", 11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22",
    16: "GPIO23", 17: "3.3V", 18: "GPIO24", 19: "GPIO10", 20: "GND", 21: "GPIO9", 22: "GPIO25",
    23: "GPIO11", 24: "GPIO8", 25: "GND", 26: "GPIO7", 27: "ID_SD", 28: "ID_SC", 29: "GPIO5",
    30: "GND", 31: "GPIO6", 32: "GPIO12", 33: "GPIO13", 34: "GND", 35: "GPIO19", 36: "GPIO16",
    37: "GPIO26", 38: "GPIO20", 39: "GND", 40: "GPIO21",
}

COL = {  # wire colours
    "3v3": "#d62828", "5v": "#f77f00", "gnd": "#222222", "sclk": "#b8860b", "mosi": "#1d70b8",
    "cs": "#7b2cbf", "dc": "#2a9d8f", "rst": "#8d5524", "irrx": "#0096c7", "irtx": "#d63384",
    "i2s": "#6c757d",
}

W, H = 1500, 1130
HX_L, HX_R = 715, 775          # header pin columns (odd / even)
ROW0, DY = 200, 30
END_L, END_R = 612, 878        # where wires stop beside the pin labels


def pin_xy(p):
    row = (p - 1) // 2
    return (HX_L if p % 2 else HX_R), ROW0 + row * DY


# Devices: name, x, y, w, terminals (top to bottom), subtitle lines, dashed (planned)
DEVICES = {
    "tft": dict(x=50, y=110, w=250, title="1.28\" round TFT (GC9A01)", sub=["240x240, SPI - Chitti's eyes", "BLK: leave unconnected (backlight 100%)"],
                terms=["VCC", "GND", "SCL", "SDA", "RES", "DC", "CS", "BLK"], side="L"),
    "irrx": dict(x=50, y=560, w=250, title="IR receiver (VS1838B)", sub=["for RECORDING the remote", "dome facing you: OUT  GND  VCC"],
                 terms=["OUT", "GND", "VCC"], side="L"),
    "irtx": dict(x=1200, y=150, w=260, title="IR transmitter (KY-005)", sub=["sends to the robot", "LED 1-2 cm from robot's IR", "receiver (head board, CN3)", "middle pin: leave unconnected"],
                 terms=["S", "middle", "-"], side="R"),
    "amp": dict(x=1200, y=470, w=260, title="MAX98357A amp  (planned)", sub=["I2S audio -> 3W 4ohm speaker"],
                terms=["VIN", "GND", "BCLK", "LRC", "DIN"], side="R", dashed=True),
}
TERM_DY = 34

# (device, terminal, pin, colour, lane_x, extra)  lane_x: vertical routing column
CONNECTIONS = [
    ("tft", "VCC", 1, "3v3", 590, {}),
    ("tft", "GND", 14, "gnd", None, {"over": 92, "rlane": 900}),
    ("tft", "SCL", 23, "sclk", 470, {}),
    ("tft", "SDA", 19, "mosi", 490, {}),
    ("tft", "RES", 13, "rst", 530, {}),
    ("tft", "DC", 22, "dc", None, {"over": 80, "rlane": 920}),
    ("tft", "CS", 24, "cs", None, {"over": 68, "rlane": 940}),
    ("irrx", "OUT", 11, "irrx", 410, {}),
    ("irrx", "GND", 9, "gnd", 390, {}),
    ("irrx", "VCC", 17, "3v3", 370, {}),
    ("irtx", "S", 16, "irtx", 1060, {"resistor": True}),
    ("irtx", "-", 20, "gnd", 1080, {}),
    ("amp", "VIN", 2, "5v", 1140, {"dashed": True}),
    ("amp", "GND", 34, "gnd", 1150, {"dashed": True}),
    ("amp", "BCLK", 12, "i2s", 1120, {"dashed": True}),
    ("amp", "LRC", 35, "i2s", None, {"dashed": True, "under": 845, "llane": 595}),
    ("amp", "DIN", 40, "i2s", 1170, {"dashed": True}),
]
NOT_CONNECTED = [("tft", "BLK", "not connected = backlight always 100%"), ("irtx", "middle", "leave unconnected")]


def term_xy(dev, term):
    d = DEVICES[dev]
    i = d["terms"].index(term)
    y = d["y"] + 70 + 16 * max(0, len(d["sub"]) - 1) + i * TERM_DY
    x = d["x"] + d["w"] if d["side"] == "L" else d["x"]
    return x, y


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    o = []
    a = o.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      'font-family="Segoe UI, Helvetica, Arial, sans-serif">')
    a(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
    a('<text x="40" y="48" font-size="28" font-weight="700" fill="#111">Chitti - Raspberry Pi 4 wiring</text>')
    a('<text x="40" y="76" font-size="14" fill="#555">Header seen from above, USB ports at the bottom. '
      'Solid = connected now, dashed = planned. Wires that cross without a dot are not joined.</text>')
    a('<g transform="translate(0,50)">')

    # Pi + header
    a(f'<rect x="{HX_L - 160}" y="{ROW0 - 50}" width="{HX_R - HX_L + 320}" height="{19 * DY + 100}" rx="18" '
      'fill="#e8f5e9" stroke="#2e7d32" stroke-width="2"/>')
    a(f'<text x="{(HX_L + HX_R) / 2}" y="{ROW0 - 26}" font-size="15" font-weight="700" fill="#2e7d32" '
      'text-anchor="middle">Raspberry Pi 4 - 40-pin header</text>')
    a(f'<rect x="{HX_L - 18}" y="{ROW0 - 16}" width="{HX_R - HX_L + 36}" height="{19 * DY + 32}" rx="6" fill="#263238"/>')
    used = {c[2]: c[3] for c in CONNECTIONS}
    planned = {c[2] for c in CONNECTIONS if c[5].get("dashed")}
    for p, name in PINS.items():
        x, y = pin_xy(p)
        if p in used:
            fill = COL[used[p]]
        elif name == "GND":
            fill = "#555"
        elif name in ("3.3V", "5V"):
            fill = "#8a5a5a"
        else:
            fill = "#90a4ae"
        ring = ' stroke-dasharray="3 2"' if p in planned else ""
        a(f'<circle cx="{x}" cy="{y}" r="11" fill="{fill}" stroke="#fff" stroke-width="1.5"{ring}/>')
        a(f'<text x="{x}" y="{y + 4}" font-size="10" font-weight="700" fill="#fff" text-anchor="middle">{p}</text>')
        weight = "700" if p in used else "400"
        colr = "#111" if p in used else "#8a8a8a"
        if p % 2:
            a(f'<text x="{x - 22}" y="{y + 4}" font-size="12" font-weight="{weight}" fill="{colr}" text-anchor="end">{name}</text>')
        else:
            a(f'<text x="{x + 22}" y="{y + 4}" font-size="12" font-weight="{weight}" fill="{colr}">{name}</text>')

    # wires
    for dev, term, p, col, lane, ex in CONNECTIONS:
        tx, ty = term_xy(dev, term)
        px, py = pin_xy(p)
        end = END_L if p % 2 else END_R
        c = COL[col]
        dash = ' stroke-dasharray="9 6"' if ex.get("dashed") else ""
        if "over" in ex:            # left device -> right-hand pin, over the top of the header
            oy, rl = ex["over"], ex["rlane"]
            path = f"M{tx},{ty} H{340 + (92 - oy)} V{oy} H{rl} V{py} H{end}"
        elif "under" in ex:         # right device -> left-hand pin, under the header
            uy, ll = ex["under"], ex["llane"]
            path = f"M{tx},{ty} H{1160} V{uy} H{ll} V{py} H{end}"
        else:
            path = f"M{tx},{ty} H{lane} V{py} H{end}"
        a(f'<path d="{path}" fill="none" stroke="{c}" stroke-width="3.2" stroke-linejoin="round"{dash}/>')
        a(f'<circle cx="{end}" cy="{py}" r="4.5" fill="{c}"/>')
        a(f'<circle cx="{tx}" cy="{ty}" r="4.5" fill="{c}"/>')
        if ex.get("resistor"):      # series resistor drawn on the first horizontal run
            rx = tx - 28
            a(f'<rect x="{rx - 22}" y="{ty - 9}" width="44" height="18" fill="#fff" stroke="{c}" stroke-width="2.5"/>')
            a(f'<text x="{rx}" y="{ty - 14}" font-size="11" fill="#333" text-anchor="middle">220 ohm*</text>')

    # devices
    for key, d in DEVICES.items():
        h = 70 + 16 * max(0, len(d["sub"]) - 1) + len(d["terms"]) * TERM_DY - 10
        dash = ' stroke-dasharray="8 5"' if d.get("dashed") else ""
        a(f'<rect x="{d["x"]}" y="{d["y"]}" width="{d["w"]}" height="{h}" rx="10" fill="#f7f9fc" stroke="#37474f" stroke-width="2"{dash}/>')
        a(f'<text x="{d["x"] + 14}" y="{d["y"] + 26}" font-size="15" font-weight="700" fill="#111">{esc(d["title"])}</text>')
        for i, s in enumerate(d["sub"]):
            a(f'<text x="{d["x"] + 14}" y="{d["y"] + 46 + 16 * i}" font-size="11.5" fill="#555">{esc(s)}</text>')
        for t in d["terms"]:
            x, y = term_xy(key, t)
            if d["side"] == "L":
                a(f'<text x="{x - 12}" y="{y + 4}" font-size="13" font-weight="700" fill="#222" text-anchor="end">{t}</text>')
            else:
                a(f'<text x="{x + 12}" y="{y + 4}" font-size="13" font-weight="700" fill="#222">{t}</text>')
    for dev, term, note in NOT_CONNECTED:
        x, y = term_xy(dev, term)
        if DEVICES[dev]["side"] == "L":
            a(f'<line x1="{x}" y1="{y}" x2="{x + 22}" y2="{y}" stroke="#999" stroke-width="2"/>')
            a(f'<text x="{x + 20}" y="{y - 4}" font-size="15" fill="#999">x</text>')
        else:
            a(f'<line x1="{x - 22}" y1="{y}" x2="{x}" y2="{y}" stroke="#999" stroke-width="2"/>')
            a(f'<text x="{x - 30}" y="{y - 4}" font-size="15" fill="#999">x</text>')

    # ports along the bottom
    by = 900
    a(f'<text x="40" y="{by - 14}" font-size="16" font-weight="700" fill="#111">Plugged into the Pi\'s ports</text>')
    ports = [
        ("USB-C power", "Portronics power bank", "5V 3A, short USB-A to C cable", False),
        ("USB", "Jabra EVOLVE 20 headset", "mic + earphones (preferred)", False),
        ("USB", "USB desk mic", "used if no headset", False),
        ("3.5 mm jack", "Speaker / earphones", "used with the desk mic", False),
        ("USB", "Arduino Nano  (planned)", "WS2812B mood lights on D6", True),
    ]
    bw, gap = 268, 18
    for i, (port, name, note, planned_) in enumerate(ports):
        x = 40 + i * (bw + gap)
        dash = ' stroke-dasharray="8 5"' if planned_ else ""
        a(f'<rect x="{x}" y="{by}" width="{bw}" height="92" rx="10" fill="#f7f9fc" stroke="#37474f" stroke-width="2"{dash}/>')
        a(f'<rect x="{x}" y="{by}" width="{bw}" height="26" rx="10" fill="#37474f"/>')
        a(f'<rect x="{x}" y="{by + 14}" width="{bw}" height="12" fill="#37474f"/>')
        a(f'<text x="{x + 12}" y="{by + 18}" font-size="13" font-weight="700" fill="#fff">{esc(port)}</text>')
        a(f'<text x="{x + 12}" y="{by + 50}" font-size="14" font-weight="700" fill="#111">{esc(name)}</text>')
        a(f'<text x="{x + 12}" y="{by + 72}" font-size="12" fill="#555">{esc(note)}</text>')

    # notes
    notes = [
        "* 220 ohm in series only if your KY-005 board has no resistor on it (keeps GPIO current under ~10 mA).",
        "Wire with the Pi OFF: power + GND first, then signals. Check each pin number twice - a wrong pin once stopped the Pi booting.",
        "Pins: /boot/firmware/config.txt has dtoverlay=gpio-ir,gpio_pin=17 (receiver) and dtoverlay=gpio-ir-tx,gpio_pin=23 (transmitter).",
    ]
    for i, n in enumerate(notes):
        a(f'<text x="40" y="{by + 120 + i * 18}" font-size="12" fill="#444">{esc(n)}</text>')
    a("</g></svg>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(o))
    print("wrote", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
