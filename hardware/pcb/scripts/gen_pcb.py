"""Build the Pi Zero pHAT PCB (65 x 30 mm) for the 60 kHz transmitter with pcbnew."""
import pcbnew, sys, re
from pcbnew import VECTOR2I, FromMM as MM

OUT = sys.argv[1]
NETFILE = sys.argv[2]
FPLIB = "/usr/share/kicad/footprints/"

b = pcbnew.BOARD()
ds = b.GetDesignSettings()
ds.SetCopperLayerCount(2)
ds.m_TrackMinWidth = MM(0.2)
ds.m_MinClearance = MM(0.2)
ds.m_ViasMinSize = MM(0.6)
ds.m_MinThroughDrill = MM(0.3)
ds.m_HoleToHoleMin = MM(0.5)
ds.m_CopperEdgeClearance = MM(0.3)
ds.SetCustomViaSize(MM(0.6))
ds.SetCustomViaDrill(MM(0.3))

# ---- nets from the schematic netlist ----
txt = open(NETFILE).read()
pad_net = {}
for chunk in re.split(r'\(net \(code', txt)[1:]:
    name = re.search(r'\(name "([^"]+)"', chunk).group(1)
    if name.startswith("unconnected"):
        continue
    name = name.lstrip("/")
    for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', chunk):
        pad_net[(ref, pin)] = name
NETS = {}
for n in sorted(set(pad_net.values())):
    ni = pcbnew.NETINFO_ITEM(b, n)
    b.Add(ni)
    NETS[n] = ni

X0, Y0 = 100.0, 100.0
def P(x, y): return VECTOR2I(MM(X0 + x), MM(Y0 + y))

def add_fp(lib, name, ref, value, x, y, rot=0, bottom=False):
    fp = pcbnew.FootprintLoad(FPLIB + lib + ".pretty", name)
    fp.SetReference(ref); fp.SetValue(value); fp.SetFPID(pcbnew.LIB_ID(lib, name))
    b.Add(fp)
    if bottom:
        fp.Flip(fp.GetPosition(), False)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(x, y))
    for pad in fp.Pads():
        n = pad_net.get((ref, pad.GetNumber()))
        if n:
            pad.SetNet(NETS[n])
    return fp

