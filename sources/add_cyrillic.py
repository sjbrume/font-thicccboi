"""Generate Cyrillic glyphs (Russian, Ukrainian, Belarusian, Bulgarian, Serbian, Macedonian)
into THICCCBOI.glyphs from the existing Latin outlines.

    pip install glyphsLib
    python sources/add_cyrillic.py sources/THICCCBOI.glyphs

Re-running replaces the glyphs it generated before, so tweak the numbers below and run again.
Look-alike letters (А В Е К М Н О Р С Т Х …) are components of the Latin glyphs.
Every number is given as (Thin, Black) for the two masters.
"""
import sys

from fontTools.misc.transform import Transform as T
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from glyphsLib.classes import GSComponent, GSFont, GSGlyph, GSLayer, GSNode, GSPath, Transform

path = sys.argv[1]
f = GSFont(path)
MASTERS = [m.id for m in f.masters]  # Thin, Black
assert [m.name for m in f.masters] == ["Thin", "Black"], [m.name for m in f.masters]

# ---------- outline helpers (a contour is a Glyphs node list: [(x, y, type), ...], start node last)


def reverse(nodes):
    rec = RecordingPen()
    pen = ReverseContourPen(rec)
    pen.moveTo(nodes[-1][:2])
    offs = []
    for x, y, t in nodes:
        if t == "offcurve":
            offs.append((x, y))
        elif t == "line":
            pen.lineTo((x, y))
        else:
            pen.curveTo(*offs, (x, y))
            offs = []
    pen.closePath()
    out, start = [], None
    for op, args in rec.value:
        if op == "moveTo":
            start = args[0]
        elif op == "lineTo":
            out.append((*args[0], "line"))
        elif op == "curveTo":
            out += [(*args[0], "offcurve"), (*args[1], "offcurve"), (*args[2], "curve")]
    if (out[-1][0], out[-1][1]) != tuple(start):
        out.append((*start, "line"))
    # drop zero-length lines
    return [n for i, n in enumerate(out) if not (n[2] == "line" and n[:2] == out[i - 1][:2])]


def transform(contours, tf):
    tf = T(*tf)
    out = [[(*tf.transformPoint((x, y)), t) for x, y, t in c] for c in contours]
    return [reverse(c) for c in out] if tf.xx * tf.yy - tf.xy * tf.yx < 0 else out


def pw(v, pts):
    """Piecewise-linear remap through (src, dst) points; constant shift outside them."""
    if not pts:
        return v
    if v <= pts[0][0]:
        return v + pts[0][1] - pts[0][0]
    if v >= pts[-1][0]:
        return v + pts[-1][1] - pts[-1][0]
    for (a, a2), (b, b2) in zip(pts, pts[1:]):
        if a <= v <= b:
            return a2 + (v - a) * (b2 - a2) / (b - a)


def remap(contours, xmap=(), ymap=()):
    return [[(pw(x, xmap), pw(y, ymap), t) for x, y, t in c] for c in contours]


def items(name, m):
    """Top-level shapes of a glyph layer (components first, then paths), each as decomposed contours."""
    layer = f.glyphs[name].layers[MASTERS[m]]
    out = [transform(sum(items(c.name, m), []), tuple(c.transform)) for c in layer.components]
    out += [[[(n.position.x, n.position.y, n.type) for n in p.nodes]] for p in layer.paths]
    return out


def src(name, m, idx=None, tf=(1, 0, 0, 1, 0, 0), xmap=(), ymap=()):
    shapes = items(name, m)
    picked = sum((shapes[i] for i in (idx if idx is not None else range(len(shapes)))), [])
    return transform(remap(picked, xmap, ymap), tf)


def width(name, m):
    return f.glyphs[name].layers[MASTERS[m]].width


def bbox(contours):
    xs = [n[0] for c in contours for n in c]
    ys = [n[1] for c in contours for n in c]
    return min(xs), max(xs), min(ys), max(ys)


def poly(pts):
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    return [(x, y, "line") for x, y in (pts if area > 0 else pts[::-1])]


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def para(xb, w, xt, y0, y1):
    """Slanted stroke: horizontal width w, from x=xb at y0 to x=xt at y1."""
    return poly([(xb, y0), (xb + w, y0), (xt + w, y1), (xt, y1)])


