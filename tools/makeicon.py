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

background(BG_TOP, BG_BOT)

# ------------------------------------------------- links: Pellet-Cluster
S = SS
pellets = [
    ((146, 470), (146, 576)),
    ((222, 502), (222, 608)),
    ((112, 606), (112, 712)),
    ((190, 640), (190, 746)),
]
for (ax, ay), (bx, by) in pellets:
    capsule(ax, ay, bx, by, 31, PELLET, PELLET_EDGE, edge_w=6)
    capsule(ax - 9, ay + 17, bx - 9, by - 17, 8, PELLET_HI)

# ------------------------------------------------------ Mitte: Pfeil ">"
capsule(370, 600, 492, 600, 29, CREAM)
triangle([(468, 526), (468, 674), (582, 600)], CREAM)

# --------------------------------------------- rechts: Heu-/Strohbuendel
fan_x, fan_y = 800, 776
for ang, ln in ((-118, 250), (-100, 285), (-82, 296), (-64, 278), (-46, 238), (-134, 208), (-30, 190)):
    a = math.radians(ang)
    ex, ey = fan_x + math.cos(a) * ln, fan_y + math.sin(a) * ln
    capsule(fan_x, fan_y, ex, ey, 13, HAY, HAY_EDGE, edge_w=4)
for ang, ln in ((-109, 178), (-73, 190)):
    a = math.radians(ang)
    ex, ey = fan_x + math.cos(a) * ln, fan_y + math.sin(a) * ln
    capsule(fan_x, fan_y, ex, ey, 5, HAY_HI)

# ------------------------------------------------------ "x4" oben mittig
# "x"
capsule(392, 236, 470, 314, 17, CREAM)
capsule(470, 236, 392, 314, 17, CREAM)
# "4": Diagonale, Querbalken, Senkrechte
capsule(566, 318, 636, 196, 18, CREAM)
capsule(556, 318, 682, 318, 18, CREAM)
capsule(646, 190, 646, 356, 18, CREAM)

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
