#!/usr/bin/env python3
"""Erzeugt icon.dds (256x256, unkomprimiertes BGRA) + icon.png fuer den FS25-Mod."""
import math
import struct
import zlib
import sys

SS = 4                      # Supersampling
W = H = 256
BW = BH = W * SS

buf = bytearray(BW * BH * 3)


def put(x, y, c):
    i = (y * BW + x) * 3
    buf[i] = c[0]
    buf[i + 1] = c[1]
    buf[i + 2] = c[2]


def lerp(a, b, t):
    return tuple(int(round(a[k] + (b[k] - a[k]) * t)) for k in range(3))


def background(top, bottom, vignette=0.55):
    cx, cy = BW / 2, BH / 2
    maxd = math.hypot(cx, cy)
    for y in range(BH):
        base = lerp(top, bottom, y / (BH - 1))
        for x in range(BW):
            d = math.hypot(x - cx, y - cy) / maxd
            f = 1.0 - vignette * (d ** 2)
            put(x, y, (int(base[0] * f), int(base[1] * f), int(base[2] * f)))


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    L = vx * vx + vy * vy
    t = 0.0 if L == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / L))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def capsule(ax, ay, bx, by, r, color, edge=None, edge_w=6):
    x0 = int(min(ax, bx) - r - edge_w) - 1
    x1 = int(max(ax, bx) + r + edge_w) + 2
    y0 = int(min(ay, by) - r - edge_w) - 1
    y1 = int(max(ay, by) + r + edge_w) + 2
    for y in range(max(0, y0), min(BH, y1)):
        for x in range(max(0, x0), min(BW, x1)):
            d = seg_dist(x + 0.5, y + 0.5, ax, ay, bx, by)
            if d <= r:
                put(x, y, color)
            elif edge is not None and d <= r + edge_w:
                put(x, y, edge)


def triangle(pts, color):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    (x1, y1), (x2, y2), (x3, y3) = pts

    def side(px, py, ax, ay, bx, by):
        return (bx - ax) * (py - ay) - (by - ay) * (px - ax)

    for y in range(max(0, int(min(ys)) - 1), min(BH, int(max(ys)) + 2)):
        for x in range(max(0, int(min(xs)) - 1), min(BW, int(max(xs)) + 2)):
            px, py = x + 0.5, y + 0.5
            d1 = side(px, py, x1, y1, x2, y2)
            d2 = side(px, py, x2, y2, x3, y3)
            d3 = side(px, py, x3, y3, x1, y1)
            if (d1 >= 0 and d2 >= 0 and d3 >= 0) or (d1 <= 0 and d2 <= 0 and d3 <= 0):
                put(x, y, color)


# ---------------------------------------------------------------- Farben
BG_TOP = (46, 82, 52)
BG_BOT = (16, 30, 20)
PELLET = (150, 96, 44)
PELLET_HI = (188, 130, 66)
PELLET_EDGE = (28, 22, 14)
HAY = (232, 190, 74)
HAY_HI = (248, 220, 130)
HAY_EDGE = (60, 42, 12)
CREAM = (246, 244, 232)

# ------------------------------------------------------------- Bausteine

def hay_fan(cx, cy):
    """Heu-/Strohbuendel, aufgefaechert nach oben (Fusspunkt cx, cy)."""
    for ang, ln in ((-108, 225), (-100, 258), (-92, 285), (-84, 296),
                    (-76, 280), (-68, 250), (-62, 215)):
        a = math.radians(ang)
        capsule(cx, cy, cx + math.cos(a) * ln, cy + math.sin(a) * ln,
                13, HAY, HAY_EDGE, edge_w=4)
    for ang, ln in ((-98, 172), (-80, 180)):
        a = math.radians(ang)
        capsule(cx, cy, cx + math.cos(a) * ln, cy + math.sin(a) * ln, 5, HAY_HI)


def pellet_cluster(cx, cy):
    """Vier gepresste Pellets - kompakter Haufen statt loser Halme.
    Leicht gekippt und mit Luecke zwischen den Spalten, damit bei 256 px
    vier Koerner erkennbar bleiben und nicht ein Balken entsteht."""
    for dx0, dy0, dx1, dy1 in ((-62, -150, -44, -58), (44, -136, 60, -44),
                               (-58, -6, -40, 86), (40, 8, 58, 100)):
        ax, ay, bx, by = cx + dx0, cy + dy0, cx + dx1, cy + dy1
        capsule(ax, ay, bx, by, 27, PELLET, PELLET_EDGE, edge_w=5)
        capsule(ax - 8, ay + 20, bx - 8, by - 20, 7, PELLET_HI)