def shift(contours, dx, dy=0):
    return transform(contours, (1, 0, 0, 1, dx, dy))


def mirror(contours, lsb, rsb):
    x0, x1, _, _ = bbox(contours)
    out = transform(contours, (-1, 0, 0, 1, x0 + x1, 0))
    out = shift(out, lsb - x0)
    return out, bbox(out)[1] + rsb


# ---------- parameters, (Thin, Black)

CAP = dict(L=(90, 35), S=(32, 190), B=(30, 180), H=700, D=-150, R=(549, 485))
LC = dict(L=(65, 20), S=(30, 180), B=(30, 170), H=500, D=-150, R=(447, 330))


def P(k, m):
    return {key: (v[m] if isinstance(v, tuple) else v) for key, v in k.items()}


built = {}  # (name, m) -> contours, for accent placement


def two_stems(p, h=None):
    h = h or p["H"]
    return [rect(p["L"], 0, p["L"] + p["S"], h), rect(p["R"], 0, p["R"] + p["S"], h)], p["R"] + p["S"] + p["L"]


def pe(k, m):
    p = P(k, m)
    c, w = two_stems(p)
    return c + [rect(p["L"], p["H"] - p["B"], p["R"] + p["S"], p["H"])], w


def en_lc(m):
    p = P(LC, m)
    c, w = two_stems(p)
    y = (235, 165)[m]
    return c + [rect(p["L"], y, p["R"] + p["S"], y + p["B"])], w


def tse(k, m, center=False):
    p = P(k, m)
    c, w = two_stems(p)
    x = (p["L"] + p["R"] + p["S"]) / 2 - p["S"] / 2 if center else p["R"]
    return c + [rect(p["L"], 0, p["R"] + p["S"], p["B"]), rect(x, p["D"], x + p["S"], 1)], w


def sha(k, m, tail=False):
    p = P(k, m)
    xs = {id(CAP): ((90, 422, 754), (35, 415, 795)), id(LC): ((65, 345, 625), (20, 318, 616))}[id(k)][m]
    c = [rect(x, 0, x + p["S"], p["H"]) for x in xs] + [rect(xs[0], 0, xs[2] + p["S"], p["B"])]
    if tail:
        c.append(rect(xs[2], p["D"], xs[2] + p["S"], 1))
    return c, xs[2] + p["S"] + p["L"]


def che(k, m):
    p = P(k, m)
    xr, yb = {id(CAP): ((489, 300), (425, 250)), id(LC): ((420, 210), (320, 160))}[id(k)][m]
    L, S, B, H = p["L"], p["S"], p["B"], p["H"]
    return [rect(L, yb, L + S, H), rect(L, yb, xr + S, yb + B), rect(xr, 0, xr + S, H)], xr + S + L


def te_lc(m):
    p = P(LC, m)
    x0, x1, w = ((20, 440, 460), (0, 500, 500))[m]
    c = (x0 + x1) / 2
    return [rect(x0, p["H"] - p["B"], x1, p["H"]), rect(c - p["S"] / 2, 0, c + p["S"] / 2, p["H"])], w


def ge(k, m):
    if k is CAP:
        return src("F", m, idx=[0, 1]), width("F", m)
    p = P(k, m)
    end, w = ((380, 420), (400, 430))[m]
    return [rect(p["L"], 0, p["L"] + p["S"], p["H"]), rect(p["L"], p["H"] - p["B"], end, p["H"])], w


def geupturn(k, m):
    c, w = ge(k, m)
    p = P(k, m)
    end = bbox(c)[1]
    return c + [rect(end - p["S"], p["H"] - 10, end, p["H"] + 150)], w


