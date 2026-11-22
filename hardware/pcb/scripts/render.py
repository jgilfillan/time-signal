"""Photo-style render of the pHAT from per-layer SVG plots plus drawn component bodies."""
import cairosvg, io, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import pcbnew

# Folder holding per-layer SVGs exported with:
#   kicad-cli pcb export svg --layers <L> --exclude-drawing-sheet --page-size-mode 0 \
#     --black-and-white -o <dir>/<L>.svg pi_time_tx.kicad_pcb
# for L in F.Cu F.Mask F.Silkscreen B.Cu B.Mask B.Silkscreen
S = (sys.argv[1] if len(sys.argv) > 1 else "svg") + "/"
PCB = "pi_time_tx.kicad_pcb"
SC = 40                      # px per mm
X0, Y0, W, H, M = 100, 100, 65, 30, 4
board = pcbnew.LoadBoard(PCB)

def layer(name):
    png = cairosvg.svg2png(url=S + name + ".svg", output_width=int(297.0022 * SC), background_color="white")
    im = Image.open(io.BytesIO(png)).convert("L")
    im = im.crop((int((X0 - M) * SC), int((Y0 - M) * SC), int((X0 + W + M) * SC), int((Y0 + H + M) * SC)))
    return np.array(im) < 128          # True where something is drawn

def px(x, y): return ((x - X0 + M) * SC, (y - Y0 + M) * SC)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def render(side):
    cu, mask, silk = layer(side + ".Cu"), layer(side + ".Mask"), layer(side + ".Silkscreen")
    h, w = cu.shape
    img = np.zeros((h, w, 3), np.float32)
    # board outline mask
    outline = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(outline)
    d.rounded_rectangle([px(X0, Y0), px(X0 + W, Y0 + H)], radius=3 * SC, fill=255)
    bmask = np.array(outline) > 0
    FR4 = np.array([196, 170, 110]); MASK = np.array([18, 92, 48]); MASKCU = np.array([38, 128, 64])
    HASL = np.array([214, 214, 206]); SILK = np.array([245, 245, 240])
    img[:] = FR4
    img[~mask & ~cu] = MASK
    img[~mask & cu] = MASKCU
    img[mask & cu] = HASL
    img[silk & ~mask] = SILK
    # subtle noise for texture
    img += np.random.default_rng(1).normal(0, 3, img.shape)
    out = np.clip(img, 0, 255).astype(np.uint8)
    pic = Image.fromarray(out)
    pic.putalpha(outline)
    dr = ImageDraw.Draw(pic)
    # drill holes
    for fp in board.GetFootprints():
        for p in fp.Pads():
            dsz = p.GetDrillSize()
            if dsz.x > 0:
                c = p.GetPosition(); r = pcbnew.ToMM(dsz.x) / 2
                cx, cy = px(pcbnew.ToMM(c.x), pcbnew.ToMM(c.y))
                dr.ellipse([cx - r * SC, cy - r * SC, cx + r * SC, cy + r * SC], fill=(20, 20, 20, 0) if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else (25, 25, 25, 255))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition(); cx, cy = px(pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)); r = 0.15 * SC
            dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(25, 25, 25, 255))
    # punch NPTH mounting holes through alpha
    a = np.array(pic.getchannel("A"))
    for fp in board.GetFootprints():
        if fp.GetReference().startswith("H"):
            c = fp.GetPosition(); cx, cy = px(pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)); r = 1.35 * SC
            yy, xx = np.ogrid[:h, :w]; a[(xx - cx) ** 2 + (yy - cy) ** 2 < r * r] = 0
    pic.putalpha(Image.fromarray(a))
    return pic, dr

def body(dr, cx, cy, lw, lh, rot, fill, edge=None, label=None, fsize=1.0, lab_col=(235, 235, 235)):
    """Draw a component body (mm) centred on cx,cy rotated by rot degrees."""
    if rot % 180 == 90: lw, lh = lh, lw
    x0, y0 = px(cx - lw / 2, cy - lh / 2); x1, y1 = px(cx + lw / 2, cy + lh / 2)
    dr.rounded_rectangle([x0 + 6, y0 + 8, x1 + 6, y1 + 8], radius=int(0.2 * SC), fill=(0, 0, 0, 90))  # shadow
    dr.rounded_rectangle([x0, y0, x1, y1], radius=int(0.15 * SC), fill=fill, outline=edge, width=3)
    if label:
        f = ImageFont.truetype(FONT, int(fsize * SC))
        tw = dr.textlength(label, font=f)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        dr.text((mx - tw / 2, my - fsize * SC * 0.62), label, font=f, fill=lab_col)

