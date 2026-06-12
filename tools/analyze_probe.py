#!/usr/bin/env python3
"""Analyze the tedtest.png probe screenshot.

Finds the screen area by locating the test rows, then reports per-pixel
colors for the striped char in row 6 (attr bit3=1) vs row 8 (attr bit3=0).
If bit3 gates multicolor per char (C64 style), row 8 renders hires:
%01010101 -> alternating single-width pixels. If MCM is global on TED,
both rows render identical structure (solid-color rows), only hue differs.
"""
import sys
from PIL import Image

img = Image.open(sys.argv[1] if len(sys.argv) > 1 else "build/tedtest.png").convert("RGB")
W, H = img.size
px = img.load()

# Find the leftmost/topmost non-black pixel region to anchor the layout.
# Row 2 of the screen (16 colored cells) is the first bright feature.
minx, miny = W, H
for y in range(H):
    for x in range(W):
        r, g, b = px[x, y]
        if r + g + b > 90:
            if y < miny: miny, minx = y, x
            if y == miny and x < minx: minx = x
    if miny < H and y > miny + 4:
        break

# row 2 starts at char col 12 -> anchor: minx is col12*8, miny is row2*8
x0 = minx - 12 * 8   # screen origin x
y0 = miny - 2 * 8    # screen origin y
print(f"screen origin estimate: ({x0},{y0})  image {W}x{H}")

def cell(row, col):
    return x0 + col * 8, y0 + row * 8

def dump_charrow(label, row, col, charline):
    cx, cy = cell(row, col)
    y = cy + charline
    cols = [px[cx + i, y] for i in range(8)]
    print(f"{label} charline {charline}: " + " ".join(f"{r:02x}{g:02x}{b:02x}" for r, g, b in cols))

print("\n--- row 2: char3 (all %11), attr lum7 color 0..15 (one sample px per cell) ---")
for i in range(16):
    cx, cy = cell(2, 12 + i)
    print(f"  col{i:2d} attr={0x70 | i:02x}: {px[cx + 3, cy + 3]}")

print("\n--- row 4: char3 (all %11), attr color2, lum 0..7 ---")
for i in range(8):
    cx, cy = cell(4, 12 + i)
    print(f"  lum{i}: {px[cx + 3, cy + 3]}")

print("\n--- row 6 (attr $0A, bit3=1) vs row 8 (attr $02, bit3=0), striped char ---")
print("char lines: 0=%00000000 1=%01010101 2=%10101010 3=%11111111")
for line in range(4):
    dump_charrow("row6", 6, 13, line)
for line in range(4):
    dump_charrow("row8", 8, 13, line)

print("\n--- row 10: solid chars 0,1,2,3 ---")
for i in range(4):
    cx, cy = cell(10, 12 + i)
    print(f"  char{i}: {px[cx + 3, cy + 3]}")