# El / De: slanted left leg, top bar, right stem (De adds base and tails)
EL = {
    id(CAP): (dict(xb=30, w=36, xt=150, stem=540, w_=662), dict(xb=0, w=205, xt=150, stem=490, w_=715)),
    id(LC): (dict(xb=25, w=35, xt=120, stem=422, w_=517), dict(xb=0, w=200, xt=120, stem=380, w_=580)),
}
DE = {
    id(CAP): (dict(xb=80, w=36, xt=200, stem=578, x0=20, x1=650, w_=690),
              dict(xb=70, w=200, xt=210, stem=530, x0=0, x1=760, w_=790)),
    id(LC): (dict(xb=70, w=34, xt=160, stem=440, x0=20, x1=510, w_=530),
             dict(xb=60, w=195, xt=180, stem=420, x0=0, x1=640, w_=660)),
}


def el_shape(p, g):
    H, S, B = p["H"], p["S"], p["B"]
    return [para(g["xb"], g["w"], g["xt"], 0, H), rect(g["xt"], H - B, g["stem"] + S, H), rect(g["stem"], 0, g["stem"] + S, H)]


def el(k, m):
    g = EL[id(k)][m]
    return el_shape(P(k, m), g), g["w_"]


def de(k, m):
    p, g = P(k, m), DE[id(k)][m]
    S, B, D = p["S"], p["B"], p["D"]
    c = el_shape(p, g) + [rect(g["x0"], 0, g["x1"], B), rect(g["x0"], D, g["x0"] + S, 1), rect(g["x1"] - S, D, g["x1"], 1)]
    return c, g["w_"]


def bowl(k, m):
    """Lower bowl of B, resized for Soft sign; attaches to a stem at x=L."""
    if k is CAP:
        top = (410, 450)[m]
        ymap = ([(0, 0), (32, 32), (343, top - 32), (375, top)], [(0, 0), (444, top)])[m]
        return src("B", m, idx=[2], ymap=ymap), (75, 50)[m]
    ymap = ([(0, 0), (32, 32), (343, 268), (375, 300)], [(0, 0), (444, 330)])[m]
    xmap = ([(130, 130), (368, 320)], [(230, 230), (375, 335)])[m]
    return src("B", m, idx=[2], xmap=xmap, ymap=ymap, tf=(1, 0, 0, 1, (-25, -15)[m], 0)), (60, 40)[m]


def soft(k, m):
    p = P(k, m)
    b, rsb = bowl(k, m)
    return [rect(p["L"], 0, p["L"] + p["S"], p["H"])] + b, bbox(b)[1] + rsb


def hard(k, m):
    p = P(k, m)
    c, w = soft(k, m)
    dx, x0 = {id(CAP): ((120, 25), (130, 0)), id(LC): ((100, 20), (110, 0))}[id(k)][m]
    return shift(c, dx) + [rect(x0, p["H"] - p["B"], dx + p["L"] + p["S"], p["H"])], w + dx


def yeru(k, m):
    p = P(k, m)
    c, _ = soft(k, m)
    x = bbox(c)[1] + {id(CAP): (90, 70), id(LC): (75, 55)}[id(k)][m]
    return c + [rect(x, 0, x + p["S"], p["H"])], x + p["S"] + p["L"]


def be(k, m):
    p = P(k, m)
    if k is CAP:
        c, _ = soft(k, m)
        return c + [rect(p["L"], p["H"] - p["B"], (470, 500)[m], p["H"])], width("B", m)
    y = (670, 560)[m]
    return src("b", m) + [rect(p["L"], y, (440, 470)[m], 700)], width("b", m)


def ve_lc(m):
    ymap = ([(32, 32), (343, 236), (375, 268), (668, 468)], [(0, 0), (700, 500)])[m]
    xmap = ([(200, 200), (354, 314)], [(220, 220), (358, 318)])[m]
    dx = (-25, -15)[m]
    return src("B", m, xmap=xmap, ymap=ymap, tf=(1, 0, 0, 1, dx, 0)), width("B", m) - 40 + dx


def ii(k, m):
    L = P(k, m)["L"]
    if k is CAP:
        c = src("N", m)
    else:
        xmap = ([(122, 122), (548, 460)], [(225, 225), (425, 345)])[m]
        c = src("N", m, xmap=xmap, ymap=[(0, 0), (700, 500)])
    return mirror(c, L, L)