def arrow(x0, y):
    """Pfeil nach rechts, Gesamtlaenge 140 ab x0."""
    capsule(x0, y, x0 + 86, y, 22, CREAM)
    triangle([(x0 + 74, y - 56), (x0 + 74, y + 56), (x0 + 140, y)], CREAM)


def glyph_div(cx, cy):
    capsule(cx - 34, cy, cx + 34, cy, 10, CREAM)
    capsule(cx, cy - 28, cx, cy - 28, 12, CREAM)
    capsule(cx, cy + 28, cx, cy + 28, 12, CREAM)


def glyph_times(cx, cy):
    capsule(cx - 24, cy - 24, cx + 24, cy + 24, 11, CREAM)
    capsule(cx + 24, cy - 24, cx - 24, cy + 24, 11, CREAM)


def glyph_four(cx, cy):
    capsule(cx - 33, cy + 28, cx + 11, cy - 48, 11, CREAM)   # Diagonale
    capsule(cx - 39, cy + 28, cx + 39, cy + 28, 11, CREAM)   # Querbalken
    capsule(cx + 17, cy - 51, cx + 17, cy + 51, 11, CREAM)   # Senkrechte


# ------------------------------------------------------------ Komposition
#
# Heu -> Pellets -> Heu: der Umweg ueber die Presse ist mit dem Mod
# verlustfrei, deshalb sind beide Buendel gleich gross. Das Pressen
# viertelt das Volumen (:4), der Mischwagen rechnet es wieder hoch (x4).

background(BG_TOP, BG_BOT)

hay_fan(124, 755)
arrow(255, 595)
pellet_cluster(512, 607)
arrow(629, 595)
hay_fan(867, 755)

glyph_div(279, 325)
glyph_four(365, 325)
glyph_times(653, 325)
glyph_four(739, 325)

# ------------------------------------------------------------- Downsample
out = bytearray(W * H * 3)
for y in range(H):
    for x in range(W):
        r = g = b = 0
        for dy in range(SS):
            row = (y * SS + dy) * BW
            for dx in range(SS):
                i = (row + x * SS + dx) * 3
                r += buf[i]
                g += buf[i + 1]
                b += buf[i + 2]
        n = SS * SS
        i = (y * W + x) * 3
        out[i] = r // n
        out[i + 1] = g // n
        out[i + 2] = b // n

# ------------------------------------------------------------------- PNG
def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += out[y * W * 3:(y + 1) * W * 3]

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ------------------------------------------------------------------- DDS
def write_dds(path):
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x0000100F)   # CAPS|HEIGHT|WIDTH|PITCH|PIXELFORMAT
    struct.pack_into("<I", header, 12, H)
    struct.pack_into("<I", header, 16, W)
    struct.pack_into("<I", header, 20, W * 4)       # pitch
    struct.pack_into("<I", header, 76, 32)          # pixelformat size
    struct.pack_into("<I", header, 80, 0x41)        # ALPHAPIXELS|RGB
    struct.pack_into("<I", header, 88, 32)          # bit count
    struct.pack_into("<I", header, 92, 0x00FF0000)  # R
    struct.pack_into("<I", header, 96, 0x0000FF00)  # G
    struct.pack_into("<I", header, 100, 0x000000FF) # B
    struct.pack_into("<I", header, 104, 0xFF000000) # A
    struct.pack_into("<I", header, 108, 0x1000)     # DDSCAPS_TEXTURE

    pix = bytearray(W * H * 4)
    for i in range(W * H):
        r, g, b = out[i * 3], out[i * 3 + 1], out[i * 3 + 2]
        pix[i * 4] = b
        pix[i * 4 + 1] = g
        pix[i * 4 + 2] = r
        pix[i * 4 + 3] = 255
    with open(path, "wb") as f:
        f.write(bytes(header) + bytes(pix))


base = sys.argv[1]
write_png(base + ".png")
write_dds(base + ".dds")
print("written:", base + ".png", base + ".dds")
