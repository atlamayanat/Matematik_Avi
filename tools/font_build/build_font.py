# Builds FredokaGame.ttf:
#   * Fredoka variable font instanced to a static weight (game-friendly).
#   * Turkish letters Istanbul-I, gbreve, Gbreve, Scedilla, scedilla COMPOSED from
#     Fredoka's OWN base letters + its own combining marks (perfect style match).
#   * Math glyphs root/pi/infinity borrowed from Noto Sans Math (same 1000 upm).
import sys, copy
sys.stdout.reconfigure(encoding="utf-8")
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontTools.ttLib.tables import ttProgram
from fontTools.varLib import instancer

WGHT = 540   # Fredoka weight to bake (300..700). 540 = friendly + readable.

f = TTFont("Fredoka-VF.ttf")
instancer.instantiateVariableFont(f, {"wght": WGHT, "wdth": 100}, inplace=True)
glyf = f["glyf"]; hmtx = f["hmtx"]
order = f.getGlyphOrder()

def bbox(name):
    g = glyf[name]; g.recalcBounds(glyf)
    return g.xMin, g.yMin, g.xMax, g.yMax
def cx(name):
    x0,_,x1,_ = bbox(name); return (x0+x1)/2.0
def adv(name):
    return hmtx[name][0]

# reference cedilla placement straight from the font's own ccedilla / Ccedilla
c_cx, C_cx = cx("c"), cx("C")
s_cx, S_cx = cx("s"), cx("S")

def add_composite(newname, cp, base, mark, dx, dy, advance):
    g = Glyph(); g.numberOfContours = -1; g.components = []
    for gn, x, y in ((base, 0, 0), (mark, int(round(dx)), int(round(dy)))):
        c = GlyphComponent(); c.glyphName = gn; c.x = int(x); c.y = int(y)
        c.flags = 0x0004  # ROUND_XY_TO_GRID; ARGS_ARE_XY_VALUES added below
        c.flags |= 0x0002
        g.components.append(c)
    glyf[newname] = g
    g.recalcBounds(glyf)
    _, lsb = hmtx[base]
    hmtx[newname] = (advance, g.xMin if hasattr(g, "xMin") else 0)
    if newname not in order: order.append(newname)
    return cp, newname

added = []

# --- cedilla letters: reuse font's own ccedilla/Ccedilla offsets, shift for s/S center
added.append(add_composite("scedilla", 0x015F, "s", "uni0327", 170 + (s_cx - c_cx), 0,  adv("s")))
added.append(add_composite("Scedilla", 0x015E, "S", "uni0327", 266 + (S_cx - C_cx), 16, adv("S")))

# --- marks above: centre over the base, sit a small gap above the base top
def above(newname, cp, base, mark, gap, advance):
    bx0,by0,bx1,by1 = bbox(base)
    mx0,my0,mx1,my1 = bbox(mark)
    dx = (bx0+bx1)/2.0 - (mx0+mx1)/2.0
    dy = (by1 + gap) - my0
    added.append(add_composite(newname, cp, base, mark, dx, dy, advance))

above("gbreve",     0x011F, "g", "uni0306", 30, adv("g"))   # ğ
above("Gbreve",     0x011E, "G", "uni0306", 60, adv("G"))   # Ğ
above("Idotaccent", 0x0130, "I", "uni0307", 60, adv("I"))   # İ

# --- math glyphs from Noto Sans Math (1000 upm, simple outlines)
md = TTFont("MathDonor.ttf")
mglyf, mhmtx, mcmap = md["glyf"], md["hmtx"], md.getBestCmap()
for cp, newname in [(0x221A,"uni221A"), (0x03C0,"uni03C0"), (0x221E,"uni221E")]:
    src = mcmap[cp]
    g = copy.deepcopy(mglyf[src])
    if hasattr(g, "program"):
        p = ttProgram.Program(); p.fromBytecode(b""); g.program = p
    glyf[newname] = g
    hmtx[newname] = mhmtx[src]
    if newname not in order: order.append(newname)
    added.append((cp, newname))

# commit glyph order + maxp, then map all new codepoints into every unicode cmap
f.setGlyphOrder(order)
f["maxp"].numGlyphs = len(order)
for t in f["cmap"].tables:
    if t.isUnicode():
        for cp, name in added:
            t.cmap[cp] = name

# rename so Unity shows a distinct font
for nid in (1, 16):
    f["name"].setName("Fredoka Game", nid, 3, 1, 0x409)
    f["name"].setName("Fredoka Game", nid, 1, 0, 0)
for nid in (4,):
    f["name"].setName("Fredoka Game Regular", nid, 3, 1, 0x409)
f["name"].setName("FredokaGame-Regular", 6, 3, 1, 0x409)
for nid in (2, 17):
    f["name"].setName("Regular", nid, 3, 1, 0x409)

f.save("FredokaGame.ttf")
print("Saved FredokaGame.ttf  (weight", WGHT, ")  added glyphs:", [n for _,n in added])