def em_lc(m):
    xmap = ([(122, 122), (671, 551)], [(225, 225), (567, 467)])[m]
    dx = (-25, -15)[m]
    return src("M", m, xmap=xmap, ymap=[(0, 0), (700, 500)], tf=(1, 0, 0, 1, dx, 0)), width("M", m) - (120, 100)[m] + dx


def ya(k, m):
    if k is CAP:
        return mirror(src("R", m), (55, 45)[m], (90, 30)[m])
    ymap = ([(0, 0), (284, 190), (316, 222), (668, 468), (700, 500)], [(0, 0), (700, 500)])[m]
    xmap = ([(200, 200), (343, 293)], [(240, 240), (332, 292)])[m]
    return mirror(src("R", m, xmap=xmap, ymap=ymap), (45, 35)[m], (65, 20)[m])


def ka_lc(m):
    c = src("k", m)
    x0, x1, _, _ = bbox([c[0]])
    return [rect(x0, 0, x1, 500)] + c[1:], width("k", m)


def zhe(k, m):
    if k is CAP:
        c, w0 = src("K", m), width("K", m)
        stem, diags = c[2], c[:2]
    else:
        c, w0 = ka_lc(m)
        stem, diags = c[0], c[1:]
    x0, x1, _, _ = bbox([stem])
    sc = (x0 + x1) / 2
    reach = bbox(diags)[1] - sc
    rsb = w0 - bbox(c)[1]
    cx = (25, 0)[m] + reach
    dx = cx - sc
    left = transform(diags, (-1, 0, 0, 1, 2 * cx - dx, 0))
    return shift(diags + [stem], dx) + left, cx + reach + rsb


def ze_lc(m):
    ymap = ([(20, 20), (359, 245), (390, 276), (680, 470)], [(0, 0), (700, 500)])[m]
    xmap = ([(150, 150), (275, 235)], [(150, 150), (306, 266)])[m]
    return src("three", m, xmap=xmap, ymap=ymap), width("three", m) - 40


def ef(k, m):
    p = P(k, m)
    if k is CAP:
        b = src("P", m, idx=[1], tf=(1, 0, 0, 1, 0, (-142, -109)[m]))
        x0, x1, _, _ = bbox(src("P", m, idx=[0]))
        sc = (x0 + x1) / 2
        reach = bbox(b)[1] - sc
        cx = (40, 30)[m] + reach
        right = shift(b, cx - sc)
        left = transform(b, (-1, 0, 0, 1, cx + sc, 0))
        stem = rect(cx - p["S"] / 2, 0, cx + p["S"] / 2, p["H"])
        return [stem] + right + left, 2 * cx
    # lowercase: bowl of d on the left, bowl of b on the right, long stem
    dl, ds = src("d", m, idx=[0]), src("d", m, idx=[1])
    bl, bs = src("b", m, idx=[0]), src("b", m, idx=[1])
    dsc = sum(bbox(ds)[:2]) / 2
    bsc = sum(bbox(bs)[:2]) / 2
    cx = dsc - bbox(dl)[0] + (25, 10)[m]
    c = shift(dl, cx - dsc) + shift(bl, cx - bsc) + [rect(cx - p["S"] / 2, -200, cx + p["S"] / 2, 700)]
    return c, bbox(c)[1] + (25, 10)[m]


def ereversed(k, m):
    p = P(k, m)
    base = "C" if k is CAP else "c"
    c, w = mirror(src(base, m), width(base, m) - bbox(src(base, m))[1], bbox(src(base, m))[0])
    x0, x1, _, _ = bbox(c)
    y = p["H"] / 2
    return c + [rect(x0 + 0.38 * (x1 - x0), y - p["B"] / 2, x1 - p["S"] / 2, y + p["B"] / 2)], w


def e_ukr(k, m):
    p = P(k, m)
    base = "C" if k is CAP else "c"
    c = src(base, m)
    x0, x1, _, _ = bbox(c)
    y = p["H"] / 2
    return c + [rect(x0 + p["S"] / 2, y - p["B"] / 2, x0 + 0.62 * (x1 - x0), y + p["B"] / 2)], width(base, m)