def fpos(ref):
    fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
    c = fp.GetPosition()
    return pcbnew.ToMM(c.x), pcbnew.ToMM(c.y), fp.GetOrientationDegrees() % 360, fp

# ---------------- TOP ----------------
top, dr = render("F")
DARK = (28, 28, 30, 255)
CERA = (176, 140, 92, 255)
x, y, r, _ = fpos("Q1")
body(dr, x, y, 2.9, 1.3, r, DARK, label="A09T", fsize=0.55)
x, y, r, _ = fpos("R1"); body(dr, x, y, 2.9, 1.5, r, DARK, label="2200", fsize=0.7)
for ref, lab in (("R2", "101"), ("R3", "104")):
    x, y, r, _ = fpos(ref); body(dr, x, y, 1.45, 0.8, r, DARK, label=None)
for ref in ("C1", "C2"):
    x, y, r, _ = fpos(ref); body(dr, x, y, 2.9, 1.5, r, CERA, edge=(150, 115, 70, 255))
x, y, r, _ = fpos("C6"); body(dr, x, y, 1.75, 1.15, r, CERA, edge=(150, 115, 70, 255))
# terminal block J2 (bounding box of its silk courtyard approximated)
x, y, r, fp = fpos("J2")
bb = fp.GetBoundingBox(False, False)
bx0, by0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
bx1, by1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
body(dr, cx, cy, bx1 - bx0 - 0.3, by1 - by0 - 0.3, 0, (30, 110, 60, 255), edge=(15, 70, 35, 255))
for p in fp.Pads():
    c = p.GetPosition(); sx, sy = px(pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)); rr = 1.6 * SC
    dr.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=(180, 180, 175, 255), outline=(90, 90, 90, 255), width=4)
    dr.line([sx - rr * 0.8, sy, sx + rr * 0.8, sy], fill=(60, 60, 60, 255), width=int(0.35 * SC))
    # wire entry openings on the board-edge side
    ex0, ey0 = px(bx1 - 1.2, pcbnew.ToMM(c.y) - 1.4); ex1, ey1 = px(bx1 - 0.2, pcbnew.ToMM(c.y) + 1.4)
    dr.rectangle([ex0, ey0, ex1, ey1], fill=(10, 30, 15, 255))
# antenna leads leaving J2
for i, p in enumerate(fp.Pads()):
    c = p.GetPosition(); sy = px(0, pcbnew.ToMM(c.y))[1]
    sx = px(bx1, 0)[0]
    dr.line([sx, sy, top.width, sy + (i * 2 - 1) * 10], fill=(180, 95, 45, 255), width=int(0.5 * SC))

def finish(pic, title, path, mirror=False):
    if mirror: pic = pic.transpose(Image.FLIP_LEFT_RIGHT)
    pad = 60
    canvas = Image.new("RGBA", (pic.width + 2 * pad, pic.height + 2 * pad + 70), (236, 236, 232, 255))
    sh = Image.new("RGBA", pic.size, (0, 0, 0, 0)); sh.putalpha(pic.getchannel("A").point(lambda v: 110 if v else 0))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(sh, (pad + 18, pad + 24)); canvas.alpha_composite(pic, (pad, pad))
    d = ImageDraw.Draw(canvas)
    d.text((pad, pic.height + pad + 18), title, font=ImageFont.truetype(FONT, 40), fill=(60, 60, 60))
    canvas.convert("RGB").save(path, quality=92)

finish(top, "Top - 65 x 30 mm, plugs onto a Pi Zero", "render_top.png")

# ---------------- BOTTOM ----------------
bot, dr = render("B")
x, y, r, fp = fpos("J1")
bb = fp.GetBoundingBox(False, False)
bx0, by0, bx1, by1 = [pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())]
body(dr, (bx0 + bx1) / 2, (by0 + by1) / 2, bx1 - bx0 - 0.2, by1 - by0 - 0.2, 0, (22, 22, 24, 255), edge=(60, 60, 60, 255))
for p in fp.Pads():
    c = p.GetPosition(); sx, sy = px(pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)); rr = 0.45 * SC
    dr.rectangle([sx - rr, sy - rr, sx + rr, sy + rr], fill=(8, 8, 8, 255))
finish(bot, "Bottom - 40-pin socket plugs onto the Pi header", "render_bottom.png", mirror=True)
print("done")