def padpos(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == num:
            v = p.GetPosition()
            return (pcbnew.ToMM(v.x) - X0, pcbnew.ToMM(v.y) - Y0)

# ---- board outline: 65 x 30, r=3 corners ----
W, H, R = 65.0, 30.0, 3.0
def seg(a, bb, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a)); s.SetEnd(P(*bb)); s.SetLayer(layer); s.SetWidth(MM(w)); b.Add(s)
def arc(c, start, angle):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(P(*c)); s.SetStart(P(*start)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
seg((R, 0), (W - R, 0)); seg((W, R), (W, H - R)); seg((W - R, H), (R, H)); seg((0, H - R), (0, R))
arc((R, R), (0, R), 90); arc((W - R, R), (W - R, 0), 90)
arc((W - R, H - R), (W, H - R), 90); arc((R, H - R), (R, H), 90)

# ---- mounting holes (Pi Zero pattern 58 x 23) ----
for i, (hx, hy) in enumerate([(3.5, 3.5), (61.5, 3.5), (3.5, 26.5), (61.5, 26.5)]):
    add_fp("MountingHole", "MountingHole_2.7mm_M2.5", "H%d" % (i + 1), "M2.5", hx, hy)

# ---- J1 40-pin socket on the bottom, matching the Pi header ----
# Pi Zero (top view, header along top edge): pin 1 at left, inner row; pin 2 on the board-edge row.
# Header centre x = 32.5 mm, rows at y = 2.23 (even) and 4.77 (odd).
j1 = None
target1, target2, target3 = (32.5 - 9.5 * 2.54, 4.77), (32.5 - 9.5 * 2.54, 2.23), (32.5 - 8.5 * 2.54, 4.77)
for rot in (0, 90, 180, 270):
    for bottom in (True,):
        fp = add_fp("Connector_PinSocket_2.54mm", "PinSocket_2x20_P2.54mm_Vertical", "J1", "RPi_GPIO_40pin", 0, 0, rot, bottom)
        # move so pad 1 lands on target
        p1 = padpos(fp, "1")
        fp.Move(VECTOR2I(MM(target1[0] - p1[0]), MM(target1[1] - p1[1])))
        ok = all(abs(a - c) < 0.01 and abs(bb - d) < 0.01 for (a, bb), (c, d) in
                 [(padpos(fp, "2"), target2), (padpos(fp, "3"), target3)])
        if ok:
            j1 = fp; break
        b.Remove(fp)
    if j1: break
assert j1, "could not orient J1"
print("J1 orientation", j1.GetOrientationDegrees(), "bottom", j1.IsFlipped(), "pin7", padpos(j1, "7"))

# ---- parts ----
q1 = add_fp("Package_TO_SOT_SMD", "SOT-23", "Q1", "AO3400A", 23.0, 12.0, 0)
r2 = add_fp("Resistor_SMD", "R_0603_1608Metric", "R2", "470R", 15.99, 10.0, 270)
r3 = add_fp("Resistor_SMD", "R_0603_1608Metric", "R3", "100k", 19.0, 14.5, 270)
r1 = add_fp("Resistor_SMD", "R_1206_3216Metric", "R1", "220R", 24.0, 20.0, 0)
c6 = add_fp("Capacitor_SMD", "C_0805_2012Metric", "C6", "10uF", 11.5, 21.0, 270)
caps = []
for i, ref in enumerate(["C1", "C2", "C3", "C4"]):
    caps.append(add_fp("Capacitor_SMD", "C_1206_3216Metric", ref, "", 32.0 + i * 3.6, 16.5, 270))
c5 = add_fp("Capacitor_THT", "C_Disc_D5.0mm_W2.5mm_P5.00mm", "C5", "DNP trimmer/leaded", 47.5, 13.0, 270)
j2 = add_fp("TerminalBlock_Phoenix", "TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
            "J2", "ANTENNA", 55.0, 12.0, 270)
for fp, v in zip(caps, ["10nF C0G", "1.5nF C0G", "DNP tune", "DNP tune"]):
    fp.SetValue(v)

for fp in [q1, r2, r3, r1, c6, c5, j2] + caps:
    print(fp.GetReference(), [(p.GetNumber(), tuple(round(v, 2) for v in padpos(fp, p.GetNumber())), p.GetNetname()) for p in fp.Pads()])

print("STEP # ---- routing helpe", flush=True)
# ---- routing helpers ----
def track(pts, net, w=0.4, layer=pcbnew.F_Cu):
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c))
        t.SetWidth(MM(w)); t.SetLayer(layer); t.SetNet(NETS[net]); b.Add(t)
def via(pt, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(*pt)); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3))
    v.SetNet(NETS[net]); b.Add(v)

pp = padpos
# GPIO4: J1 pin 7 straight down to R2
g = pp(j1, "7"); r2a = pp(r2, "1"); r2b = pp(r2, "2")
track([g, (g[0], r2a[1])], "GPIO4", 0.3)
# GATE: R2.2 -> Q1.1 ; R3.1 -> gate line
q_g, q_s, q_d = pp(q1, "1"), pp(q1, "2"), pp(q1, "3")
track([r2b, (r2b[0], q_g[1]), q_g], "GATE", 0.3)
r3a, r3b = pp(r3, "1"), pp(r3, "2")
track([r3a, (r3a[0], q_g[1])], "GATE", 0.3)
# Q1 source to GND via
via((q_s[0] - 1.6, q_s[1]), "GND"); track([q_s, (q_s[0] - 1.6, q_s[1])], "GND", 0.5)
via((r3b[0], r3b[1] + 1.4), "GND"); track([r3b, (r3b[0], r3b[1] + 1.4)], "GND", 0.4)
# +5V: J1 pin 2 -> bottom layer -> left edge -> down -> via -> C6 -> R1
p2 = pp(j1, "2"); r1a, r1b = pp(r1, "1"), pp(r1, "2")
c6a, c6b = pp(c6, "1"), pp(c6, "2")
v5 = (6.7, r1a[1])
track([p2, (6.7, p2[1]), v5], "+5V", 0.6, pcbnew.B_Cu)
via(v5, "+5V")
track([v5, (c6a[0], v5[1])], "+5V", 0.6)
track([(c6a[0], v5[1]), c6a], "+5V", 0.6)
track([(c6a[0], v5[1]), r1a], "+5V", 0.6)
via((c6b[0], c6b[1] + 1.4), "GND"); track([c6b, (c6b[0], c6b[1] + 1.4)], "GND", 0.5)
# TANK_B: R1.2 up to the top bus -> caps pin 1 -> J2.1
cap_b = [pp(c, "1") for c in caps] + [pp(c5, "1")]
cap_a = [pp(c, "2") for c in caps] + [pp(c5, "2")]
ja, jb = pp(j2, "1"), pp(j2, "2")
yb = 12.0
track([r1b, (r1b[0], yb), (ja[0], yb)], "TANK_B", 0.6)
for c in cap_b:
    track([(c[0], yb), c], "TANK_B", 0.6)