def yu(k, m):
    p = P(k, m)
    base = "O" if k is CAP else "o"
    o = src(base, m)
    ox0 = bbox(o)[0]
    gap = (60, 60)[m]
    x = p["L"] + p["S"] + gap
    y = p["H"] / 2
    c = [rect(p["L"], 0, p["L"] + p["S"], p["H"]), rect(p["L"] + p["S"] - 5, y - p["B"] / 2, x + 30, y + p["B"] / 2)]
    return c + shift(o, x - ox0), x - ox0 + width(base, m)


def lje(k, m):
    p = P(k, m)
    c, _ = el(k, m)
    b, rsb = bowl(k, m)
    b = shift(b, EL[id(k)][m]["stem"] - p["L"])
    return c + b, bbox(b)[1] + rsb


def nje(k, m):
    p = P(k, m)
    xr = {id(CAP): (400, 425), id(LC): (330, 300)}[id(k)][m]
    b, rsb = bowl(k, m)
    top = bbox(b)[3] if k is LC else (410, 450)[m]
    b = shift(b, xr - p["L"])
    L, S = p["L"], p["S"]
    c = [rect(L, 0, L + S, p["H"]), rect(xr, 0, xr + S, p["H"]), rect(L, top - p["B"], xr + S, top)]
    return c + b, bbox(b)[1] + rsb


def tshe_parts(m):
    """h moved right with its shoulder lowered in Black so the cap bar fits above it."""
    dx = (70, 80)[m]
    ymap = ([], [(280, 280), (350, 290)])[m]
    shoulder = src("h", m, idx=[0], ymap=ymap, tf=(1, 0, 0, 1, dx, 0))
    shortstem = src("h", m, idx=[1], tf=(1, 0, 0, 1, dx, 0))
    stem = src("h", m, idx=[2], tf=(1, 0, 0, 1, dx, 0))
    bar = rect((25, 0)[m], (670, 540)[m], (400, 420)[m], 700)
    return shoulder, shortstem, stem, bar, width("h", m) + dx


def j_tail(m, shortstem):
    """Stem + hook of j, shortened so it hangs from the shoulder in place of the short stem."""
    j = src("j", m, idx=[1])
    _, jx1, _, _ = bbox(j)
    sx0, sx1, _, sy1 = bbox(shortstem)
    j = remap(j, ymap=[((-57, 0)[m], (-57, 0)[m]), (500, sy1)])
    return shift(j, sx1 - jx1)


def tshe(m):
    shoulder, shortstem, stem, bar, w = tshe_parts(m)
    return shoulder + shortstem + stem + [bar], w


def dje(m):
    shoulder, shortstem, stem, bar, w = tshe_parts(m)
    return shoulder + stem + [bar] + j_tail(m, shortstem), w


def dje_lc(m):
    shortstem = src("h", m, idx=[1])
    return src("h", m, idx=[0, 2]) + src("hbar", m, idx=[1]) + j_tail(m, shortstem), width("hbar", m)


# ---------- glyph table: name, unicode, builder (m -> (contours, width)) or alias, kerning groups (left, right)

