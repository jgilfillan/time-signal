"""Generate the KiCad 7 schematic for the Pi 60 kHz time-signal pHAT.
Symbols are copied from the installed KiCad libraries; every pin gets a short
wire stub and a net label so connectivity is exact and checkable with ERC."""
import re, uuid, math, sys

LIB = "/usr/share/kicad/symbols/"
OUT = sys.argv[1]

def u(): return str(uuid.uuid4())

# ---------- tiny s-expression helpers ----------
def extract_block(text, start):
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == '"':
            # skip string
            j = i + 1
            while text[j] != '"':
                j += 2 if text[j] == '\\' else 1
            continue
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError

def get_symbol(lib, name):
    txt = open(LIB + lib + ".kicad_sym").read()
    i = txt.find('(symbol "%s"' % name)
    blk = extract_block(txt, i)
    # rename top-level to lib:name (sub-units keep plain names)
    blk = blk.replace('(symbol "%s"' % name, '(symbol "%s:%s"' % (lib, name), 1)
    pins = {}
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\).*?\(number "([^"]+)"', blk, re.S):
        x, y, a, num = m.groups()
        pins[num] = (float(x), float(y), float(a))
    return blk, pins

SYMS = {}
def need(lib, name):
    key = lib + ":" + name
    if key not in SYMS:
        SYMS[key] = get_symbol(lib, name)
    return key

parts = []      # symbol instances
wires = []
labels = []
noconn = []
texts = []

def rot(px, py, r):
    # symbol coords (y up) -> sheet offset (y down), rotated by r deg CCW
    x, y = px, -py
    t = math.radians(r)
    return (round(x * math.cos(t) + y * math.sin(t), 4),
            round(-x * math.sin(t) + y * math.cos(t), 4))

def place(lib, name, ref, value, x, y, r=0, fp="", props=None, nets=None,
          in_bom=True, on_board=True, dnp=False, stub=2.54):
    key = need(lib, name)
    blk, pins = SYMS[key]
    parts.append(dict(key=key, ref=ref, value=value, x=x, y=y, r=r, fp=fp,
                      props=props or {}, pins=list(pins.keys()),
                      in_bom=in_bom, on_board=on_board, dnp=dnp))
    for num, (px, py, pa) in pins.items():
        ox, oy = rot(px, py, r)
        ex, ey = x + ox, y + oy
        net = (nets or {}).get(num)
        if net is None:
            noconn.append((ex, ey))
            continue
        # outward direction = pin angle + 180, rotated
        ang = math.radians(pa + 180 + r)
        dx, dy = round(math.cos(ang) * stub, 4), round(-math.sin(ang) * stub, 4)
        wx, wy = round(ex + dx, 4), round(ey + dy, 4)
        wires.append(((ex, ey), (wx, wy)))
        # label rotation so text reads away from pin
        deg = (pa + 180 + r) % 360
        labels.append((net, wx, wy, {0: 0, 90: 90, 180: 180, 270: 270}.get(round(deg) % 360, 0)))

# ---------------- the circuit ----------------
# J1: Raspberry Pi 40-pin header (female socket on the pHAT)
GND_PINS = ["6", "9", "14", "20", "25", "30", "34", "39"]
j1nets = {"2": "+5V", "4": "+5V", "7": "GPIO4"}
for p in GND_PINS: j1nets[p] = "GND"
place("Connector_Generic", "Conn_02x20_Odd_Even", "J1", "RPi_GPIO_40pin", 50.8, 88.9,
      fp="Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical", props={"LCSC": "C2977589"}, nets=j1nets)

# Gate drive
place("Device", "R", "R2", "470R", 88.9, 66.04, r=90, fp="Resistor_SMD:R_0603_1608Metric",
      props={"LCSC": "C23179"}, nets={"1": "GPIO4", "2": "GATE"})
place("Device", "R", "R3", "100k", 101.6, 78.74, r=0, fp="Resistor_SMD:R_0603_1608Metric",
      props={"LCSC": "C25803"}, nets={"1": "GATE", "2": "GND"})
place("Transistor_FET", "BSS138", "Q1", "AO3400A", 116.84, 66.04, r=0,
      fp="Package_TO_SOT_SMD:SOT-23", props={"LCSC": "C20917"},
      nets={"1": "GATE", "2": "GND", "3": "TANK_A"})
# Pull-up / current limit
place("Device", "R", "R1", "220R", 119.38, 45.72, r=0, fp="Resistor_SMD:R_1206_3216Metric",
      props={"LCSC": "C17957"}, nets={"1": "+5V", "2": "TANK_B"})
# Series tuning capacitors (all in parallel with each other)
caps = [("C1", "10nF C0G", "C64713", False, "Capacitor_SMD:C_1206_3216Metric"),
        ("C2", "1.5nF C0G", "C105972", False, "Capacitor_SMD:C_1206_3216Metric"),
        ("C3", "DNP tune", "", True, "Capacitor_SMD:C_1206_3216Metric"),
        ("C4", "DNP tune", "", True, "Capacitor_SMD:C_1206_3216Metric"),
        ("C5", "DNP trimmer/leaded", "", True, "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm")]