# TANK_A: caps pin 2 -> lower bus -> J2.2 ; Q1 drain joins via the bottom layer
ya = cap_a[-1][1] + 3.5
for c in cap_a:
    track([c, (c[0], ya)], "TANK_A", 0.6)
track([(29.5, ya), (cap_a[-1][0], ya), (jb[0] - 3.0, ya), (jb[0] - 3.0, jb[1]), jb], "TANK_A", 0.6)
vd = (q_d[0], q_d[1] + 1.8)
track([q_d, vd], "TANK_A", 0.6)
via(vd, "TANK_A"); via((29.5, ya), "TANK_A")
track([vd, (vd[0], ya), (29.5, ya)], "TANK_A", 0.6, pcbnew.B_Cu)

print("STEP # ---- GND pours", flush=True)
# ---- GND pours, both layers ----
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(NETS["GND"])
    z.SetLocalClearance(MM(0.3)); z.SetMinThickness(MM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(MM(0.4)); z.SetThermalReliefSpokeWidth(MM(0.5))
    ol = z.Outline(); ol.NewOutline()
    for (x, y) in [(0.3, 0.3), (64.7, 0.3), (64.7, 29.7), (0.3, 29.7)]:
        ol.Append(MM(X0 + x), MM(Y0 + y))
    b.Add(z)
print("STEP # stitching vias", flush=True)
# stitching vias along the free bottom strip
for x in (9.0, 13.5, 43.0, 50.0, 56.0):
    via((x, 27.6), "GND")

# keep-out over the Pi Zero W / Zero 2 W PCB antenna (port edge, between mini-HDMI and USB):
# no copper fill, tracks or vias on either layer so Wi-Fi/Bluetooth isn't shielded
ANT_KEEPOUT = (16.0, 22.4, 39.0, 30.0)   # x0, y0, x1, y1 in board mm
ko = pcbnew.ZONE(b)
ko.SetIsRuleArea(True)
ko.SetDoNotAllowCopperPour(True); ko.SetDoNotAllowTracks(True); ko.SetDoNotAllowVias(True)
ko.SetDoNotAllowPads(False); ko.SetDoNotAllowFootprints(False)
ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); ko.SetLayerSet(ls)
ko.SetZoneName("WiFi antenna keep-out")
kol = ko.Outline(); kol.NewOutline()
x0, y0, x1, y1 = ANT_KEEPOUT
for (x, y) in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
    kol.Append(MM(X0 + x), MM(Y0 + y))
b.Add(ko)

print("STEP # ---- silkscreen", flush=True)
# ---- silkscreen labels ----
def text(s, x, y, size=1.0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(b); t.SetText(s); t.SetPosition(P(x, y)); t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(size * 0.15)); b.Add(t)
text("Pi 60kHz Time TX v1.2", 33.0, 25.2, 1.2)
text("WiFi antenna: keep clear", 27.5, 28.2, 0.8)
text("ANTENNA COIL", 58.0, 8.1, 0.8)
text("(either way round)", 58.0, 21.1, 0.8)
text("TUNE: C3 C4 C5", 39.5, 21.0, 0.8)
text("GPIO4 / 5V / GND", 16.0, 7.2, 0.8)
# +5V: join header pins 2 and 4 on the bottom layer
track([pp(j1, "2"), pp(j1, "4")], "+5V", 0.6, pcbnew.B_Cu)
# solid ground on the header GND pins (pin field too tight for 2 thermal spokes)
for pad in j1.Pads():
    if pad.GetNetname() == "GND":
        pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
# tidy silkscreen: hide mounting-hole refs, move C5 ref
for fp in b.GetFootprints():
    if fp.GetReference().startswith("H"):
        fp.Reference().SetVisible(False)
c5.Reference().SetPosition(P(47.5, 20.6))

print("STEP pcbnew.ZONE_FILLER", flush=True)
#FILL_LATER
print("STEP b.Save(OUT)", flush=True)
b.Save(OUT)
print("saved")