C, L_ = CAP, LC
GLYPHS = [
    # uppercase
    ("A-cy", "0410", "A"), ("Be-cy", "0411", lambda m: be(C, m), ("H", "B")), ("Ve-cy", "0412", "B"),
    ("Ge-cy", "0413", lambda m: ge(C, m), ("H", "F")), ("De-cy", "0414", lambda m: de(C, m), (None, None)),
    ("Ie-cy", "0415", "E"), ("Zhe-cy", "0416", lambda m: zhe(C, m), ("X", "K")), ("Ze-cy", "0417", "three", (None, None)),
    ("Ii-cy", "0418", lambda m: ii(C, m), ("H", "H")), ("Ka-cy", "041A", "K"),
    ("El-cy", "041B", lambda m: el(C, m), (None, "H")), ("Em-cy", "041C", "M"), ("En-cy", "041D", "H"),
    ("O-cy", "041E", "O"), ("Pe-cy", "041F", lambda m: pe(C, m), ("H", "H")), ("Er-cy", "0420", "P"),
    ("Es-cy", "0421", "C"), ("Te-cy", "0422", "T"),
    ("U-cy", "0423", lambda m: (src("y", m, tf=(1, 0, 0, 1, 0, 200)), width("y", m)), ("Y", "Y")),
    ("Ef-cy", "0424", lambda m: ef(C, m), ("O", "O")), ("Ha-cy", "0425", "X"),
    ("Tse-cy", "0426", lambda m: tse(C, m), ("H", None)), ("Che-cy", "0427", lambda m: che(C, m), (None, "H")),
    ("Sha-cy", "0428", lambda m: sha(C, m), ("H", "H")), ("Shcha-cy", "0429", lambda m: sha(C, m, tail=True), ("H", None)),
    ("Hardsign-cy", "042A", lambda m: hard(C, m), ("T", "B")), ("Yeru-cy", "042B", lambda m: yeru(C, m), ("H", "H")),
    ("Softsign-cy", "042C", lambda m: soft(C, m), ("H", "B")), ("Ereversed-cy", "042D", lambda m: ereversed(C, m), (None, "O")),
    ("Yu-cy", "042E", lambda m: yu(C, m), ("H", "O")), ("Ya-cy", "042F", lambda m: ya(C, m), (None, "H")),
    ("Dze-cy", "0405", "S"), ("I-cy", "0406", "I"), ("Je-cy", "0408", "J"), ("Io-cy", "0401", "Edieresis"),
    ("Yi-cy", "0407", "Idieresis"), ("Iegrave-cy", "0400", "Egrave"),
    ("E-cy", "0404", lambda m: e_ukr(C, m), ("O", "C")),
    ("Geupturn-cy", "0490", lambda m: geupturn(C, m), ("H", "F")),
    ("Lje-cy", "0409", lambda m: lje(C, m), (None, "B")), ("Nje-cy", "040A", lambda m: nje(C, m), ("H", "B")),
    ("Tshe-cy", "040B", tshe, ("T", None)), ("Dje-cy", "0402", dje, ("T", None)),
    ("Dzhe-cy", "040F", lambda m: tse(C, m, center=True), ("H", "H")),
    # lowercase
    ("a-cy", "0430", "a"), ("be-cy", "0431", lambda m: be(L_, m), ("b", "o")), ("ve-cy", "0432", ve_lc, ("m", None)),
    ("ge-cy", "0433", lambda m: ge(L_, m), ("m", "r")), ("de-cy", "0434", lambda m: de(L_, m), (None, None)),
    ("ie-cy", "0435", "e"), ("zhe-cy", "0436", lambda m: zhe(L_, m), ("x", "k")), ("ze-cy", "0437", ze_lc, (None, None)),
    ("ii-cy", "0438", lambda m: ii(L_, m), ("m", "h")), ("ka-cy", "043A", ka_lc, ("m", "k")),
    ("el-cy", "043B", lambda m: el(L_, m), (None, "h")), ("em-cy", "043C", em_lc, ("m", "h")),
    ("en-cy", "043D", en_lc, ("m", "h")), ("o-cy", "043E", "o"), ("pe-cy", "043F", lambda m: pe(L_, m), ("m", "h")),
    ("er-cy", "0440", "p"), ("es-cy", "0441", "c"), ("te-cy", "0442", te_lc, (None, None)), ("u-cy", "0443", "y"),
    ("ef-cy", "0444", lambda m: ef(L_, m), ("o", "o")), ("ha-cy", "0445", "x"),
    ("tse-cy", "0446", lambda m: tse(L_, m), ("m", None)), ("che-cy", "0447", lambda m: che(L_, m), (None, "h")),
    ("sha-cy", "0448", lambda m: sha(L_, m), ("m", "h")), ("shcha-cy", "0449", lambda m: sha(L_, m, tail=True), ("m", None)),
    ("hardsign-cy", "044A", lambda m: hard(L_, m), (None, "o")), ("yeru-cy", "044B", lambda m: yeru(L_, m), ("m", "h")),
    ("softsign-cy", "044C", lambda m: soft(L_, m), ("m", "o")), ("ereversed-cy", "044D", lambda m: ereversed(L_, m), (None, "o")),
    ("yu-cy", "044E", lambda m: yu(L_, m), ("m", "o")), ("ya-cy", "044F", lambda m: ya(L_, m), (None, "h")),
    ("dze-cy", "0455", "s"), ("i-cy", "0456", "i"), ("je-cy", "0458", "j"), ("io-cy", "0451", "edieresis"),
    ("yi-cy", "0457", "idieresis"), ("iegrave-cy", "0450", "egrave"),
    ("e-cy", "0454", lambda m: e_ukr(L_, m), ("o", "c")),
    ("geupturn-cy", "0491", lambda m: geupturn(L_, m), ("m", "r")),
    ("lje-cy", "0459", lambda m: lje(L_, m), (None, "o")), ("nje-cy", "045A", lambda m: nje(L_, m), ("m", "o")),
    ("tshe-cy", "045B", "hbar"), ("dje-cy", "0452", dje_lc, ("b", None)),
    ("dzhe-cy", "045F", lambda m: tse(L_, m, center=True), ("m", "h")),
]
# base + combining mark, mark centred over the base; caps marks sit 200 higher (like Abreve)
ACCENTED = [
    ("Iishort-cy", "0419", "Ii-cy", "brevecomb"), ("Ushort-cy", "040E", "U-cy", "brevecomb"),
    ("Gje-cy", "0403", "Ge-cy", "acutecomb"), ("Kje-cy", "040C", "Ka-cy", "acutecomb"),
    ("Iigrave-cy", "040D", "Ii-cy", "gravecomb"),
    ("iishort-cy", "0439", "ii-cy", "brevecomb"), ("ushort-cy", "045E", "y", "brevecomb"),
    ("gje-cy", "0453", "ge-cy", "acutecomb"), ("kje-cy", "045C", "ka-cy", "acutecomb"),
    ("iigrave-cy", "045D", "ii-cy", "gravecomb"),
]