for i, (ref, val, lc, dnp, fp) in enumerate(caps):
    place("Device", "C", ref, val, 142.24 + i * 12.7, 66.04, r=0, fp=fp,
          props={"LCSC": lc} if lc else {}, nets={"1": "TANK_B", "2": "TANK_A"},
          in_bom=not dnp, dnp=dnp)
# Antenna terminal and the off-board ferrite coil
place("Connector", "Screw_Terminal_01x02", "J2", "ANTENNA", 213.36, 66.04, r=0,
      fp="TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
      props={"LCSC": "C8465"}, nets={"1": "TANK_B", "2": "TANK_A"})
place("Device", "L", "L1", "Ferrite antenna ~610uH (off-board)", 228.6, 66.04, r=0,
      nets={"1": "TANK_B", "2": "TANK_A"}, in_bom=False, on_board=False)
# Supply decoupling
place("Device", "C", "C6", "10uF", 101.6, 45.72, r=0, fp="Capacitor_SMD:C_0805_2012Metric",
      props={"LCSC": "C15850"}, nets={"1": "+5V", "2": "GND"})
# Power flags
place("power", "PWR_FLAG", "#FLG01", "PWR_FLAG", 88.9, 30.48, nets={"1": "+5V"})
place("power", "PWR_FLAG", "#FLG02", "PWR_FLAG", 101.6, 30.48, nets={"1": "GND"})

texts.append(("Raspberry Pi 60 kHz time-signal transmitter pHAT (WWVB / MSF / JJY60)", 25.4, 20.32))
texts.append(("Parallel tank (as tested on breadboard): 5V -> R1 220R -> TANK_B; ferrite coil and C1..C5 in parallel between TANK_B and TANK_A;\\nQ1 drain on TANK_A, source to GND. GPIO4 drives the gate via R2 470R, R3 100k holds Q1 off at boot.", 25.4, 130.0))
texts.append(("Tuning: C1+C2 = 11.5 nF for ~600 uH. Add C3/C4 (1206 C0G) or a leaded trimmer in C5 to trim to 60.000 kHz.", 25.4, 140.0))

# ---------------- write file ----------------
o = []
o.append('(kicad_sch (version 20230121) (generator eeschema)\n  (uuid %s)\n  (paper "A4")' % u())
o.append('  (title_block (title "Pi 60kHz Time-Signal pHAT") (rev "1.2") (date "2026-11-17"))')
o.append('  (lib_symbols')
for k, (blk, _) in SYMS.items():
    o.append(blk)
o.append('  )')
for (a, b) in wires:
    o.append('  (wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid %s))' % (a[0], a[1], b[0], b[1], u()))
for (net, x, y, r) in labels:
    just = "left" if r in (0, 90) else "right"
    o.append('  (label "%s" (at %s %s %d) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify %s bottom)) (uuid %s))' % (net, x, y, r, just, u()))
for (x, y) in noconn:
    o.append('  (no_connect (at %s %s) (uuid %s))' % (x, y, u()))
for (t, x, y) in texts:
    o.append('  (text "%s" (at %s %s 0) (effects (font (size 1.8 1.8)) (justify left bottom)) (uuid %s))' % (t, x, y, u()))
root = u()
for p in parts:
    pin_s = "\n".join('    (pin "%s" (uuid %s))' % (n, u()) for n in p["pins"])
    prop_lines = []
    pidx = 4
    for k, v in p["props"].items():
        prop_lines.append('    (property "%s" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) hide))' % (k, v, p["x"], p["y"]))
    hide_ref = " hide" if p["ref"].startswith("#") else ""
    o.append('''  (symbol (lib_id "%s") (at %s %s %d) (unit 1)
    (in_bom %s) (on_board %s) (dnp %s) (fields_autoplaced)
    (uuid %s)
    (property "Reference" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left)%s))
    (property "Value" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "%s" (at %s %s 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "~" (at %s %s 0) (effects (font (size 1.27 1.27)) hide))
%s
%s
    (instances (project "pi_time_tx" (path "/%s" (reference "%s") (unit 1))))
  )''' % (p["key"], p["x"], p["y"], p["r"],
         "yes" if p["in_bom"] else "no", "yes" if p["on_board"] else "no", "yes" if p["dnp"] else "no",
         u(), p["ref"], p["x"] + 4, p["y"] - 4, hide_ref, p["value"], p["x"] + 4, p["y"] + 4.5,
         p["fp"], p["x"], p["y"], p["x"], p["y"], "\n".join(prop_lines), pin_s, root, p["ref"]))
o.append('  (sheet_instances (path "/" (page "1")))\n)')
txt = "\n".join(o).replace("(uuid %s)\n  (paper" % "", "(paper")
# set root uuid consistently
txt = re.sub(r'\(kicad_sch \(version 20230121\) \(generator eeschema\)\n  \(uuid [^)]+\)',
             '(kicad_sch (version 20230121) (generator eeschema)\n  (uuid %s)' % root, txt, count=1)
open(OUT, "w").write(txt)
print("pins found:", {k: len(v[1]) for k, v in SYMS.items()})