# ---------- write into the font

names = {g[0] for g in GLYPHS} | {g[0] for g in ACCENTED}
for g in [g for g in f.glyphs if g.name in names]:
    f.glyphs.pop(f.glyphs.index(g))


def new_glyph(name, uni, groups):
    g = GSGlyph(name)
    g.unicode = uni
    g.leftKerningGroup, g.rightKerningGroup = groups
    f.glyphs.append(g)
    return g


def new_layer(g, m, w):
    layer = GSLayer()
    layer.layerId = layer.associatedMasterId = MASTERS[m]
    layer.width = round(w)
    g.layers.append(layer)
    return layer


def add_contours(layer, contours):
    for c in contours:
        p = GSPath()
        p.closed = True
        p.nodes = [GSNode((round(x), round(y)), t) for x, y, t in c]
        layer.paths.append(p)


def contours_of(name, m):
    return built.get((name, m)) or sum(items(name, m), [])


for entry in GLYPHS:
    name, uni, how = entry[:3]
    if isinstance(how, str):  # component alias
        base = f.glyphs[how]
        groups = entry[3] if len(entry) > 3 else (base.leftKerningGroup, base.rightKerningGroup)
        g = new_glyph(name, uni, groups)
        for m in range(2):
            new_layer(g, m, width(how, m)).components.append(GSComponent(how))
        continue
    g = new_glyph(name, uni, entry[3])
    for m in range(2):
        contours, w = how(m)
        built[(name, m)] = contours
        add_contours(new_layer(g, m, w), contours)

for name, uni, base, mark in ACCENTED:
    bg = f.glyphs[base]
    g = new_glyph(name, uni, (bg.leftKerningGroup, bg.rightKerningGroup))
    for m in range(2):
        x0, x1, _, _ = bbox(contours_of(base, m))
        mx0, mx1, _, _ = bbox(contours_of(mark, m))
        dy = 200 if name[0].isupper() else 0
        layer = new_layer(g, m, width(base, m))
        layer.components.append(GSComponent(base))
        layer.components.append(GSComponent(mark, offset=(round((x0 + x1 - mx0 - mx1) / 2), dy)))

f.save(path)
print(f"added {len(names)} glyphs")
